# netbox-discovery 1.10.8 — Comandos rápidos

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

**Não usar Python auxiliar para abrir/filtrar o PLAN na operação normal.**

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

Lista `atual=Tenant/Site` versus `esperado=Tenant/Site` para Hosts, VMs, Clusters e Prefixes.

Não executa POST/PATCH.

## Hypervisor — APPLY

Somente depois de revisar dry-run/compare:

```bash
netbox-discovery hypervisor run --apply
```

Antes da primeira escrita:

```text
===== HYPERVISOR PREFLIGHT GLOBAL MULTI-CONTEXT =====
PREFLIGHT GLOBAL: OK
REVIEW/BLOCKED: 0
NetBox write até aqui: NÃO
```

Para cada contexto com migração:

```text
RECLASSIFY PREFLIGHT Tenant/Site: OK
```

Se o conjunto `RECLASSIFY_SAFE`, `existing_id`, identidade ou alvo mudar, o APPLY aborta.

### Cluster mudando de Site — 1.10.7

```text
RECLASSIFY PREFLIGHT
→ CLUSTER SCOPE RELEASE
→ move HOSTS
→ reaplica scope do CLUSTER no Site alvo
→ continua VMs
```

### VM seguindo Host/Cluster — 1.10.8

Antes de reclassificar VMs vinculadas:

```text
revalida identidade da VM
→ relê Device/Cluster
→ confirma parent no Site alvo
→ VM PARENT PREFLIGHT: OK
→ PATCH tenant + site juntos
→ ajusta Tenant dos IPs
```

Se Device/Cluster ainda estiver em outro Site, nenhuma VM daquele contexto é reclassificada.

## Falha parcial de APPLY

```text
1. NÃO repetir --apply cegamente
2. NÃO corrigir objetos em massa manualmente
3. confirmar que processo/lock terminou
4. rodar: netbox-discovery hypervisor run --compare
5. rodar dry-run se necessário
6. revisar o estado real
7. somente então autorizar novo --apply
```

O journal registra escritas concluídas. Objetos já corretos devem reaparecer como `NOOP`.

## Política

```text
READY / CREATE            → cria somente com --apply e após preflight
READY / UPDATE_SAFE       → atualiza somente com --apply e após preflight
READY / RECLASSIFY_SAFE   → reclassifica após preflight global + identidade/parent
REVIEW                    → não escreve
BLOCKED                   → não escreve
COMPARE                   → somente leitura
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

```text
1. IP que corresponde ao FQDN/nome do ESXi
2. vmk0 management
3. única rede candidata
4. ambiguidade → REVIEW
```

VM herda Tenant/Site do Host.

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
