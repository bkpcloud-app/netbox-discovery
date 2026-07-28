# netbox-discovery 1.10.17 — Matriz de Homologação

## Estados

```text
LIVE PASS     = validado ao vivo com evidência
LIVE PARTIAL  = parte relevante validada, fluxo completo pendente
CI PASS       = regressões automatizadas passaram
NOT LIVE      = ainda não validado ao vivo
```

CI PASS não equivale a LIVE PASS.

## Hypervisor

**Estado:** LIVE PASS.

```text
Objetos comparados: 282
OK: 282
MISMATCH: 0
MISSING: 0
AMBIGUOUS: 0
COMPARE STATUS: OK
```

## Network — funções LIVE PASS

```text
ownership por IP → DELEGATED
Dell N2024/PCT7024/S4128F-ON → NETWORK_SWITCH/HIGH
VM por nome único → DELEGATED
Device físico + VM → BLOCKED
precedência de ownership por IP → DELEGATED preservado
Dell MD3200BKP .56/.57 → 1 STORAGE com MGMT + MGMT-2
preflight global base → PASS
IMPORT normal → PASS
MAC RECONCILE de Devices → PASS
```

## APPLY real da 1.10.14 — MD3200BKP

**Estado:** LIVE PASS.

```text
10.1.1.56 + 10.1.1.57
role=STORAGE
model=PowerVault MD32xx
READY/CREATE inicial: 1
READY/CREATE posterior: 0
```

## APPLY real da 1.10.15 — ME5024 e audit

**Estado:** LIVE PASS com warnings não destrutivos.

```text
MAC RECONCILE: PASS
Assets FAIL: 0
Checks FAIL: 0
Status: PASS_WITH_WARNINGS
```

O erro anterior `MAC_MISSING | ME5024 | 00:C0:FF:66:B4:BF` foi eliminado.

Warnings preservados:

```text
nomes live dos hosts VMware
Dell Inc. versus Dell no fabricante
nome live ME4024-10-1-1-52 preservado
```

## APPLY real da 1.10.16 — resultado

Executado em 28/07/2026 no Site DCM.

### Plano

```text
Planner: 4.6-product
READY/CREATE: 0
READY/UPDATE_SAFE: 0
READY/REPAIR_SAFE: 0
DELEGATED/HYPERVISOR: 42
REVIEW: 1
BLOCKED: 1
```

### Safety

**Estado:** LIVE PASS para bloqueio conservador.

O produto confirmou:

```text
SRV-AE11
VM única por nome: ID 359
MAC VMware forte: 00:50:56:9F:9E:70
Device duplicado criado pelo produto
Interfaces cadastradas na VM: 0
```

E bloqueou sem tentar adivinhar uma interface:

```text
REPAIR_SAFE_NOT_ELIGIBLE:
Fallback de interface única exige exatamente uma interface na VM: 0

Reparos seguros concluídos: 0
```

### Import/Audit 1.10.16

**Estado:** LIVE PASS para o conjunto normal.

```text
PREFLIGHT GLOBAL FINALIZE: OK
Assets READY processados: 13
Runtime blocked: 0
Erros: 0
MAC RECONCILE: PASS
Assets FAIL: 0
Checks FAIL: 0
Status: PASS_WITH_WARNINGS
```

O `SRV-AE11` permaneceu `BLOCKED`; portanto não foi alterado.

## 1.10.17 — criar interface ausente e concluir SRV-AE11

**Estado:** NOT LIVE até a execução final.

O PLAN V7 só promove o reparo quando:

```text
VM única por nome
+ zero interfaces live
+ exatamente um MAC VMware forte
+ MAC ausente ou sem vínculo
+ MAC não duplicado e sem outro owner
+ Device/IP/interfaces integralmente criados pelo produto
+ exatamente um IP no Device duplicado
+ VM sem outro primary IPv4
```

Fluxo esperado:

```text
READY/REPAIR_SAFE: 1
→ criar virtualization.vminterface MGMT na VM ID 359
→ criar/atribuir 00:50:56:9F:9E:70
→ definir primary MAC da interface
→ mover 10.1.1.111 para a interface da VM
→ definir primary IPv4 da VM se vazio
→ remover somente o Device SRV-AE11 duplicado
→ preservar a VM
```

O audit V7 deve comprovar:

```text
REPAIR_VM_INTERFACE_CREATED_OK
REPAIR_VM_MAC_OK
REPAIR_DUPLICATE_DEVICE_REMOVED
REPAIR_IP_ON_VM
REPAIR_VM_PRIMARY_IP_OK
REPAIR_IDEMPOTENCY_DELEGATED
Assets FAIL: 0
Checks FAIL: 0
```

## Única validação live da 1.10.17

```bash
netbox-discovery update run
netbox-discovery version
netbox-discovery run --apply
```

Critério de conclusão:

```text
Versão: 1.10.17
Planner: 4.7-product
READY/REPAIR_SAFE: 1 antes da escrita
PREFLIGHT GLOBAL FINALIZE: OK
Reparos seguros concluídos: 1
SRV-AE11 não existe mais como dcim.device
VM ID 359 preservada
10.1.1.111 pertence à virtualization.vminterface criada
novo PLAN: SRV-AE11 DELEGATED/NOOP
READY/CREATE: 0
READY/UPDATE_SAFE: 0
READY/REPAIR_SAFE: 0 no plano pós-reparo
Assets FAIL: 0
Checks FAIL: 0
```

O `10.1.1.54` pode continuar `REVIEW` sem impedir a conclusão.

## Schedulers

```text
Auto-update stable: LIVE PASS
Network scheduler: DISABLED durante homologação
Hypervisor scheduler: DISABLED durante homologação
```
