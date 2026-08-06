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

A validação agora consulta `dcim/interfaces`, usa `interface.device.id` como autoridade e continua fail-closed quando o owner não pode ser resolvido. Não há transferência automática de MAC.

A regressão reproduz a interface ID 543, o `READY/NOOP` parcial, o spec sem IP inferível e a duplicação da mesma MAC em dois specs.

---

## V1.11.20 — Global MAC ownership preflight

O primeiro APPLY do DCM na 1.11.19 parou no primeiro `READY`, `SW-CORE-AE`, porque a MAC de gerenciamento já pertencia à interface ID 543:

```text
MAC E8:B5:D0:72:9D:FC já pertence a dcim.interface ID 543
```

O conflito foi detectado tarde, depois de `PREFLIGHT: OK`, quando o Importer já estava no loop de escrita. A execução deve ser tratada como possível aplicação parcial do primeiro equipamento.

A 1.11.20 adiciona proteção em duas camadas:

```text
PLAN V11
→ valida toda MAC presente nas interfaces finais
→ MAC pertencente a outro objeto vira BLOCKED/NOOP
→ write guard conta apenas os READY restantes

IMPORT V12
→ repete a consulta global de MAC antes da primeira escrita
→ conflito ou falha de consulta bloqueia o lote inteiro sem iniciar novas escritas
```

A regra aceita somente MAC livre, sem atribuição, ou já vinculada à interface do mesmo `existing_device_id`. Não há transferência automática entre Devices, VMs ou outros objetos.

A regressão reproduz a interface ID 543, valida bloqueio no PLAN, preflight fail-closed e isolamento dos outros 13 candidatos estáveis do DCM.

---

## V1.11.19 — Final stable identity guard

A revisão ao vivo do PLAN 1.11.18 no DCM encontrou três novos candidatos indevidamente liberados como `READY/CREATE` apesar de possuírem `Discovery UID: WEAK`:

```text
10.28.1.22 | SRV-DCAR03 | WINDOWS_HOST
10.28.1.23 | SRV-DCAR02 | WINDOWS_HOST
10.225.1.61 | SMS Agente SNMP | SMS_GATEWAY
```

As proteções anteriores eram específicas para classes físicas e roles Windows conhecidas. A 1.11.19 adiciona uma validação final independente de role e classe:

```text
novo READY/CREATE + discovery_uid WEAK
→ REVIEW/NOOP
→ interfaces e intenções de IP removidas
```

A regra roda antes do write guard. Assim, candidatos fracos não entram em `eligible_total`, enquanto identidades estáveis por serial ou management MAC continuam elegíveis.

No cenário DCM, o resultado esperado passa de 17 para 14 `READY/CREATE`, mantendo os dois conflitos Kubernetes em `BLOCKED` e o write guard em `PASS`.

---

## V1.11.18 — Small-site bootstrap write guard

Sites em fase inicial não usam mais a regra percentual enquanto a base tiver menos de 50 Devices.

```text
base < 50  → SMALL_SITE_BOOTSTRAP_ABSOLUTE_ONLY
base >= 50 → ABSOLUTE_AND_PERCENT
```

Durante o bootstrap, apenas o percentual é adiado. Os limites absolutos continuam obrigatórios:

```text
CREATE=25
UPDATE_SAFE=50
REPAIR_SAFE_VM_DUPLICATE=20
TOTAL=75
```

O relatório nativo do PLAN mostra política, percentual ativo/adiado e base mínima. A regressão cobre o cenário DCM de 17 mudanças sobre 13 Devices, o bloqueio absoluto de 26 criações e o bloqueio percentual em base madura.

Conflitos de identidade, nomes duplicados, REVIEW, DELEGATED e BLOCKED continuam sem escrita.

---

## V1.11.17 — Final write guard ordering

O ciclo DCM revelou um falso bloqueio: uma camada intermediária calculou `CREATE=32` antes de políticas posteriores reclassificarem candidatos fracos para `REVIEW`.

Planner V11 agora executa a sequência:

```text
políticas finais de identidade e inventário
→ decisões finais
→ write guard uma única vez
```

Somente mudanças finais `READY/CREATE`, `READY/UPDATE_SAFE` e `READY/REPAIR_SAFE_VM_DUPLICATE` entram no cálculo. Os limites existentes continuam inalterados e mudanças finais excessivas continuam bloqueadas.

`netbox-discovery plan summary` passa a mostrar status, elegíveis, base de Devices, percentual e violações do guard efetivo.

A regressão reproduz 32 candidatos intermediários sobre 13 Devices, exigindo guard final PASS depois da conversão para `REVIEW/NOOP`, e valida também que 26 `READY/CREATE` finais continuam bloqueados pelo limite 25.

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

O status deixou de apresentar IMPORT/AUDIT históricos como se pertencessem a um dry-run atual.

---

## V1.11.15 — Update preflight before every scheduled collection

Network e Hypervisor executam o updater imediatamente antes de cada coleta agendada. Atualização válida é instalada e testada; falha de candidato executa rollback/quarentena; indisponibilidade temporária do GitHub não cancela a coleta.

---

## V1.11.14 — Scheduler guarantees auto-update and documentation parity

- schedulers Network e Hypervisor garantem que o timer de update esteja habilitado;
- desabilitar coleta não desabilita update;
- documentação principal sincronizada;
- CI exige versão exata dos documentos.

---

## V1.11.13 — Discovery V6 entrypoints

- comando direto `discover` alinhado ao Discovery V6;
- `check` atualizado para V6;
- self-test exige o componente V6.

---

## V1.11.12 — Large-CIDR discovery

- prefixos grandes divididos em lotes `/24`;
- paralelismo controlado;
- progresso e erros por lote;
- suporte ao cenário DCM com `/16`.

---

## V1.11.11 — Scheduler migration

- configurações antigas recebem bloco `automation` seguro;
- scheduler inicia desabilitado;
- `apply` permanece falso por padrão.

---

## V1.11.10 — Import and audit idempotency

- Device Type aplicado e verificado;
- aliases de módulos corrigidos;
- auditoria idempotente por identidade estável;
- piloto FBA concluído sem FAIL.

---

## V1.11.0–1.11.9 — Identity and safety consolidation

- identidade e proveniência;
- virtualização centralizada;
- Printer-MIB, Windows, industrial e CFTV;
- proteção de nomes;
- write guard, preflight e auditoria final;
- correções sucessivas baseadas no piloto FBA.
