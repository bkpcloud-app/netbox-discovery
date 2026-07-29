## V1.10.19 — Identity quality and safe generic enrichment

Release criada a partir do APPLY live da 1.10.18 no FBA.

### Evidência live de origem

```text
Hosts ativos: 288
Assets reconciliados: 283
READY processados: 175/175
Runtime blocked: 0
Erros: 0
MAC RECONCILE: PASS
Assets FAIL: 0
Checks FAIL: 0
Idempotência: READY/CREATE=0, READY/UPDATE_SAFE=0, READY/NOOP=175
```

O FBA ficou operacionalmente consistente, mas expôs qualidade insuficiente em impressoras genéricas, um Moxa NPort não reconhecido, nomes SNMP repetidos e drifts causados por perda transitória de evidência.

### DISCOVER V4

- leitura read-only de Printer-MIB;
- coleta `prtGeneralPrinterName` e `prtGeneralSerialNumber`;
- uso de `hrDeviceDescr` para fabricante/modelo explícitos;
- enriquecimento somente quando Printer-MIB realmente responde.

### CLASSIFY V6

- impressora com Printer-MIB passa a `PRINTER/HIGH`;
- fabricante, modelo e serial explícitos são preservados;
- `sysObjectID .1.3.6.1.4.1.8691.2.7` vira `Moxa / NPort 5210 / INDUSTRIAL_COMMUNICATION / HIGH`.

### PLAN V8

- upgrade automático somente de Device Type genérico criado pelo produto para identidade exata HIGH;
- preservação read-only de identidade live forte quando a observação atual enfraquece;
- aliases de fabricante evitam drift falso, como `Dell Inc.` versus `Dell`;
- colisão de `sysName` entre equipamentos físicos HIGH recebe nome determinístico por serial/MAC;
- identidade fraca, IP conflitante ou objeto manual continuam REVIEW/BLOCKED.

### IMPORT V9

O importer revalida no momento da escrita:

```text
Device criado pelo netbox-discovery
+ tipo atual ainda genérico
+ classificação HIGH
+ fabricante/modelo idênticos ao PLAN
```

Somente depois assegura o Device Type exato e executa PATCH. Device manual ou tipo já específico bloqueia a alteração.

### Componentes

```text
network_v4.py       4.3-product
classifier_v6.py    5.1-product
planner_v8.py       4.8-product
importer_v9.py      5.7-product
auditor_v8.py       6.6-product
pipeline            2.9-product
runner              2.8-product
```

Estado inicial: **CI/NOT LIVE até a única execução final `netbox-discovery run --apply` no FBA**.

---

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

---

## V1.10.17 — Create missing VM interface during safe duplicate repair

Adicionou criação protegida de `virtualization.vminterface MGMT` para VM inequívoca com zero interfaces e um único MAC VMware forte.

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
