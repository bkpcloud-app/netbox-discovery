# netbox-discovery 1.10.5 — Comandos rápidos

## Versão e saúde

```bash
netbox-discovery version
netbox-discovery status
netbox-discovery self-test
netbox-discovery health
netbox-discovery health --json
```

## Atualizar

```bash
netbox-discovery update status
netbox-discovery update check
netbox-discovery update run
```

## Hypervisor — configurar

```bash
netbox-discovery hypervisor configure
netbox-discovery hypervisor check
```

## Hypervisor — dry-run

```bash
netbox-discovery hypervisor run
```

A partir da 1.10.5 o próprio comando mostra automaticamente:

```text
HYPERVISOR NOVOS OBJETOS READY
READY / CREATE

HYPERVISOR AJUSTES/MIGRAÇÕES SEGURAS PENDENTES
READY / UPDATE_SAFE
READY / RECLASSIFY_SAFE

HYPERVISOR PENDÊNCIAS DO PLAN
REVIEW
BLOCKED

RESUMO DE ESCRITA DO DRY-RUN
CREATE READY: N
UPDATE_SAFE/RECLASSIFY_SAFE READY: N
REVIEW/BLOCKED: N
NetBox write: NÃO
```

**Não usar Python auxiliar para abrir/filtrar o PLAN na operação normal.** O produto deve mostrar isso sozinho.

## Hypervisor — APPLY

Somente depois de revisar o dry-run:

```bash
netbox-discovery hypervisor run --apply
```

## Política

```text
READY / CREATE            → cria somente com --apply
READY / UPDATE_SAFE       → atualiza somente com --apply
READY / RECLASSIFY_SAFE   → migra/reclassifica somente com --apply
REVIEW                    → não escreve
BLOCKED                   → não escreve
DELETE automático         → NÃO
```

## Mudança de inventário

```text
HYPERVISOR INVENTORY CHANGE
VMs adicionadas desde a coleta anterior: N
VMs ausentes desde a coleta anterior: N
REMOVED/REVIEW
DELETE automático: NÃO
```

## VMware — placement

Regra de rede autoritativa:

```text
1. IP que corresponde ao FQDN/nome do ESXi
2. vmk0 management
3. única rede candidata
4. ambiguidade → REVIEW
```

## Schedulers

```bash
netbox-discovery scheduler status
netbox-discovery hypervisor scheduler status
netbox-discovery update scheduler status
```

Network/Hypervisor são opt-in.

## Caminhos

```text
Aplicação:              /opt/netbox-discovery
Configuração principal: /opt/netbox-discovery/config.yml
Config Hypervisor:      /etc/netbox-discovery/hypervisors.json
Relatórios:             /opt/netbox-discovery/reports
Backups:                /opt/netbox-discovery/backups
```

## Homologação

```text
docs/HOMOLOGACAO.md
```

CI PASS não significa LIVE PASS.
