# netbox-discovery 1.11.10

## Correção do fluxo real de IMPORT/AUDIT

A versão 1.11.9 corrigiu o Planner usado pelo comando `inventory`, mas o fluxo interno do IMPORT e do AUDIT ainda possuía referências antigas e aliases Python distintos. Isso fazia o IMPORT recalcular com Planner V10, voltar a bloquear os dois switches `SW-BA17-*` e percorrer as nove impressoras sem persistir o `device_type:SET`.

A 1.11.10 corrige o caminho efetivamente executado em produção:

- adiciona Importer V12 (`6.1-product`);
- adiciona Auditor V11 (`6.9-product`);
- mantém Planner V11 (`5.3-product`) em `inventory`, IMPORT e AUDIT;
- propaga o Planner V11 por todos os wrappers legados do importador e auditor;
- corrige os dois aliases de `importer.py` e `inventory.py` carregados pelo Python;
- aplica `device_type:SET` somente em Device existente, pertencente ao produto, com identidade confirmada e confiança HIGH;
- executa leitura do Device imediatamente depois do PATCH;
- considera a atualização concluída somente quando fabricante e modelo retornados pelo NetBox são exatamente os esperados;
- grava relatório específico `import-device-type-verify` com quantidade atualizada, verificada e eventuais erros;
- utiliza a chave estável de idempotência sem depender do nome preservado do Device;
- mantém os dois switches com nome de colisão em `READY/NOOP`;
- corrige os rótulos e rotas do CLI para Importer V12 e Auditor V11.

## Proteções

- não altera nomes existentes;
- não cria novos Devices para este ajuste;
- não escreve itens REVIEW ou BLOCKED;
- exige Tenant e Site corretos;
- exige ownership `Criado pelo netbox-discovery`;
- exige serial correspondente ou, quando não houver serial, todos os IPs vinculados ao mesmo Device;
- bloqueia se o Device Type atual já não for genérico;
- bloqueia se o fabricante/modelo do PLAN divergir do safe diff;
- bloqueia e retorna erro se o readback do NetBox não confirmar a alteração.

## Resultado esperado no FBA antes do APPLY

- `READY/CREATE: 0`;
- `READY/UPDATE_SAFE: 9`;
- `BLOCKED: 0`;
- Planner `5.3-product`;
- Importer `6.1-product`;
- Auditor `6.9-product`;
- `NetBox write: NÃO`.

## Resultado esperado no APPLY controlado

- nove Device Types atualizados e relidos;
- `Device Types verificados: 9`;
- `Status: PASS` no relatório de readback;
- plano de idempotência posterior com `READY/UPDATE_SAFE: 0`;
- nenhum falso `IDEMPOTENCY_ASSET_MISSING` para VMware ou ECOSYS;
- nenhum bloqueio para os dois switches `SW-BA17-*`.

## Regressões

`tests/test_network_1_11_10.py` valida:

- os aliases Python distintos que causaram a falha real;
- propagação do Planner V11 por todos os wrappers;
- atualização isolada de Device Type;
- criação de Manufacturer/Device Type quando necessário;
- PATCH no Device;
- leitura posterior e confirmação exata do fabricante/modelo;
- idempotência com nome preservado;
- rotas do CLI e componentes do runner;
- execução direta do Importer V12 e Auditor V11.
