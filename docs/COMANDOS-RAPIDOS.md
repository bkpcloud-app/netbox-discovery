# netbox-discovery 1.10.9 — Comandos rápidos

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

## Network — dry-run

```bash
netbox-discovery run
```

Fluxo:

```text
DISCOVER → CLASSIFY → RECONCILE → PLAN
NetBox write: NÃO
```

A partir da 1.10.9, o próprio comando mostra:

```text
NETWORK PLAN DIAGNÓSTICO
NETWORK NOVOS OBJETOS READY
NETWORK AJUSTES READY
NETWORK PENDÊNCIAS POR MOTIVO
NETWORK PENDÊNCIAS DETALHADAS
```

Para `REVIEW`/`BLOCKED`, mostra IP, nome, role, confiança, motivos, match, fabricante/modelo/serial, SNMP e evidência CLASSIFY.

**Não usar Python auxiliar para abrir/filtrar PLAN na operação normal.**

## Network — APPLY

Somente depois de revisar o PLAN:

```bash
netbox-discovery run --apply
```

Política:

```text
READY   → pode escrever
REVIEW  → não escreve
BLOCKED → não escreve
```

O APPLY executa IMPORT apenas de READY e depois AUDIT.

## Network — motivos importantes

```text
CONFIDENCE_*                    → REVIEW
UNKNOWN_ROLE                    → REVIEW
STANDALONE_OOB_NEEDS_PARENT     → REVIEW
IDENTITY_CONFLICT               → BLOCKED
IP_ASSIGNED_TO_OTHER_DEVICE     → BLOCKED
IP_ASSIGNED_TO_EXTERNAL_OBJECT  → REVIEW
```

Não corrigir dezenas de objetos manualmente no NetBox para “ajudar” o discovery.

## Hypervisor — configurar

```bash
netbox-discovery hypervisor configure
netbox-discovery hypervisor check
```

## Hypervisor — dry-run

```bash
netbox-discovery hypervisor run
```

Mostra READY/CREATE, UPDATE_SAFE, RECLASSIFY_SAFE, REVIEW e BLOCKED.

## Hypervisor — comparar

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

## Hypervisor — APPLY

```bash
netbox-discovery hypervisor run --apply
```

Antes da escrita:

```text
HYPERVISOR PREFLIGHT GLOBAL MULTI-CONTEXT
PREFLIGHT GLOBAL: OK
REVIEW/BLOCKED: 0
```

### Cluster/Site — 1.10.7

```text
RECLASSIFY PREFLIGHT
→ CLUSTER SCOPE RELEASE
→ move HOSTS
→ reaplica scope do CLUSTER
→ continua VMs
```

### VM/Parent — 1.10.8

```text
revalida identidade da VM
→ relê Device/Cluster
→ VM PARENT PREFLIGHT
→ PATCH tenant + site juntos
→ ajusta Tenant dos IPs
```

## Falha parcial

```text
1. confirmar processo/lock
2. não repetir --apply cegamente
3. usar compare/dry-run
4. revisar estado real
5. somente então retomar
```

## Política geral

```text
READY / CREATE            → escrita somente com --apply
READY / UPDATE_SAFE       → escrita somente com --apply
READY / RECLASSIFY_SAFE   → escrita após preflight
REVIEW                    → não escreve
BLOCKED                   → não escreve
COMPARE                   → somente leitura
DELETE automático         → NÃO
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
Lock global:            /var/lock/netbox-discovery-global.lock
```

## Homologação

```text
docs/HOMOLOGACAO.md
```

CI PASS não significa LIVE PASS.
