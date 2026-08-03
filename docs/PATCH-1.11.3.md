# netbox-discovery 1.11.3

Patch corretivo do Planner V9 para compatibilidade com o formato real dos pré-requisitos retornados no FBA.

## Correção

- aceita `prerequisites.roles` e `prerequisites.device_types` como lista, dicionário, ausente ou valor inválido;
- preserva a saída em lista, que é o formato do PLAN JSON e do importer;
- remove roles internas `WINDOWS_SERVER` e `WINDOWS_WORKSTATION` dos pré-requisitos;
- cria somente `SERVER-WINDOWS` e `WORKSTATION-WINDOWS` quando ainda não existem no NetBox;
- evita duplicar Device Types Windows já existentes;
- mantém todas as proteções da 1.11.2 para nomes, serial, CFTV, impressoras, VMs e write guard.

## Incidente reproduzido

A versão 1.11.2 encerrava o dry-run com:

```text
AttributeError: 'list' object has no attribute 'items'
```

O erro ocorria antes do PLAN e antes de qualquer escrita. A execução afetada permaneceu em modo `DRY-RUN`, com `Gravação no NetBox: NÃO`.

## Operação

```bash
netbox-discovery update run
netbox-discovery version
netbox-discovery self-test
netbox-discovery run
```

Não executar `--apply` antes da revisão do novo PLAN.
