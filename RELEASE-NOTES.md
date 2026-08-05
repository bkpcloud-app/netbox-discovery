## V1.11.15 — Update preflight before every scheduled collection

### Sequência automática corrigida

Network e Hypervisor agora executam o updater imediatamente antes de cada coleta agendada:

```text
UPDATE PREFLIGHT
→ instalar atualização validada quando existir
→ self-test/check
→ rollback e quarentena em falha
→ iniciar coleta
```

Os serviços usam `ExecStartPre` com tolerância a falha externa. Se o GitHub estiver indisponível, o problema fica registrado e a coleta continua com a versão instalada válida.

### Segurança

- não altera `automation.apply`;
- não executa `--apply`;
- preserva token, redes, exclusões e communities;
- mantém lock global entre Update, Network e Hypervisor;
- mantém timer diário de update independente.

### Documentação e regressão

- documentos oficiais sincronizados na 1.11.15;
- regressão valida a ordem `ExecStartPre` antes de `ExecStart`;
- regressão valida tolerância a falha externa;
- testes históricos deixam de exigir a versão corrente fixa e passam a validar sua versão mínima, evitando manutenção artificial em cada release.

---

## V1.11.14 — Scheduler guarantees auto-update and documentation parity

- schedulers Network e Hypervisor garantem que o timer de update esteja habilitado;
- desabilitar coleta não desabilita update;
- documentação principal sincronizada;
- CI passou a exigir versão exata dos documentos.

---

## V1.11.13 — Discovery V6 entrypoints

- comando direto `discover` alinhado ao Discovery V6;
- `check` atualizado para V6;
- self-test passou a exigir e validar o componente V6.

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
