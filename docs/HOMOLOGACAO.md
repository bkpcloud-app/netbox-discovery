# netbox-discovery 1.10.18 — Matriz de Homologação

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

## Network — Site DCM

**Estado:** LIVE PASS em 29/07/2026.

### Funções validadas ao vivo

```text
ownership por IP → DELEGATED
VM por nome único → DELEGATED
Device físico + VM inequívoca → REPAIR_SAFE protegido
Dell N2024/PCT7024/S4128F-ON → NETWORK_SWITCH/HIGH
Dell MD3200BKP .56/.57 → 1 STORAGE com MGMT + MGMT-2
Dell ME4024/ME5024 → STORAGE com identidade forte
preflight global → PASS
IMPORT normal → PASS
MAC RECONCILE de Devices → PASS
recuperação após falha parcial → PASS
reparo seguro de Device duplicado de VM → PASS
idempotência pós-reparo → PASS
```

## APPLY real da 1.10.18 — 29/07/2026, Site DCM

### Plano anterior à escrita

```text
Versão: 1.10.18
Planner: 4.7-product
Pipeline: 2.8-product
READY/CREATE: 0
READY/UPDATE_SAFE: 0
READY/REPAIR_SAFE: 1
DELEGATED/HYPERVISOR: 42
REVIEW: 1
BLOCKED: 0
```

### Reparo SRV-AE11

```text
Device duplicado: ID 324
VM correta: ID 359
VM interface existente após recuperação: ID 533
IP transferido: 10.1.1.111/24
PREFLIGHT GLOBAL FINALIZE: OK
Reparos seguros concluídos: 1
Erros: 0
```

A ordem corrigida foi validada ao vivo:

```text
limpar primary/oob do Device antigo
→ mover IP para virtualization.vminterface
→ definir primary IPv4 da VM
→ remover somente o Device duplicado
```

### Evidência de remoção segura

```text
Devices no Site antes: 14
Devices no Site após: 13
VM ID 359 preservada
interface ID 533 preservada
MAC VMware preservado
Device ID 324 removido
```

### IMPORT normal e MAC reconcile

```text
Assets READY normais processados: 13/13
Runtime blocked: 0
Erros: 0
MAC RECONCILE: PASS
```

### Idempotência posterior

```text
READY/CREATE: 0
READY/UPDATE_SAFE: 0
READY/NOOP: 13
BLOCKED: 0
```

O `SRV-AE11` deixou de aparecer como conflito/reparo pendente. O IP agora possui ownership da camada Hypervisor.

### AUDIT FINALIZE

```text
Status: PASS_WITH_WARNINGS
Assets PASS: 9
Assets WARN: 5
Assets FAIL: 0
Checks PASS: 161
Checks WARN: 9
Checks FAIL: 0
```

Warnings conhecidos e não destrutivos:

```text
NAME_PRESERVED nos hosts VMware
Dell Inc. versus Dell no fabricante/modelo esperado
nome live ME4024-10-1-1-52 preservado
```

Esses warnings não representam falha de ownership, IP, interface, MAC, criação, remoção ou idempotência.

## REVIEW residual

```text
10.1.1.54
confidence=NONE
role=UNKNOWN
```

O asset permanece `REVIEW`, sem escrita automática e sem impedir a homologação do ciclo seguro. Não deve ser forçado sem identidade forte.

## Resultado final Network

```text
DISCOVER → PASS
CLASSIFY V5 → PASS
RECONCILE V5 → PASS
PLAN V7 → PASS
PREFLIGHT GLOBAL FINALIZE → PASS
IMPORT normal → PASS
MAC RECONCILE → PASS
REPAIR_SAFE → PASS
AUDIT FINALIZE → PASS_WITH_WARNINGS
IDEMPOTÊNCIA → PASS
```

**Conclusão:** ciclo Network do Site DCM homologado como **LIVE PASS**.

## Schedulers

```text
Auto-update stable: LIVE PASS
Network scheduler: DISABLED
Hypervisor scheduler: DISABLED
```

A habilitação dos schedulers é uma decisão operacional separada da homologação funcional.
