# netbox-discovery 1.10.13 — Comandos rápidos

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

Saída relevante:

```text
NETWORK PLAN DIAGNÓSTICO
READY/CREATE: N
READY/UPDATE_SAFE: N
DELEGATED/HYPERVISOR: N
REVIEW: N
BLOCKED: N
NetBox write: NÃO
```

## Precedência de ownership por IP — 1.10.13

```text
IP já vinculado a virtualization.vminterface
→ DELEGATED/NOOP
→ ownership Hypervisor autoritativo
→ name bridge não pode rebaixar para REVIEW
```

A correlação por nome continua ativa quando o IP ainda não comprova ownership.

## Anti-flap de identidade — 1.10.12+

Se uma coleta perder temporariamente MAC VMware ou FA-MIB, procure:

```text
Anti-flap: identidade forte preservada de ...
VMware MAC histórico: 00:50:56:...
```

Conflito VMware com Device físico:

```text
BLOCKED
PHYSICAL_DEVICE_CONFLICT_WITH_HYPERVISOR_VM:<id>
```

VM candidata com nome único no inventário Hypervisor:

```text
DELEGATED
OWNED_BY_HYPERVISOR_VM_NAME:<id>
```

## Storage / PowerVault

```text
Storage FA-MIB: id=... product=... serial=... type=storage-subsystem(11)
```

```text
serial/connUnitId forte igual → mesmo STORAGE
connUnitId 000...000          → ignorado
identidade forte diferente    → conflito
FA-MIB transitório ausente    → histórico forte pode ser preservado por 48h
```

## Network — APPLY

Somente depois de revisar o PLAN:

```bash
netbox-discovery run --apply
```

```text
READY       → pode escrever
DELEGATED   → não escreve
REVIEW      → não escreve
BLOCKED     → não escreve
```

O IMPORT recalcula o PLAN com `planner_v3.py` antes da escrita.

## AUDIT

```text
===== AUDIT PENDÊNCIAS DETALHADAS =====
WARN | código | asset | detalhe
FAIL | código | asset | detalhe
```

## Dell switches

```text
N2024      → NETWORK_SWITCH/HIGH
PCT7024    → NETWORK_SWITCH/HIGH
S4128F-ON  → NETWORK_SWITCH/HIGH
```

## Hypervisor

```bash
netbox-discovery hypervisor configure
netbox-discovery hypervisor check
netbox-discovery hypervisor run
netbox-discovery hypervisor run --compare
netbox-discovery hypervisor run --apply
netbox-discovery hypervisor status
```

## Falha parcial

```text
1. confirmar processo/lock
2. não repetir --apply cegamente
3. usar compare/dry-run
4. revisar estado real
5. corrigir o produto, não inventário em massa
6. somente então retomar
```

## Status

```bash
netbox-discovery version
netbox-discovery status
netbox-discovery self-test
netbox-discovery health
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

CI PASS não significa LIVE PASS.
