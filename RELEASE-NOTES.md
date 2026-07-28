## V1.10.16 — Single-interface VM MAC bootstrap before safe repair

Release criada a partir do APPLY live da 1.10.15 no DCM.

### Evidência live da 1.10.15

```text
MAC RECONCILE: PASS
Assets FAIL: 0
Checks FAIL: 0
ME5024 MAC_MISSING: resolvido
```

O `SRV-AE11` permaneceu bloqueado:

```text
VM única ID 359
MAC VMware forte 00:50:56:9F:9E:70
Interface da VM por MAC não é única: 0
Reparos seguros concluídos: 0
```

A interface da VM não possuía objeto MAC no NetBox.

### PLAN V6

Adiciona um fallback estritamente limitado:

```text
VM única por nome
+ exatamente uma interface live
+ interface sem outro MAC
+ exatamente um MAC VMware forte
+ MAC não duplicado e sem outro owner
→ READY/REPAIR_SAFE_VM_DUPLICATE
```

VM com múltiplas interfaces, MAC divergente ou MAC pertencente a outro objeto continua `BLOCKED`.

### Importer V6

Antes de mover o IP ou remover o Device duplicado:

```text
cria/atribui o MAC à virtualization.vminterface única
→ define primary_mac_address da interface
→ revalida o reparo
→ move o IP
→ define primary IPv4 da VM se vazio
→ remove somente o Device duplicado criado pelo produto
```

A VM nunca é removida. O MAC é revalidado no preflight global e novamente imediatamente antes da escrita.

### Auditor V6

Além dos checks anteriores, exige:

```text
REPAIR_VM_MAC_OK
```

O MAC deve existir uma única vez, pertencer à interface correta da VM e ser o `primary_mac_address` dessa interface.

### Componentes

```text
planner_v6.py       4.6-product
importer_v6.py      5.4-product
auditor_v6.py       6.4-product
pipeline            2.7-product
runner              2.5-product
```

Estado inicial: **CI/NOT LIVE até a única execução final `netbox-discovery run --apply`**.

---

## V1.10.15 — Historical VMware repair + preserved-interface MAC reconcile

Release criada a partir do APPLY live da 1.10.14 no DCM.

### Lacunas tratadas

```text
SRV-AE11
→ historical_vmware_mac estava presente
→ PLAN V4 avaliava somente asset.macs atual

ME5024
→ IP/interface existentes foram preservados
→ ensure_mac não foi chamado nesse caminho
→ AUDIT: MAC_MISSING 00:C0:FF:66:B4:BF
```

### PLAN V5

O `historical_vmware_mac` pode participar do gate quando é OUI VMware, existe uma única VM por nome, o MAC corresponde exatamente a uma interface live e todas as proteções de ownership continuam válidas.

### Preflight e MAC RECONCILE

```text
MAC ausente ou sem vínculo → permitido
MAC na interface correta  → permitido
MAC duplicado              → bloqueia
MAC em outra interface/VM  → bloqueia
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

O reparo do SRV-AE11 revelou a ausência de MAC na própria interface da VM e foi finalizado na 1.10.16.

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
