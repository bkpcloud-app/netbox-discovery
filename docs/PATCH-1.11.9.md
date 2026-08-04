# netbox-discovery 1.11.9

## Correções

- adiciona o Planner V11 (`5.3-product`);
- recupera com segurança Devices que já foram criados com nome de colisão e depois aparecem como `BLOCKED` por `DUPLICATE_DESIRED_NAME`;
- cobre os casos reais `SW-BA17-LB43JZ` e `SW-BA17-KPC2C1`;
- exige coincidência simultânea de `existing_device_id`, serial, todos os IPs, role, fabricante, modelo e nome com sufixo do serial;
- mantém bloqueado qualquer objeto manual, serial divergente, IP divergente ou modelo divergente;
- atualiza o pipeline para Planner V11;
- corrige os comandos diretos para usar Classifier V8, Planner V11, Importer V11 e Auditor V10;
- corrige os rótulos exibidos por `netbox-discovery check`.

## Segurança operacional

- a correção dos switches resulta em `READY/NOOP`; não gera escrita;
- os nove ajustes de impressoras permanecem `READY/UPDATE_SAFE` e continuam sujeitos à revisão antes do `--apply`;
- nomes existentes continuam protegidos pelo NetBox;
- nenhum scheduler de Network ou Hypervisor é habilitado;
- o primeiro passo após atualização continua sendo `netbox-discovery inventory`, sem escrita.

## Resultado esperado no FBA

- `BLOCKED: 0` para os dois switches já correspondidos por identidade forte;
- `READY/UPDATE_SAFE: 9` para os Device Types das impressoras;
- `READY/CREATE: 0`;
- `PLAN V11: OK`;
- `NetBox write: NÃO`.

## Validação

A regressão `tests/test_network_1_11_9.py` valida:

- os dois switches reais;
- bloqueio por serial divergente;
- bloqueio de Device manual;
- componentes usados pelo pipeline e runner;
- rotas e rótulos do CLI;
- execução direta do Planner V11.
