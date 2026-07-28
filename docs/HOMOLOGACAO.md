# netbox-discovery 1.10.13 — Matriz de Homologação

## Estados

```text
LIVE PASS     = validado ao vivo com evidência
LIVE PARTIAL  = parte relevante validada, fluxo completo pendente
CI PASS       = regressões automatizadas passaram
NOT LIVE      = ainda não validado ao vivo
```

CI PASS não equivale a LIVE PASS.

## Hypervisor — estado de referência

**Estado:** LIVE PASS.

```text
Objetos comparados: 282
OK: 282
MISMATCH: 0
MISSING: 0
AMBIGUOUS: 0
CLUSTER: OK=2
HOST: OK=22
PREFIX: OK=12
VM: OK=246
COMPARE STATUS: OK
```

## Network DCM — baseline 1.10.9

```text
Hosts ativos: 64
Assets reconciliados: 60
READY: 7
REVIEW: 47
BLOCKED: 6
NetBox write: NÃO
```

## 1.10.10 — ownership Network/Hypervisor por IP

**Estado:** LIVE PASS.

O dry-run real de 28/07/2026 confirmou que IP já atribuído a `virtualization.vminterface` vira `DELEGATED/NOOP`.

## 1.10.10 — Dell Network Switch

**Estado:** LIVE PASS.

```text
10.1.1.31 SW-DCM-SERVERS Dell N2024      → NETWORK_SWITCH/HIGH
10.1.1.38 SW_LINKS       Dell PCT7024    → NETWORK_SWITCH/HIGH
10.1.1.50 SW-SAN-AE1     Dell S4128F-ON  → NETWORK_SWITCH/HIGH
10.1.1.51 SW-SAN-AE2     Dell S4128F-ON  → NETWORK_SWITCH/HIGH
```

## 1.10.11 — PowerVault / FA-MIB

**Estado:** LIVE PARTIAL.

Evidência real:

```text
ME4024 10.1.1.52
role=STORAGE/HIGH
product=DELL EMC ME4024
serial=CN0PJ27VFCG0091F01VNA00
connUnitId=208000C0FFF069900000000000000000

ME5024 10.1.1.55
role=STORAGE/HIGH
product=DELL EMC ME5024
serial=SGFTJ22265E8428
connUnitId=208000C0FF5E84280000000000000000
```

A leitura FA-MIB variou entre controladoras/executações, portanto a reconciliação multi-controladora permanece em homologação.

## Primeiro APPLY Network real — 1.10.11

**Estado:** LIVE PARTIAL.

```text
PREFLIGHT: OK
Assets READY processados: 13
Runtime blocked: 0
Erros: 0
NetBox write: SIM
```

AUDIT:

```text
Status: PASS_WITH_WARNINGS
Assets PASS: 9
Assets WARN: 4
Assets FAIL: 0
Checks FAIL: 0
```

Idempotency preview:

```text
READY/CREATE: 0
READY/UPDATE_SAFE: 0
READY/NOOP: 13
```

O APPLY também revelou que `SRV-AE11` foi criado como Device físico após uma coleta deixar de observar o MAC VMware.

## 1.10.12 — identidade anti-flap

**Estado:** LIVE PARTIAL.

A implementação existe e possui CI PASS. O dry-run posterior voltou a observar o MAC VMware de `SRV-AE11`, então ainda não houve uma segunda execução live com o MAC ausente para provar especificamente a retenção histórica.

## 1.10.12 — ownership VM por nome único / conflito físico

**Estado:** LIVE PASS para o conflito físico/VM e para delegação por nome.

Dry-run real em 28/07/2026:

```text
BLOCKED | 10.1.1.111 | SRV-AE11
PHYSICAL_DEVICE_CONFLICT_WITH_HYPERVISOR_VM:359
Device físico existe, mas identidade VMware corresponde à VM ID 359
```

Também houve delegações reais por nome único, por exemplo:

```text
10.1.1.3   SRV-AE01  → VM ID 317
10.1.1.168 SRV-GEP11 → VM ID 336
```

Isso comprova que a ponte por nome acrescenta ownership quando o match é inequívoco e bloqueia o caso Device físico + VM.

## 1.10.12 — regressão encontrada no mesmo dry-run

**Estado:** FAIL funcional específico, sem escrita porque o teste foi dry-run.

Seis assets já tinham ownership por IP provado (`match_state=EXTERNAL_MANAGED`, IP vinculado a `virtualization.vminterface`) mas foram rebaixados de `DELEGATED` para `REVIEW` pela ponte de nome quando não houve match nominal:

```text
10.1.1.20  vcsa
10.1.1.155 pagamento
10.1.1.170 unifi
10.1.1.200 FAZ-MIZU
10.1.1.202 FMG-DCM
10.1.1.230 LINUX_HOST-10-1-1-230
```

Sintoma:

```text
Motivos: OWNED_BY_HYPERVISOR_VM, VIRTUAL_MACHINE_CANDIDATE_NO_VM_MATCH
Match: EXTERNAL_MANAGED | IP(s) já vinculado(s) a virtualization.vminterface
Decisão final incorreta: REVIEW
```

Diagnóstico: o `planner_v3` reaplicava a lógica de name bridge sobre uma decisão `DELEGATED` já autoritativa do planner base.

## 1.10.13 — precedência de ownership por IP

**Estado:** NOT LIVE até update + novo dry-run.

Regra corrigida:

```text
se decisão base == DELEGATED por ownership de IP
→ preservar DELEGATED/NOOP
→ não executar name bridge para rebaixar a decisão
```

A ponte por nome continua funcionando para assets sem ownership IP já provado, e o conflito `SRV-AE11` continua `BLOCKED`.

Regressões automatizadas cobrem:

- IP-owned `DELEGATED` não pode virar `REVIEW` sem match de nome;
- `SRV-AE11`-like Device físico + VM por nome continua `BLOCKED/CONFLICT`.

## Próxima validação live

```text
1. CI PASS 1.10.13
2. publicar stable
3. update no SNOC-AGL-DCM
4. netbox-discovery run   # somente dry-run
5. confirmar os 6 assets acima novamente DELEGATED
6. confirmar SRV-AE11 continua BLOCKED
7. READY/CREATE deve permanecer 0
8. revisar storage residual
9. não executar --apply nessa validação
```

## Schedulers

```text
Auto-update stable: LIVE PASS
Network scheduler: DISABLED durante homologação
Hypervisor scheduler: DISABLED durante homologação
```
