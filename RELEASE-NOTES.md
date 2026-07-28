## V1.10.18 — Clear parent primary IP before VM reassignment

Release criada a partir do APPLY live da 1.10.17 no DCM.

### Evidência live da 1.10.17

```text
READY/REPAIR_SAFE: 1
VM interface MGMT criada na VM ID 359
MAC 00:50:56:9F:9E:70 criado/atribuído
PREFLIGHT GLOBAL FINALIZE: OK
IMPORT normal: 12/12
MAC RECONCILE: PASS
```

O NetBox bloqueou a transferência do IP:

```text
Cannot reassign IP address while it is designated as the primary IP for the parent object
```

Nenhum Device foi removido. A VM, a interface e o MAC foram preservados. O IP e o Device permaneceram no estado anterior.

### Importer V8

Corrige a ordem de operação do `REPAIR_SAFE_VM_DUPLICATE`:

```text
revalidar reparo
→ validar primary_ip4/primary_ip6/oob_ip do Device
→ limpar referências que apontam para o IP alvo
→ mover o IP para virtualization.vminterface
→ definir primary IPv4 da VM
→ remover somente o Device duplicado criado pelo produto
```

Se qualquer primary/oob apontar para outro IP, bloqueia antes do IP move e antes do DELETE.

### Recuperação do estado parcial

A interface `MGMT` e o MAC criados pela 1.10.17 são reutilizados. A 1.10.18 não cria uma segunda interface.

### Regressões

- NetBox simulado rejeita reassignment enquanto o Device ainda tem primary IP;
- importer V8 limpa o primary antes do PATCH do IP;
- ordem validada: `Device primary clear → IP move → Device delete`;
- primary apontando para outro IP bloqueia sem qualquer escrita.

### Componentes

```text
planner_v7.py       4.7-product
importer_v8.py      5.6-product
auditor_v7.py       6.5-product
pipeline            2.8-product
runner              2.7-product
```

Estado inicial: **CI/NOT LIVE até a única execução final `netbox-discovery run --apply`**.

---

## V1.10.17 — Create missing VM interface during safe duplicate repair

Adicionou criação protegida de `virtualization.vminterface MGMT` para VM inequívoca com zero interfaces e um único MAC VMware forte.

Validação live parcial:

```text
interface MGMT criada
MAC VMware criado/atribuído
IP move bloqueado porque o IP ainda era primary do Device
Device preservado
```

---

## V1.10.16 — Single-interface VM MAC bootstrap

Adicionou fallback para VM única com exatamente uma interface sem MAC.

---

## V1.10.15 — Historical VMware repair + MAC reconcile

Adicionou uso conservador de MAC VMware histórico e reconciliação de MAC em interfaces físicas preservadas.

---

## V1.10.14 — One-pass Network finalization

Adicionou MD32xx, `REPAIR_SAFE_VM_DUPLICATE`, preflight global, journal, recuperação parcial e audit combinado.

---

## V1.10.13 — Preserve authoritative Hypervisor IP delegation

IP em `virtualization.vminterface` permanece `DELEGATED/NOOP`.

---

## V1.10.12 — Identity anti-flap + VM ownership by name

Retenção conservadora de identidade VMware/storage e correlação por VM única.

---

## V1.10.11 — PowerVault / FibreAlliance storage identity

Leitura FA-MIB e reconciliação de storage por identidade forte.

---

## V1.10.10 — Ownership Network/Hypervisor + Dell Networking

Classificação Dell N2024/PCT7024/S4128F-ON e delegação Hypervisor.

---

## V1.10.9 — Diagnóstico automático do PLAN Network

Diagnóstico detalhado de READY, DELEGATED, REVIEW e BLOCKED.
