## V1.10.17 — Create missing VM interface during safe duplicate repair

Release criada a partir do APPLY live da 1.10.16 no DCM.

### Evidência live da 1.10.16

```text
Planner: 4.6-product
READY/REPAIR_SAFE: 0
SRV-AE11 → BLOCKED
VM única: ID 359
MAC VMware: 00:50:56:9F:9E:70
Interfaces cadastradas na VM: 0
```

A 1.10.16 bloqueou corretamente:

```text
REPAIR_SAFE_NOT_ELIGIBLE:
Fallback de interface única exige exatamente uma interface na VM: 0
```

O conjunto normal permaneceu saudável:

```text
PREFLIGHT GLOBAL FINALIZE: OK
MAC RECONCILE: PASS
Assets FAIL: 0
Checks FAIL: 0
Status: PASS_WITH_WARNINGS
```

### PLAN V7

Adiciona um terceiro caminho estritamente protegido para `REPAIR_SAFE_VM_DUPLICATE`:

```text
VM única por nome
+ zero virtualization.vminterface
+ exatamente um MAC VMware forte
+ MAC ausente ou sem vínculo
+ MAC não duplicado e sem outro owner
+ Device/IP/interfaces integralmente criados pelo produto
→ READY/REPAIR_SAFE_VM_DUPLICATE
```

O plano registra:

```text
vm_interface_mode=CREATE_SINGLE_VM_INTERFACE
vm_interface_name=MGMT
vm_mac_mode=ENSURE_CREATED_VM_INTERFACE
```

### Importer V7

Antes de qualquer escrita destrutiva, o importer revalida:

- Device, Tenant/Site e ownership do produto;
- ausência de serial, rack, location, cluster e objetos relacionados;
- interfaces físicas e IP ainda inalterados;
- VM ainda sem interfaces;
- MAC VMware ainda único e sem outro proprietário;
- VM ainda sem outro primary IPv4.

Depois executa:

```text
cria virtualization.vminterface MGMT
→ cria/atribui MAC VMware
→ define primary_mac_address
→ move o IP para a nova interface
→ define primary IPv4 da VM se vazio
→ remove somente o Device duplicado criado pelo produto
```

A VM nunca é removida.

### Recuperação

Falhas parciais convergem de forma segura:

```text
interface criada sem MAC
→ fallback de interface única na próxima execução

interface + MAC criados, IP ainda no Device
→ REPAIR_SAFE normal

IP já movido
→ RECOVERY_AFTER_IP_MOVE
```

### Auditor V7

Adiciona validações específicas:

```text
REPAIR_VM_INTERFACE_CREATED_OK
REPAIR_VM_MAC_OK
REPAIR_DUPLICATE_DEVICE_REMOVED
REPAIR_IP_ON_VM
REPAIR_VM_PRIMARY_IP_OK
REPAIR_IDEMPOTENCY_DELEGATED
```

### Componentes

```text
planner_v7.py       4.7-product
importer_v7.py      5.5-product
auditor_v7.py       6.5-product
pipeline            2.8-product
runner              2.6-product
```

Estado inicial: **CI/NOT LIVE até a única execução final `netbox-discovery run --apply`**.

---

## V1.10.16 — Single-interface VM MAC bootstrap before safe repair

Release criada a partir do APPLY live da 1.10.15 no DCM.

### Evidência anterior

```text
VM única ID 359
MAC VMware forte 00:50:56:9F:9E:70
Interface da VM por MAC não é única: 0
```

O PLAN V6 adicionou fallback para:

```text
VM única por nome
+ exatamente uma interface live
+ interface sem outro MAC
+ exatamente um MAC VMware forte
+ MAC não duplicado e sem outro owner
→ READY/REPAIR_SAFE_VM_DUPLICATE
```

A validação live mostrou que a VM possuía zero interfaces, não uma. O produto permaneceu `BLOCKED`, sem escrita destrutiva. Esse cenário foi tratado na 1.10.17.

---

## V1.10.15 — Historical VMware repair + preserved-interface MAC reconcile

Release criada a partir do APPLY live da 1.10.14 no DCM.

### Lacunas tratadas

```text
SRV-AE11
→ historical_vmware_mac estava presente
→ PLAN anterior avaliava somente asset.macs atual

ME5024
→ IP/interface existentes foram preservados
→ ensure_mac não foi chamado nesse caminho
→ AUDIT: MAC_MISSING 00:C0:FF:66:B4:BF
```

Após o IMPORT normal:

```text
IP único em dcim.interface
→ confirma Device esperado
→ cria/atribui MAC esperado
→ garante primary_mac_address
```

Validação live:

```text
MAC RECONCILE: PASS
Assets FAIL: 0
Checks FAIL: 0
```

---

## V1.10.14 — One-pass Network finalization

Adicionou:

- classificação e reconciliação do Dell PowerVault MD32xx com duas controladoras;
- `REPAIR_SAFE_VM_DUPLICATE`;
- preflight global e `REPAIR_JOURNAL`;
- recuperação `RECOVERY_AFTER_IP_MOVE`;
- audit combinado.

Validação live:

```text
MD3200BKP .56/.57 → 1 STORAGE com MGMT + MGMT-2
PREFLIGHT GLOBAL FINALIZE: OK
IMPORT normal: 12/12, erros=0
```

---

## V1.10.13 — Preserve authoritative Hypervisor IP delegation

```text
IP já vinculado a virtualization.vminterface
→ DELEGATED/NOOP
→ ponte por nome não pode rebaixar para REVIEW
```

Validação live: `42 DELEGATED` e `READY/CREATE=0`.

---

## V1.10.12 — Identity anti-flap + VM ownership by name

Adicionou retenção conservadora de identidade VMware/FA-MIB por até 48 horas, correlação por nome único e bloqueio de Device físico + VM.

---

## V1.10.11 — PowerVault / FibreAlliance storage identity

Adicionou leitura FCMGMT/FibreAlliance, classificação `STORAGE/HIGH` e reconciliação por serial/`connUnitId` válido.

---

## V1.10.10 — Ownership Network/Hypervisor + Dell Networking

Validação live:

```text
DELEGATED/HYPERVISOR: 41
N2024      → NETWORK_SWITCH/HIGH
PCT7024    → NETWORK_SWITCH/HIGH
S4128F-ON  → NETWORK_SWITCH/HIGH
```

---

## V1.10.9 — Diagnóstico automático do PLAN Network

Adicionou diagnóstico completo no terminal para READY, REVIEW, BLOCKED, matching, SNMP e evidências.

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
