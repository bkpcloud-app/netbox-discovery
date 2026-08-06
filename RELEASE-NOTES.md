## V1.11.22 — Runtime MAC interface reuse

A terceira tentativa de APPLY do DCM, já na 1.11.21, passou pelos dois preflights mas ainda falhou no runtime do primeiro READY:

```text
PREFLIGHT GLOBAL FINALIZE: OK
PREFLIGHT: OK
ERRO em SW-CORE-AE: MAC E8:B5:D0:72:9D:FC já pertence a dcim.interface ID 543
```

O runtime do Importer V2 procurava a interface pelo nome do `spec` antes de validar a MAC. Quando o nome live divergia, ele podia criar uma segunda interface e só depois descobrir que a MAC já estava na interface original.

A 1.11.22 altera a ordem:

```text
resolver MAC global
→ resolver dcim.interface vinculada
→ validar interface.device.id
→ reutilizar a interface live do mesmo Device
→ somente sem vínculo usar busca/criação por nome
```

Conflitos reais continuam bloqueados antes da criação. A regressão reproduz a interface ID 543, nome divergente, mesma MAC repetida, owner estrangeiro, vínculo em VM e MAC sem atribuição.

---

## V1.11.21 — Legacy MAC owner preflight recovery

A segunda tentativa de APPLY do DCM, já na 1.11.20, foi bloqueada antes da escrita por um falso conflito no `SW-CORE-AE`:

```text
MAC E8:B5:D0:72:9D:FC pertence a dcim.interface ID 543,
esperado interface ainda não existente
```

O PLAN já havia reconciliado o equipamento parcial corretamente como `READY/NOOP`, com `SERIAL+MAC+IP+NAME`. A camada global nova reconhecia que a interface pertencia ao próprio Device, mas o preflight V5 legado ainda inferia a interface exclusivamente pelo IP presente no `spec`.

A 1.11.21 corrige essa camada:

```text
interface live pertence ao mesmo Device reconciliado
→ PASS

interface live pertence a outro Device
→ BLOQUEADO

mesma MAC repetida em vários specs do mesmo registro
→ avaliada uma única vez
```

A validação consulta `dcim/interfaces`, usa `interface.device.id` como autoridade e continua fail-closed quando o owner não pode ser resolvido.

---

## V1.11.20 — Global MAC ownership preflight

O primeiro APPLY do DCM na 1.11.19 parou no primeiro `READY`, `SW-CORE-AE`, porque a MAC de gerenciamento já pertencia à interface ID 543.

A 1.11.20 adicionou proteção no Planner V11 e Importer V12 para validar ownership global antes da primeira escrita.

---

## V1.11.19 — Final stable identity guard

Novo `READY/CREATE` com `discovery_uid WEAK` passa a `REVIEW/NOOP`, independentemente de role ou classe.

---

## V1.11.18 — Small-site bootstrap write guard

Sites com menos de 50 Devices adiam apenas a regra percentual. Limites absolutos permanecem obrigatórios.

---

## V1.11.17 — Final write guard ordering

O write guard passa a ser calculado uma única vez após todas as políticas finais do Planner.

---

## V1.11.16 — Native PLAN reports and run-scoped status

Foram adicionados relatórios nativos somente leitura:

```text
netbox-discovery plan summary
netbox-discovery plan blocked
netbox-discovery plan review
netbox-discovery plan ready
netbox-discovery plan delegated
netbox-discovery plan all
```

---

## V1.11.15 — Update preflight before every scheduled collection

Network e Hypervisor executam o updater imediatamente antes de cada coleta agendada.

---

## V1.11.14 — Scheduler guarantees auto-update and documentation parity

- timer de update garantido;
- desabilitar coleta não desabilita update;
- documentação principal sincronizada.

---

## V1.11.13 — Discovery V6 entrypoints

- comando direto `discover` alinhado ao Discovery V6;
- `check` atualizado para V6;
- self-test exige o componente V6.

---

## V1.11.12 — Large-CIDR discovery

- prefixos grandes divididos em lotes `/24`;
- paralelismo controlado;
- suporte ao cenário DCM com `/16`.

---

## V1.11.11 — Scheduler migration

- bloco `automation` seguro;
- scheduler inicia desabilitado;
- `apply` permanece falso por padrão.

---

## V1.11.10 — Import and audit idempotency

- Device Type aplicado e verificado;
- aliases corrigidos;
- auditoria idempotente;
- piloto FBA concluído sem FAIL.

---

## V1.11.0–1.11.9 — Identity and safety consolidation

- identidade e proveniência;
- virtualização centralizada;
- Printer-MIB, Windows, industrial e CFTV;
- proteção de nomes;
- write guard, preflight e auditoria final.
