## V1.10.13 — Preserve authoritative Hypervisor IP delegation

Hotfix criada a partir do dry-run live da 1.10.12 no DCM.

### Evidência live que motivou a correção

A 1.10.12 corrigiu o caso `SRV-AE11` e comprovou a ponte por nome:

```text
BLOCKED | 10.1.1.111 | SRV-AE11
PHYSICAL_DEVICE_CONFLICT_WITH_HYPERVISOR_VM:359
```

Porém, seis assets que já tinham ownership Hypervisor provado por IP foram rebaixados para `REVIEW` porque a ponte por nome não encontrou VM nominal:

```text
10.1.1.20  vcsa
10.1.1.155 pagamento
10.1.1.170 unifi
10.1.1.200 FAZ-MIZU
10.1.1.202 FMG-DCM
10.1.1.230 LINUX_HOST-10-1-1-230
```

Todos mostravam simultaneamente:

```text
OWNED_BY_HYPERVISOR_VM
Match: EXTERNAL_MANAGED
IP(s) já vinculado(s) a virtualization.vminterface
```

Mas a decisão final ficou incorretamente `REVIEW` com `VIRTUAL_MACHINE_CANDIDATE_NO_VM_MATCH`.

### Correção

O `planner_v3` passa a tratar a decisão base `DELEGATED` como autoritativa:

```text
IP ownership já provado
→ DELEGATED/NOOP
→ name bridge não pode rebaixar a decisão
```

A correlação por nome continua ativa apenas para acrescentar ownership quando o IP ainda não o provou.

### Segurança preservada

O caso Device físico + VM única por nome continua bloqueado:

```text
SRV-AE11-like
→ BLOCKED/CONFLICT
→ PHYSICAL_DEVICE_CONFLICT_WITH_HYPERVISOR_VM:<id>
```

Nenhuma remoção automática é introduzida.

### Regressões

- `DELEGATED` por IP não pode virar `REVIEW` por ausência de name match;
- conflito físico/VM por nome continua `BLOCKED`.

Estado inicial: **CI/NOT LIVE até novo dry-run real**.

---

## V1.10.12 — Identity anti-flap + VM ownership by name

Release criada a partir do primeiro APPLY Network real do DCM em 28/07/2026.

### Primeiro APPLY Network

```text
PREFLIGHT: OK
Assets READY processados: 13
Runtime blocked: 0
Erros: 0
NetBox write: SIM
```

Idempotency preview:

```text
READY/CREATE: 0
READY/UPDATE_SAFE: 0
READY/NOOP: 13
```

AUDIT:

```text
PASS_WITH_WARNINGS
Assets FAIL: 0
Checks FAIL: 0
```

### Safety finding

`SRV-AE11` havia sido observado como:

```text
management_mac=00:50:56:9F:9E:70
asset_class=VIRTUAL_MACHINE_CANDIDATE
```

No APPLY seguinte o MAC não foi coletado. A classificação caiu para host genérico e o asset ficou `READY/CREATE`, criando um `dcim.device` físico.

O mesmo tipo de flapping ocorreu na leitura FA-MIB de controladoras PowerVault: uma execução tinha identidade do array e outra não.

### Identidade anti-flap

A 1.10.12 guarda por até 48 horas apenas identidade forte já observada no mesmo Site/IP:

- VMware OUI / `VIRTUAL_MACHINE_CANDIDATE`;
- storage com serial e/ou `connUnitId` válido.

Regras:

- identidade física forte atual vence histórico VMware;
- serial/FA atual divergente gera conflito;
- MAC antigo não é copiado para criar interface;
- ausência transitória não apaga identidade forte.

### VM ownership por nome único

O planner agora consulta VMs do mesmo Tenant/Site.

```text
VM candidate + VM única com mesmo nome
→ DELEGATED/NOOP
```

Se já existir Device físico:

```text
→ BLOCKED/CONFLICT
→ PHYSICAL_DEVICE_CONFLICT_WITH_HYPERVISOR_VM:<id>
```

### PowerVault

- até três tentativas read-only da árvore FA-MIB;
- `connUnitId=000...000` é tratado como ausente;
- serial válido ainda classifica STORAGE/HIGH;
- histórico forte pode restaurar identidade quando uma controladora falha temporariamente na leitura.

### IMPORT/AUDIT

- runner passa a usar `network_v3.py`, `classifier_v4.py`, `planner_v3.py`, `importer_v3.py`, `auditor_v3.py`;
- IMPORT recalcula obrigatoriamente o PLAN V3 antes da escrita;
- AUDIT usa PLAN V3 no preview de idempotência;
- WARN/FAIL do AUDIT aparecem no terminal.

### Segurança

Nenhuma remoção automática do Device criado incorretamente é feita nesta release. Primeiro o produto deve provar ownership Hypervisor ao vivo e bloquear o conflito.

Estado após dry-run live: ponte por nome/conflito físico comprovada; anti-flap específico ainda LIVE PARTIAL.

---

## V1.10.11 — PowerVault / FibreAlliance storage identity

Adicionou leitura FCMGMT/FibreAlliance `.1.3.6.1.3.94.1.6.1`, classificação `STORAGE/HIGH` e reconciliação por serial/`connUnitId`.

Evidência live parcial:

```text
ME4024 → DELL EMC ME4024 / serial real / FA ID real
ME5024 → DELL EMC ME5024 / serial real / FA ID real
```

A leitura mostrou flapping entre controladoras/executações, motivo da 1.10.12.

---

## V1.10.10 — Ownership Network/Hypervisor + Dell Networking

Validação live:

```text
DELEGATED/HYPERVISOR: 41
N2024      → NETWORK_SWITCH/HIGH
PCT7024    → NETWORK_SWITCH/HIGH
S4128F-ON  → NETWORK_SWITCH/HIGH
```

Estado: LIVE PASS no dry-run dessas funções.

---

## V1.10.9 — Diagnóstico automático do PLAN Network

Adicionou diagnóstico completo no terminal para READY, REVIEW, BLOCKED, motivos, matching, SNMP e evidência CLASSIFY.

Baseline:

```text
READY: 7
REVIEW: 47
BLOCKED: 6
```

---

## V1.10.8 — VM acompanha Tenant/Site do Host/Cluster

Hypervisor multi-contexto concluído ao vivo:

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

Migração coordenada de Cluster/Hosts e compare oficial. Estado: LIVE PASS.

---

## V1.10.6 — Preflight global Hypervisor

Recalcula PLAN e revalida identidade antes da primeira escrita. Estado: LIVE PASS.
