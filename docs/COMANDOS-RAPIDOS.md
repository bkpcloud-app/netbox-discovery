# netbox-discovery 1.10.3 — Comandos rápidos

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

### VMware multi-contexto — 1.10.3

Para decidir Tenant/Site, **não use toda rede que aparece como serviço `management` no VMware**.

O resolver escolhe uma rede de gerenciamento autoritativa por Host:

```text
1. IP que corresponde ao FQDN/nome do ESXi
2. vmk0 marcada como management
3. única rede management candidata
4. várias candidatas sem evidência forte → REVIEW
```

Exemplo real do DCM que motivou a correção:

```text
vmk0 / rede de gestão: 10.1.1.0/24
vmkernel auxiliares também marcados management:
192.168.140/141/142/143/160/161/180/181/190/191
```

Na 1.10.3 essas redes auxiliares podem continuar no inventário, mas **não viram mappings de Site**.

Sources antigas permanecem `single_site` até edição explícita.

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
alvo=Tenant/Site
```

## Hypervisor — APPLY

Somente após dry-run revisado:

```bash
netbox-discovery hypervisor run --apply
```

Nunca repetir APPLY cegamente quando o AUDIT deixar `REVIEW` ou `UPDATE_SAFE` residual.

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
READY   → elegível para escrita somente com --apply
REVIEW  → não escreve
BLOCKED → não escreve
NOOP    → preserva
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

## DCM — sequência atual

```text
1. atualizar para a stable atual
2. editar uma source por vez
3. escolher multi_tenant quando o manager atender vários Tenants/Sites
4. confirmar que o wizard mostra somente a rede de gestão autoritativa do ESXi
5. confirmar Tenant/Site
6. repetir na segunda source
7. hypervisor check
8. hypervisor run SEM --apply
9. revisar redistribuição dos objetos já existentes
10. só então considerar APPLY
```
