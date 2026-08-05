## V1.11.16 — Native PLAN reports and run-scoped status

### Relatório nativo do PLAN

A análise do PLAN passa a ser feita por comandos oficiais do produto, sem Python colado no terminal:

```text
netbox-discovery plan summary
netbox-discovery plan blocked
netbox-discovery plan review
netbox-discovery plan ready
netbox-discovery plan delegated
netbox-discovery plan all
```

Os relatórios mostram Run ID, status, escrita no NetBox, decisões, ações, motivos, IP, nome, role e diffs. Todos são somente leitura e aceitam `--json`.

### Status vinculado ao modo do último RUN

Quando o último RUN é dry-run, `status` não mistura mais IMPORT/AUDIT de execuções antigas. A saída informa explicitamente que essas etapas não foram executadas naquele RUN.

### Compatibilidade

`netbox-discovery plan` sem subcomando continua executando o Planner V11 normalmente. Os novos subcomandos apenas leem o último relatório existente.

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
