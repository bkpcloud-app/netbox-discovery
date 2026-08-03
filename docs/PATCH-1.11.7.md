# netbox-discovery 1.11.7

## Auditoria consolidada — 30 pontos de vista

1. **Canal de atualização:** mantém `stable` como única origem operacional.
2. **Compatibilidade:** preserva Python 3.6 e o modo de execução atual do proxy.
3. **Dry-run:** `inventory` continua sem qualquer escrita no NetBox.
4. **Vínculo de relatórios:** mantém DISCOVER, CLASSIFY, RECONCILE e PLAN encadeados pelo mesmo relatório.
5. **Autoridade de virtualização:** VMs continuam delegadas ao inventário centralizado.
6. **VM parcial:** correlação incompleta permanece apenas diagnóstica, sem criação local.
7. **Nome existente:** o nome definido no NetBox continua protegido.
8. **Colisão de nomes:** sufixo só é permitido com identidade física forte.
9. **Windows Server/Workstation:** a separação por edição explícita permanece ativa.
10. **Windows novo:** não cria Device sem serial ou MAC estável.
11. **Dispositivo físico novo:** não cria objeto com `WEAK:*` sem serial/MAC estável.
12. **Moxa NPort:** identificação exata de modelo continua visível, mas criação sem identidade estável vai para REVIEW.
13. **Serial Brother:** serial alfanumérico válido não é confundido com MAC.
14. **MAC real:** continua rejeitado como serial.
15. **Serial placeholder:** amplia bloqueio de sequências genéricas e valores indisponíveis.
16. **Serial conflitante:** evidências fortes divergentes continuam impedindo gravação.
17. **Serial duplicado no lote:** continua bloqueado pelo PLAN.
18. **Proveniência do serial:** preserva Printer-MIB, ENTITY-MIB, ONVIF/ISAPI e demais fontes.
19. **Modelo Samsung:** nome `SEC...` não pode virar modelo.
20. **Modelo Brother:** nome `BRN...` não pode virar modelo.
21. **Modelo HP:** nome `NPI...` não pode virar modelo.
22. **Modelo Xerox/Epson/Canon:** nomes automáticos conhecidos não podem virar modelo.
23. **Modelo Kyocera:** `ECOSYS` e `TASKalfa` permanecem modelos válidos mesmo quando usados como nome.
24. **Modelo Pantum:** `BM5100FDW` e famílias equivalentes permanecem modelos válidos.
25. **Device Type genérico:** `Printer-MIB managed printer` nunca é elegível para criação ou atualização.
26. **Atualização parcial:** serial válido pode ser gravado mesmo quando o modelo é rejeitado.
27. **Atualização somente genérica:** vira NOOP, sem criar catálogo falso.
28. **Impressora nova:** exige modelo específico e identidade estável para ficar READY.
29. **Pré-requisitos do NetBox:** catálogo é reduzido somente aos objetos realmente usados por ações READY.
30. **Write Guard:** é recalculado depois de todas as supressões e mudanças de decisão.

## Casos reais do FBA cobertos

- Samsung `10.2.2.86`: preserva o serial, mas rejeita `SEC30CDA7FFE27C` como modelo.
- Kyocera `10.2.2.84` e `10.2.2.88`: mantém `ECOSYS M3655idn` como modelo específico.
- Brother `10.2.2.85`: aceita `U64189M8N960565` como serial.
- Pantum `10.2.2.92`: mantém `BM5100FDW` como modelo específico.
- Moxa `10.2.2.39`: impede CREATE enquanto não houver identidade física estável.
- Windows `10.2.100.10`: permanece REVIEW sem serial/MAC estável.

## Validação

A regressão `tests/test_network_1_11_7.py` contém 36 verificações independentes cobrindo descoberta, classificação, serial, modelos, PLAN, pré-requisitos e identidade física.

## Operação

Após a publicação no `stable`, a execução permanece simples:

```bash
netbox-discovery update run
netbox-discovery inventory
```

Não usar `--apply` antes da revisão do novo PLAN.
