## V1.11.14 — Scheduler guarantees auto-update and documentation parity

### Auto-update ligado aos schedulers

Os timers Network e Hypervisor agora iniciam `netbox-discovery-update.timer` como dependência `Wants`.

Resultado:

- habilitar coleta automática também garante atualização automática;
- instalações antigas entram no fluxo de atualização sem ajuste manual;
- desabilitar a coleta não desabilita o auto-update;
- `automation.apply` não é alterado;
- o update continua no canal `stable`, com self-test e rollback.

### Documentação obrigatória

A release atualiza e sincroniza:

```text
README.md
docs/MANUAL.md
docs/COMANDOS-RAPIDOS.md
docs/HOMOLOGACAO.md
RELEASE-NOTES.md
SECURITY.md
docs/PATCH-1.11.14.md
```

O CI passa a validar a versão exata em todos esses documentos. Não basta mais conter apenas a família `1.11`.

### Componentes

```text
network_v6.py       4.6-product
classifier_v8.py    5.6-product
reconciler_v5.py    3.3-product
planner_v11.py      5.3-product
importer_v12.py     6.1-product
auditor_v11.py      6.9-product
pipeline             3.4-product
runner               3.4-product
```

---

## V1.11.13 — Discovery V6 em todos os entrypoints

- `netbox-discovery discover` passa a chamar V6;
- `netbox-discovery check` informa `DISCOVER V6: OK`;
- self-test exige e valida `network_v6.py`.

---

## V1.11.12 — Discovery escalável para `/16`

- modo `LARGE-CIDR` automático;
- divisão de redes grandes em lotes `/24`;
- paralelismo, timeout e retry por lote;
- progresso visível;
- portas de infraestrutura, impressão, CFTV e OT no discovery primário;
- execução read-only sem `--apply`.

---

## V1.11.11 — Migração segura de scheduler

Configurações antigas recebem, sem sobrescrever valores existentes:

```yaml
automation:
  enabled: false
  apply: false
  schedule: daily
```

---

## V1.11.10 — Import e auditoria idempotentes

- Importer V12 força Planner V11 em todos os aliases legados;
- Device Type recebe PATCH protegido e readback obrigatório;
- Auditor V11 deixa de depender do nome preservado;
- falhas reais de escrita continuam bloqueadas.

---

## V1.11.9 — Recuperação de switches existentes

Recupera colisões seguras quando serial, IP, ownership e Device existente comprovam a mesma identidade.

---

## V1.11.8 — Correções pós-APPLY

- nomes existentes preservados;
- aliases de roles Windows normalizados;
- Device Type específico aplicado somente em Device criado pelo produto.

---

## V1.11.2 — Windows e qualidade de serial

- separação segura Windows Server/Workstation;
- agregação e validação de candidatos de serial;
- Printer-MIB, Hikvision/ONVIF e protocolos industriais;
- nome manual protegido.

---

## V1.11.0 — Identidade consolidada e segurança de escrita

- motor central de identidade;
- `REVIEW`, `BLOCKED`, `DELEGATED` e write guard;
- nome existente como autoridade do NetBox;
- virtualização centralizada;
- industrial estruturado;
- CFTV por evidência específica.
