# netbox-discovery 1.10.1 — Comandos rápidos

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

`multi_site` e `multi_tenant` usam mappings de rede de gerenciamento → Tenant/Site.

Sources antigas permanecem `single_site` até serem editadas.

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

Após revisar o PLAN:

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

## DCM — situação atual

Antes de novo APPLY Hypervisor multi-contexto:

```text
1. atualizar
2. editar sources e escolher o modo correto
3. confirmar mappings Tenant/Site
4. hypervisor check
5. hypervisor run
6. revisar
7. NÃO usar --apply até a redistribuição estar correta
```
