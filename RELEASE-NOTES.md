## V1.10.11 — PowerVault / FibreAlliance storage identity

Release criada a partir do resíduo live do Network DCM após a 1.10.10.

### Evidência que motivou a mudança

Depois de delegar 41 VMs ao Hypervisor e corrigir Dell switches, restaram storages/controladoras como:

```text
10.1.1.52 / .53 → ME4024
10.1.1.55       → ME5024
10.1.1.56 / .57 → MD3200BKP
10.1.1.58 / .59 → ME4012
```

Os pares tinham o mesmo `sysName`, mas MACs de gerenciamento diferentes. Nome igual não é evidência suficiente para fundir assets.

### Nova identidade FibreAlliance

O discovery passa a consultar FCMGMT/FibreAlliance:

```text
.1.3.6.1.3.94.1.6.1
```

Campos utilizados:

```text
connUnitId
connUnitType
connUnitProduct
connUnitSn
connUnitName
connUnitVendorId
```

Quando `connUnitType=storage-subsystem(11)` e existe `connUnitId` válido, o array passa a ter identidade de storage explícita.

### Reconciliação

```text
mesmo connUnitId → merge forte entre IPs/controladoras
diferente connUnitId → não merge
serial válido → permanece identidade preferencial
sem serial, um connUnitId único → asset_id FA:<id>
```

O SNMP EngineID não é usado como identidade do array.

### Classificação

Storage identificado por FA-MIB:

```text
role=STORAGE
confidence=HIGH
asset_class=PHYSICAL_DEVICE
```

O terminal mostra:

```text
Storage FA-MIB: id=... product=... serial=... type=storage-subsystem(11)
```

### Segurança

- não une controladoras por nome;
- IDs FA diferentes não são fundidos;
- ausência de FA-MIB não relaxa REVIEW/BLOCKED;
- apenas READY continua elegível para IMPORT;
- nenhum APPLY automático foi habilitado.

Estado inicial: **CI/NOT LIVE até novo dry-run real**.

---

## V1.10.10 — Ownership Network/Hypervisor + Dell Networking

Validação live em 28/07/2026:

```text
Hosts ativos: 64
Assets reconciliados: 60
DELEGATED/HYPERVISOR: 41
READY/CREATE: 5
REVIEW: 4
BLOCKED: 6
NetBox write: NÃO
```

Switches Dell validados:

```text
N2024      → NETWORK_SWITCH / HIGH
PCT7024    → NETWORK_SWITCH / HIGH
S4128F-ON  → NETWORK_SWITCH / HIGH
```

VMs já inventariadas pelo Hypervisor passaram para `DELEGATED/NOOP`. VM candidata sem correspondência continua `REVIEW / VIRTUAL_MACHINE_CANDIDATE_NO_VM_MATCH`.

Estado do dry-run dessas funções: **LIVE PASS**.

---

## V1.10.9 — Diagnóstico automático do PLAN Network

Adicionou diagnóstico completo no terminal para READY, REVIEW, BLOCKED, motivos, matching, SNMP e evidência CLASSIFY.

Baseline live DCM:

```text
Hosts ativos: 64
Assets reconciliados: 60
READY: 7
REVIEW: 47
BLOCKED: 6
NetBox write: NÃO
```

---

## V1.10.8 — VM acompanha Tenant/Site do Host/Cluster

Fluxo Hypervisor multi-contexto concluído ao vivo.

```text
Objetos comparados: 282
OK: 282
MISMATCH: 0
MISSING: 0
AMBIGUOUS: 0
COMPARE STATUS: OK
```

Estado: LIVE PASS.

---

## V1.10.7 — Cluster/Site + compare read-only

Migração coordenada de Cluster scoped/Hosts e modo oficial `hypervisor run --compare`.

Estado: LIVE PASS.

---

## V1.10.6 — Preflight global Hypervisor

Recalcula PLAN e revalida identidade antes da primeira escrita.

Estado: LIVE PASS.
