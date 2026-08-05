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
