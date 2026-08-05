# netbox-discovery 1.11.13

## Correção

Completa a ativação do Discovery V6 entregue na 1.11.12.

O Runner principal já utilizava `network_v6.py`, porém dois caminhos operacionais ainda apontavam para V5:

- `netbox-discovery discover`;
- o componente exibido por `netbox-discovery check`.

Além disso, o self-test ainda não exigia nem validava explicitamente o arquivo `network_v6.py`.

## Ajustes

- `netbox-discovery discover` passa a executar `network_v6.py`;
- `netbox-discovery check` passa a mostrar `DISCOVER V6: OK`;
- o self-test exige `modules/discovery/network_v6.py`;
- o contrato de componentes valida `DISCOVERY_WRAPPER_VERSION = 4.6-product`;
- o pipeline `run` e o comando direto `discover` usam o mesmo componente;
- nenhuma mudança foi feita no Planner, Importer, Auditor ou política de escrita.

## Segurança

- a atualização não inicia descoberta;
- a atualização não habilita o scheduler;
- a atualização não altera `automation.apply`;
- `netbox-discovery run` continua somente leitura quando executado sem `--apply`;
- as redes configuradas no DCM são preservadas.

## DCM

Depois da atualização, o resultado esperado de `netbox-discovery check` inclui:

```text
DISCOVER V6: OK
CLASSIFY V8: OK
RECONCILE V5: OK
PLAN V11: OK
IMPORT V12: OK
AUDIT V11: OK
```

A coleta do DCM pode então ser iniciada em uma unidade transitória do systemd, sem depender da sessão SSH e sem escrita no NetBox.
