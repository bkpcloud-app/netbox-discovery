# netbox-discovery 1.10.15 — Matriz de Homologação

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

## Network — funções já LIVE PASS

```text
ownership por IP → DELEGATED
Dell N2024/PCT7024/S4128F-ON → NETWORK_SWITCH/HIGH
VM por nome único → DELEGATED
Device físico + VM → BLOCKED
precedência de ownership por IP → DELEGATED preservado
```

## APPLY real da 1.10.14

O usuário executou uma única operação completa em 28/07/2026.

### Discovery e plano

```text
Hosts ativos: 62
Assets reconciliados: 55
READY: 12
DELEGATED: 41
REVIEW: 1
BLOCKED: 1
```

### Dell MD3200BKP

**Estado:** LIVE PASS.

```text
READY/CREATE: 1
10.1.1.56 + 10.1.1.57
role=STORAGE
model=PowerVault MD32xx
```

O IMPORT criou o asset e o PLAN posterior mostrou:

```text
READY/CREATE: 0
READY/NOOP: 12
```

### Preflight global e IMPORT normal

**Estado:** LIVE PASS.

```text
PREFLIGHT GLOBAL FINALIZE: OK
NetBox write até aqui: NÃO
Assets READY processados: 12
Runtime blocked: 0
Erros: 0
NetBox write: SIM
```

### Web Appliance residual

**Estado:** esperado/seguro.

```text
10.1.1.54
REVIEW
CONFIDENCE_NONE + UNKNOWN_ROLE
```

Não bloqueia READY seguros.

## Findings live que motivaram a 1.10.15

### SRV-AE11

A identidade histórica foi preservada corretamente:

```text
asset_class=VIRTUAL_MACHINE_CANDIDATE
historical_vmware_mac=00:50:56:9F:9E:70
VM única ID 359
```

Porém, o PLAN V4 avaliou apenas `asset.macs` atual e ignorou `historical_vmware_mac`:

```text
REPAIR_SAFE_NOT_ELIGIBLE: Asset sem MAC VMware forte
```

**1.10.15:** o MAC histórico pode entrar no gate somente se for OUI VMware e corresponder exatamente a uma interface live da VM única.

### ME5024

O IMPORT preservou IP/interface existente, mas esse caminho não executou `ensure_mac`.

AUDIT live:

```text
FAIL | MAC_MISSING | ME5024 | 00:C0:FF:66:B4:BF
```

**1.10.15:** adiciona `MAC RECONCILE` após o IMPORT normal e preflight de ownership de MAC antes da primeira escrita.

## 1.10.15 — estado por função

| Função | Estado |
|---|---|
| Historical VMware MAC no REPAIR_SAFE | CI/NOT LIVE |
| Preflight global de ownership MAC | CI/NOT LIVE |
| MAC RECONCILE em interface preservada | CI/NOT LIVE |
| Auditor usando PLAN V5 | CI/NOT LIVE |
| MD32xx | LIVE PASS |
| IMPORT normal | LIVE PASS |
| Preflight global base | LIVE PASS |

## Única validação live prevista para 1.10.15

```bash
netbox-discovery update run
netbox-discovery version
netbox-discovery run --apply
```

Critério de conclusão:

```text
READY/REPAIR_SAFE: 1 para SRV-AE11
MAC RECONCILE: PASS
REPAIR_SAFE concluído
Device duplicado removido
IP 10.1.1.111 na VM ID 359
ME5024 MAC_OK
Web Appliance fraco permanece REVIEW se não houver nova evidência
AUDIT FINALIZE: PASS ou PASS_WITH_WARNINGS sem FAIL
novo PLAN sem CREATE/UPDATE/REPAIR pendente
```

Não haverá sequência separada de microtestes.

## Schedulers

```text
Auto-update stable: LIVE PASS
Network scheduler: DISABLED durante homologação
Hypervisor scheduler: DISABLED durante homologação
```
