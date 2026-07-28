# netbox-discovery 1.10.17 — Comandos rápidos

## Atualizar e executar a finalização

```bash
netbox-discovery update run
netbox-discovery version
netbox-discovery run --apply
```

O `run --apply` executa descoberta, PLAN V7, preflight global, import normal, MAC reconcile, reparo seguro e audit final.

## Saída esperada antes da escrita

```text
Planner: 4.7-product
READY/CREATE: ...
READY/UPDATE_SAFE: ...
READY/REPAIR_SAFE: ...

PREFLIGHT GLOBAL FINALIZE: OK
NetBox write até aqui: NÃO
REPAIR JOURNAL: ...
```

## VM sem interface no NetBox

Cenário elegível:

```text
VM única por nome
+ zero virtualization.vminterface
+ exatamente um MAC VMware forte
+ MAC sem outro owner
+ Device/IP/interfaces integralmente criados pelo produto
```

Saída do PLAN:

```text
READY/REPAIR_SAFE | <nome> | Device ID <id> -> VM ID <id>
VM interface: CRIAR MGMT na VM ID <id>
VM MAC: <mac>
Evidência VM MAC: VM única por nome + zero interfaces + VMware MAC forte
```

Ação:

```text
cria interface MGMT
→ cria/atribui MAC VMware
→ define primary MAC
→ move IP para a VM
→ define primary IPv4 se vazio
→ remove somente o Device duplicado criado pelo produto
```

## VM com interface existente

Caminhos também aceitos:

```text
MAC VMware corresponde exatamente a uma interface live
```

ou:

```text
VM única
+ exatamente uma interface live sem MAC
+ exatamente um MAC VMware forte
+ MAC sem outro owner
```

VM com múltiplas interfaces sem correspondência inequívoca permanece `BLOCKED`.

## Reconciliação de MAC de Devices

Depois do IMPORT normal:

```text
===== MAC RECONCILE =====
Status: PASS
JSON MAC: /opt/netbox-discovery/reports/<SITE>-mac-reconcile-*.json
```

MAC pertencente a outro objeto bloqueia no preflight.

## MD32xx

```text
10.x.x.56 + 10.x.x.57
mesmo sysObjectID exato
mesmo sysName
exatamente dois endpoints consecutivos
→ 1 STORAGE
→ MGMT + MGMT-2
```

## Falha de preflight

```text
PREFLIGHT GLOBAL FINALIZE: BLOQUEADO
NetBox write: NÃO
```

Não corrigir manualmente e não repetir cegamente.

## Recuperação

```text
interface criada sem MAC
→ próxima execução usa fallback de interface única

interface + MAC criados, IP ainda no Device
→ próxima execução conclui REPAIR_SAFE

IP já movido
→ RECOVERY_AFTER_IP_MOVE
```

## Audit

```text
===== AUDIT FINALIZE RESULTADO =====
Status: PASS ou PASS_WITH_WARNINGS
Assets FAIL: 0
Checks FAIL: 0
```

Para criação da interface, o audit exige:

```text
REPAIR_VM_INTERFACE_CREATED_OK
REPAIR_VM_MAC_OK
REPAIR_DUPLICATE_DEVICE_REMOVED
REPAIR_IP_ON_VM
REPAIR_VM_PRIMARY_IP_OK
REPAIR_IDEMPOTENCY_DELEGATED
```

Relatórios:

```text
/opt/netbox-discovery/reports/<SITE>-repair-journal-*.json
/opt/netbox-discovery/reports/<SITE>-mac-reconcile-*.json
/opt/netbox-discovery/reports/<SITE>-import-finalize-*.json
/opt/netbox-discovery/reports/<SITE>-audit-finalize-*.json
```

## Dry-run normal

```bash
netbox-discovery run
```

## Hypervisor

```bash
netbox-discovery hypervisor check
netbox-discovery hypervisor run
netbox-discovery hypervisor run --compare
netbox-discovery hypervisor run --apply
```

## Status

```bash
netbox-discovery version
netbox-discovery status
netbox-discovery self-test
netbox-discovery health
```

## Política

```text
READY/CREATE                    → escreve com --apply
READY/UPDATE_SAFE               → escreve com --apply
READY/REPAIR_SAFE_VM_DUPLICATE  → escreve após preflight global
READY/NOOP                      → não altera
DELEGATED                       → não escreve
REVIEW                          → não escreve
BLOCKED                         → não escreve
DELETE de VM                    → NÃO
DELETE genérico de Device       → NÃO
```

CI PASS não significa LIVE PASS.
