# netbox-discovery 1.10.10 — Comandos rápidos

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

Se houver VMs já inventariadas:

```text
NETWORK DELEGADOS AO HYPERVISOR
DELEGATED | IP | nome | IP(s) já vinculado(s) a virtualization.vminterface
```

`DELEGATED` = ownership do Hypervisor, nenhuma escrita Network.

VM candidata sem correspondência:

```text
REVIEW
VIRTUAL_MACHINE_CANDIDATE_NO_VM_MATCH
```

## Network — APPLY

Somente depois de revisar:

```bash
netbox-discovery run --apply
```

```text
READY       → pode escrever
DELEGATED   → não escreve
REVIEW      → não escreve
BLOCKED     → não escreve
```

## Dell switches — 1.10.10

Modelos Dell Networking reconhecidos pelo hardware/ENTITY-MIB têm prioridade sobre Linux/SSH/Web genérico.

Exemplos:

```text
N2024
PCT7024
S4128F-ON
```

Esperado:

```text
role=NETWORK_SWITCH
confidence=HIGH
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
5. somente então retomar
```

## Status

```bash
netbox-discovery version
netbox-discovery status
netbox-discovery self-test
netbox-discovery health
```

O status Network mostra:

```text
PLAN: READY=N DELEGATED=N REVIEW=N BLOCKED=N
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
