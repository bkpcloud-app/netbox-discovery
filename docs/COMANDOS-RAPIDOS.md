# netbox-discovery 1.10.4 — Comandos rápidos

## Versão e saúde

```bash
netbox-discovery version
netbox-discovery status
netbox-discovery self-test
netbox-discovery health
netbox-discovery health --json
```

## Instalar em Proxy novo

```bash
curl -fsSL https://raw.githubusercontent.com/bkpcloud-app/netbox-discovery/stable/install-from-github.sh | bash
```

## Atualizar

```bash
netbox-discovery update status
netbox-discovery update check
netbox-discovery update run
```

## Configuração principal

```bash
netbox-discovery init
netbox-discovery check
```

NetBox fixo:

```text
https://inventory.bkpcloud.app.br:8080
```

## Hypervisor — configurar

```bash
netbox-discovery hypervisor configure
```

Modo da source:

```text
1 - single_site
2 - multi_site
3 - multi_tenant
```

### VMware multi-contexto

Para decidir Tenant/Site, **não use toda rede que aparece como serviço `management` no VMware**.

O resolver escolhe uma rede de gerenciamento autoritativa por Host:

```text
1. IP que corresponde ao FQDN/nome do ESXi
2. vmk0 marcada como management
3. única rede management candidata
4. várias candidatas sem evidência forte → REVIEW
```

Exemplo real do DCM:

```text
vmk0 / rede de gestão: 10.1.1.0/24
vmkernel auxiliares também marcados management:
192.168.140/141/142/143/160/161/180/181/190/191
```

As redes auxiliares continuam no inventário, mas **não viram mappings de Site**.

## Hypervisor — validar e dry-run

```bash
netbox-discovery hypervisor check
netbox-discovery hypervisor run
```

Sem `--apply`: **não escreve inventário**.

Revise:

```text
Contextos Tenant/Site
READY
REVIEW
BLOCKED
UPDATE_SAFE
RECLASSIFY_SAFE
alvo=Tenant/Site
```

### `RECLASSIFY_SAFE` — 1.10.4

Significa:

```text
mesma identidade forte já existe no NetBox
+ contexto atual diverge do mapping autoritativo
= objeto pode ser reclassificado preservando o mesmo ID
```

Ação segura somente quando a identidade global é única por serial/UUID e/ou IP/MAC vinculado.

Ambiguidade:

```text
REVIEW
```

Nunca usar nome sozinho para migrar Tenant/Site.

### VM desapareceu entre coletas

A 1.10.4 mostra automaticamente:

```text
HYPERVISOR INVENTORY CHANGE
REMOVED/REVIEW
DELETE automático: NÃO
```

Ausência de VM vira `REVIEW/NOOP`. Não existe exclusão automática.

## Hypervisor — APPLY

Somente após dry-run revisado:

```bash
netbox-discovery hypervisor run --apply
```

Durante homologação da 1.10.4, **não executar APPLY até revisar o dry-run ao vivo da própria 1.10.4**.

Nunca repetir APPLY cegamente quando o AUDIT deixar `REVIEW`, `UPDATE_SAFE` ou `RECLASSIFY_SAFE` residual inesperado.

## Hypervisor — scheduler

```bash
netbox-discovery hypervisor scheduler status
netbox-discovery hypervisor scheduler enable
netbox-discovery hypervisor scheduler disable
```

Durante homologação, mantenha desabilitado.

## Rede — dry-run

```bash
netbox-discovery run
```

## Rede — APPLY

```bash
netbox-discovery run --apply
```

## Rede — scheduler

```bash
netbox-discovery scheduler status
netbox-discovery scheduler enable
netbox-discovery scheduler disable
```

## Política

```text
READY            → elegível para escrita somente com --apply
REVIEW           → não escreve
BLOCKED          → não escreve
CREATE           → cria quando READY
UPDATE_SAFE      → atualiza quando READY
RECLASSIFY_SAFE  → move contexto quando READY
NOOP             → preserva
```

Hypervisor não executa DELETE automático.

## Auto-update

```bash
netbox-discovery update scheduler status
netbox-discovery update scheduler enable
netbox-discovery update scheduler disable
```

## Caminhos

```text
Aplicação:              /opt/netbox-discovery
Configuração principal: /opt/netbox-discovery/config.yml
Config Hypervisor:      /etc/netbox-discovery/hypervisors.json
Dependências isoladas:  /opt/netbox-discovery/vendor
Config por Site:        /opt/netbox-discovery/config/sites/
Relatórios:             /opt/netbox-discovery/reports
Backups:                /opt/netbox-discovery/backups
Lock global:            /var/lock/netbox-discovery-global.lock
```

## Homologação

```text
docs/HOMOLOGACAO.md
```

CI verde ≠ automaticamente homologado ao vivo.

## Sequência de homologação atual

```text
1. publicar 1.10.4 somente após CI PASS
2. atualizar o proxy pela stable
3. netbox-discovery version
4. netbox-discovery hypervisor check
5. netbox-discovery hypervisor run SEM --apply
6. revisar INVENTORY CHANGE
7. revisar RECLASSIFY_SAFE e qualquer REVIEW/BLOCKED
8. somente depois considerar --apply
9. AUDIT
10. novo dry-run para idempotência
```
