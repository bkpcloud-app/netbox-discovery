# netbox-discovery 1.11.4

Patch corretivo do comando `netbox-discovery inventory` e da etapa de inventário executada pelo `netbox-discovery run`.

## Problema corrigido

O pipeline selecionava o relatório padrão pelo horário de modificação do arquivo. Um relatório antigo de 30/07 podia ser escolhido depois de ser relido ou recriado, mesmo existindo uma descoberta válida de 03/08.

Isso permitia misturar:

```text
DISCOVER atual
CLASSIFY/RECONCILE/PLAN antigos
```

## Nova política

- seleciona o DISCOVER pela data registrada no nome do relatório;
- restringe a seleção ao site configurado no proxy;
- CLASSIFY precisa declarar exatamente o `source_discovery` selecionado;
- RECONCILE precisa declarar exatamente o `source_classification` gerado;
- PLAN precisa declarar exatamente o `source_reconciliation` e o `source_classification` da mesma execução;
- se qualquer vínculo não existir, o pipeline encerra sem escrita;
- `netbox-discovery inventory` continua sempre dry-run.

## Operação

```bash
netbox-discovery update run
netbox-discovery version
netbox-discovery self-test
netbox-discovery inventory
```

Não é necessário informar caminhos, datas ou parâmetros de arquivo. Não executar `--apply` antes da revisão do PLAN.
