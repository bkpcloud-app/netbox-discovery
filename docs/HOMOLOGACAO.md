# netbox-discovery 1.10.16 — Matriz de Homologação

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
Dell MD3200BKP .56/.57 → 1 STORAGE com duas interfaces MGMT
preflight global base → PASS
IMPORT normal → PASS
MAC RECONCILE de Devices → PASS
```

## APPLY real da 1.10.14

### Dell MD3200BKP

**Estado:** LIVE PASS.

```text
10.1.1.56 + 10.1.1.57
role=STORAGE
model=PowerVault MD32xx
READY/CREATE inicial: 1
READY/CREATE posterior: 0
```

### IMPORT normal

**Estado:** LIVE PASS.

```text
PREFLIGHT GLOBAL FINALIZE: OK
Assets READY processados: 12
Runtime blocked: 0
Erros: 0
NetBox write: SIM
```

## APPLY real da 1.10.15

Executado em 28/07/2026 no Site DCM.

### Plano

```text
Planner: 4.5-product
READY/CREATE: 0
READY/UPDATE_SAFE: 0
READY/REPAIR_SAFE: 0
DELEGATED/HYPERVISOR: 42
REVIEW: 1
BLOCKED: 1
```

### ME5024 / MAC RECONCILE

**Estado:** LIVE PASS.

```text
Interfaces/MAC verificadas: 19
MAC RECONCILE: PASS
Assets FAIL: 0
Checks FAIL: 0
```

O erro anterior `MAC_MISSING | ME5024 | 00:C0:FF:66:B4:BF` foi eliminado.

### Audit geral

**Estado:** LIVE PASS com warnings não destrutivos.

```text
Status: PASS_WITH_WARNINGS
Assets PASS: 7
Assets WARN: 5
Assets FAIL: 0
Checks PASS: 146
Checks WARN: 9
Checks FAIL: 0
```

Warnings preservados:

```text
nomes live dos hosts VMware
Dell Inc. versus Dell no fabricante
nome live ME4024-10-1-1-52 preservado
```

### SRV-AE11

**Estado:** ainda não concluído pela 1.10.15.

A VM única foi identificada:

```text
VM ID 359
MAC VMware forte: 00:50:56:9F:9E:70
Device duplicado criado pelo produto
```

Mas a interface da VM não possuía objeto MAC no NetBox:

```text
REPAIR_SAFE_NOT_ELIGIBLE: Interface da VM por MAC não é única: 0
Reparos seguros concluídos: 0
```

O audit passou porque o asset permaneceu corretamente `BLOCKED` e não foi tratado como READY.

## 1.10.16 — fallback de interface única sem MAC

**Estado:** CI/NOT LIVE até a execução final.

O PLAN V6 só promove o reparo quando:

```text
VM única por nome
+ exatamente uma interface live
+ interface sem outro MAC
+ exatamente um MAC VMware forte
+ MAC ausente/sem vínculo/na mesma interface
+ MAC não duplicado e sem outro owner
+ todas as proteções de ownership do Device/IP
```

Resultado esperado:

```text
READY/REPAIR_SAFE: 1
VM MAC 00:50:56:9F:9E:70 criado/atribuído à única interface da VM ID 359
primary MAC da interface definido
IP 10.1.1.111 movido para virtualization.vminterface
primary IPv4 da VM definido se vazio
Device duplicado SRV-AE11 removido
VM preservada
```

VM com mais de uma interface ou com MAC divergente permanece `BLOCKED`.

## Única validação live da 1.10.16

```bash
netbox-discovery update run
netbox-discovery version
netbox-discovery run --apply
```

Critério de conclusão:

```text
Versão: 1.10.16
Planner: 4.6-product
READY/REPAIR_SAFE: 1 antes da escrita
PREFLIGHT GLOBAL FINALIZE: OK
Reparos seguros concluídos: 1
REPAIR_VM_MAC_OK
Assets FAIL: 0
Checks FAIL: 0
novo PLAN: SRV-AE11 DELEGATED/NOOP
READY/CREATE: 0
READY/UPDATE_SAFE: 0
READY/REPAIR_SAFE: 0 no plano pós-reparo
```

O `10.1.1.54` pode continuar `REVIEW` sem impedir a conclusão.

## Schedulers

```text
Auto-update stable: LIVE PASS
Network scheduler: DISABLED durante homologação
Hypervisor scheduler: DISABLED durante homologação
```
