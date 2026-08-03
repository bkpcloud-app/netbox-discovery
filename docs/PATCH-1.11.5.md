# netbox-discovery 1.11.5

Patch corretivo do entrypoint do Planner V9 em instalações reais.

## Incidente

A versão 1.11.4 concluía DISCOVER, CLASSIFY e RECONCILE, mas o comando `netbox-discovery inventory` falhava ao iniciar o Planner diretamente:

```text
ModuleNotFoundError: No module named 'modules'
```

A falha ocorreu em modo dry-run, antes do PLAN e sem escrita no NetBox.

## Correção

- o `planner_v9.py` agora resolve a raiz do produto e prepara o caminho de importação antes de carregar `planner_v9_core`;
- mantém compatibilidade com Python 3.6.8;
- o `self-test` passa a executar o Planner diretamente, fora do diretório do pacote e sem `PYTHONPATH`;
- a CI reproduz a mesma forma de execução usada pelo servidor.

## Operação

```bash
netbox-discovery update run
netbox-discovery inventory
```

Não usar `--apply` antes da revisão do PLAN.
