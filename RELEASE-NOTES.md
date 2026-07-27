## V1.10.10 — Ownership Network/Hypervisor + Dell Networking

Release criada a partir do diagnóstico live da 1.10.9 no DCM.

### Causa principal dos REVIEW Network

Grande parte dos assets descobertos na rede já eram VMs inventariadas pelo pipeline Hypervisor. O NetBox já tinha seus IPs atribuídos a:

```text
virtualization.vminterface
```

A política anterior marcava isso como `REVIEW` porque o Network corretamente se recusava a transformar o IP em um Device físico, mas ainda tratava a situação como pendência.

### Nova decisão DELEGATED

```text
IP(s) já pertencem a virtualization.vminterface
→ DELEGATED
→ NOOP
→ OWNED_BY_HYPERVISOR_VM
```

`DELEGATED` não entra no IMPORT Network. Apenas `READY` continua elegível para escrita.

### Proteção contra VM criada como Device físico

Asset com identidade virtual/VMware mas sem VM correspondente no NetBox:

```text
REVIEW
VIRTUAL_MACHINE_CANDIDATE_NO_VM_MATCH
```

Isso evita que uma lacuna do Hypervisor vire um `dcim.device` incorreto.

### Dell Networking

O classificador agora prioriza modelo de hardware/ENTITY-MIB Dell Networking antes de fingerprints genéricos Linux/SSH/Web/SNMP.

Regressões:

```text
N2024      → NETWORK_SWITCH / HIGH
PCT7024    → NETWORK_SWITCH / HIGH
S4128F-ON  → NETWORK_SWITCH / HIGH
```

A regra usa famílias de modelo, não IP/hostname/Site específicos.

### Observabilidade

O Network PLAN passa a exibir:

```text
DELEGATED/HYPERVISOR: N
NETWORK DELEGADOS AO HYPERVISOR
```

READY agora também mostra asset class, SNMP e evidência CLASSIFY para facilitar a revisão antes do APPLY.

### Segurança

- `DELEGATED` nunca escreve;
- `REVIEW`/`BLOCKED` continuam sem escrita;
- apenas `READY` é importado;
- não existe criação física para IP já pertencente a VM;
- storage duplicado/controladoras não foram auto-resolvidos nesta release.

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
