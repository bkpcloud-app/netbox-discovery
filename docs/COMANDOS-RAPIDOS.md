# netbox-discovery 1.10.7 — Comandos rápidos

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

O próprio comando mostra automaticamente:

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

## Hypervisor — comparar NetBox × source

Depois de falha parcial ou antes de novo APPLY:

```bash
netbox-discovery hypervisor run --compare
```

Saída:

```text
OK
MISMATCH
MISSING
AMBIGUOUS
NetBox write: NÃO
```

Lista automaticamente `atual=Tenant/Site` versus `esperado=Tenant/Site` para Hosts, VMs, Clusters e Prefixes.

Não executa POST/PATCH.

## Hypervisor — APPLY

Somente depois de revisar dry-run e, quando necessário, compare:

```bash
netbox-discovery hypervisor run --apply
```

Antes da primeira escrita, o APPLY obrigatoriamente mostra:

```text
===== HYPERVISOR PREFLIGHT GLOBAL MULTI-CONTEXT =====
PREFLIGHT GLOBAL: OK
REVIEW/BLOCKED: 0
NetBox write até aqui: NÃO
```

Para cada contexto com migração:

```text
RECLASSIFY PREFLIGHT Tenant/Site: OK
NetBox write: NÃO
```

Se o conjunto `RECLASSIFY_SAFE`, o `existing_id`, a identidade forte ou o Tenant/Site alvo mudar, o APPLY aborta antes da escrita.

### Cluster mudando de Site — 1.10.7

Quando um Cluster e seus Devices-host precisam mudar juntos de Site, o produto executa:

```text
RECLASSIFY PREFLIGHT
→ CLUSTER SCOPE RELEASE
→ move HOSTS
→ reaplica scope do CLUSTER no Site alvo
→ continua VMs
```

O preflight bloqueia se existir host membro fora do Site alvo sem `HOST / RECLASSIFY_SAFE` correspondente.

## Falha parcial de APPLY

```text
1. NÃO repetir --apply cegamente
2. NÃO corrigir dezenas de objetos manualmente
3. rodar: netbox-discovery hypervisor run --compare
4. rodar: netbox-discovery hypervisor run
5. revisar o estado atual
6. somente então autorizar novo --apply
```

O journal do APPLY registra as escritas que já concluíram.

## Política

```text
READY / CREATE            → cria somente com --apply e após preflight
READY / UPDATE_SAFE       → atualiza somente com --apply e após preflight
READY / RECLASSIFY_SAFE   → reclassifica somente após preflight global + identidade
REVIEW                    → não escreve
BLOCKED                   → não escreve
COMPARE                    → somente leitura
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
