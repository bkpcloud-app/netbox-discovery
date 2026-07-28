## V1.10.15 — Historical VMware repair + preserved-interface MAC reconcile

Release criada a partir do APPLY live da 1.10.14 no DCM.

### Evidência live

O MD3200BKP foi criado corretamente como um único STORAGE com dois IPs, o preflight global passou e o IMPORT normal concluiu sem erros.

Duas lacunas reais permaneceram:

```text
SRV-AE11
→ historical_vmware_mac estava presente
→ PLAN V4 avaliou somente asset.macs atual
→ REPAIR_SAFE não foi elegível

ME5024
→ IP/interface existentes foram preservados
→ ensure_mac não foi chamado nesse caminho
→ AUDIT: MAC_MISSING 00:C0:FF:66:B4:BF
```

### PLAN V5

O `historical_vmware_mac` do anti-flap pode participar do gate de reparo quando:

- o asset continua `VIRTUAL_MACHINE_CANDIDATE`;
- o valor pertence a um OUI VMware conhecido;
- existe uma única VM pelo nome;
- o MAC corresponde exatamente a uma interface live dessa VM;
- todas as proteções de ownership do Device duplicado continuam válidas.

O histórico não autoriza reparo sem confirmação live.

### Preflight de MAC

Antes da primeira escrita, todos os MACs esperados dos READY normais são verificados na tabela global.

```text
MAC ausente ou sem vínculo → permitido
MAC na interface correta  → permitido
MAC duplicado              → bloqueia
MAC em outra interface/VM  → bloqueia
```

### MAC RECONCILE

Após o IMPORT normal e antes do REPAIR_SAFE:

```text
IP único em dcim.interface
→ confirma Device esperado
→ cria/atribui MAC esperado
→ garante primary_mac_address
```

Relatório próprio:

```text
<SITE>-mac-reconcile-*.json
```

### Componentes

```text
planner_v5.py       4.5-product
importer_v5.py      5.3-product
auditor_v5.py       6.3-product
pipeline            2.6-product
runner              2.4-product
```

Estado inicial: **CI/NOT LIVE até a única execução final `netbox-discovery run --apply`**.

---

## V1.10.14 — One-pass Network finalization

Release criada para concluir em uma única execução as pendências Network remanescentes do DCM.

### Escopo

```text
Dell MD3200BKP com dois endpoints/controladoras
+ Device físico duplicado de uma VM criado anteriormente pelo próprio produto
+ Web Appliance residual mantido em REVIEW se continuar sem identidade forte
```

### Dell PowerVault MD32xx

Classificação explícita pelo `sysObjectID`:

```text
.1.3.6.1.4.1.674.10893.2.31
```

A reconciliação automática exige exatamente dois endpoints, mesmo `sysObjectID`, mesmo `sysName` não genérico, `STORAGE/HIGH`, IPs consecutivos e ausência de serial conflitante.

Resultado planejado:

```text
1 Device STORAGE
├─ MGMT
└─ MGMT-2
```

Nome igual isolado não autoriza merge.

### REPAIR_SAFE_VM_DUPLICATE

Novo action:

```text
READY / REPAIR_SAFE_VM_DUPLICATE
```

Elegibilidade exige ownership completo do `netbox-discovery` no Device, interface e IP, além de VM/interface únicas, MAC VMware forte, ausência de serial, rack, location, cluster, cabos e objetos relacionados.

Ação:

```text
move IP para virtualization.vminterface
→ define primary IPv4 da VM se vazio
→ remove MACs do Device criados pelo produto
→ remove somente o Device duplicado criado pelo produto
```

Nenhuma VM é removida e não existe DELETE genérico.

### Preflight global e journal

Antes da primeira escrita:

```text
PREFLIGHT GLOBAL FINALIZE
→ valida READY normal
→ valida REPAIR_SAFE
→ relê relações live
→ cria REPAIR_JOURNAL
→ somente então escreve
```

Falha em qualquer proteção bloqueia tudo antes da etapa final.

### Ordem e recuperação

O IMPORT normal executa antes do reparo destrutivo. Cada reparo é revalidado novamente imediatamente antes da ação.

Se uma falha ocorrer após o IP já ter sido movido:

```text
RECOVERY_AFTER_IP_MOVE
```

Uma nova execução pode concluir somente a limpeza segura restante após novo preflight.

### Audit combinado

O `auditor_v4` valida READY normais e MD32xx, Device duplicado removido, IP na VM interface correta, primary IPv4 e idempotência `DELEGATED/NOOP`.

### Componentes

```text
classifier_v5.py
reconciler_v5.py
planner_v4.py
importer_v4.py
auditor_v4.py
pipeline 2.5-product
runner 2.3-product
```

Validação live parcial: MD32xx, preflight global e IMPORT normal passaram; findings corrigidos na 1.10.15.

---

## V1.10.13 — Preserve authoritative Hypervisor IP delegation

Corrige a precedência de ownership:

```text
IP já vinculado a virtualization.vminterface
→ DELEGATED/NOOP
→ ponte por nome não pode rebaixar para REVIEW
```

Validação live: `42 DELEGATED`, incluindo appliances sem correspondência nominal, e `READY/CREATE=0`.

---

## V1.10.12 — Identity anti-flap + VM ownership by name

Adicionou retenção conservadora de identidade VMware/FA-MIB por até 48 horas, correlação por nome único e bloqueio de Device físico + VM.

Evidência live:

```text
SRV-AE11
→ PHYSICAL_DEVICE_CONFLICT_WITH_HYPERVISOR_VM
```

Também adicionou retry read-only de FA-MIB, tratamento de `connUnitId=000...000` e audit detalhado.

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
