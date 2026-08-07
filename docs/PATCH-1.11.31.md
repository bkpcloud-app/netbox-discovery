# netbox-discovery 1.11.31

## Configurador alinhado ao NetBox HTTPS/443

A migração do produto para `https://inventory.bkpcloud.app.br` já estava ativa no loader central, porém o assistente `netbox-discovery configure` ainda mantinha um endpoint fixo legado com `:8080`.

Isso fazia o configurador salvar novamente a URL antiga e, ao testar a conexão, o próprio loader central recusava a configuração com `Endpoint NetBox não autorizado`.

A 1.11.31 corrige o endpoint fixo do configurador para:

`https://inventory.bkpcloud.app.br`

Também inclui regressão que exige que o endpoint do configurador e o endpoint bloqueado pelo loader central sejam exatamente o mesmo e que `:8080` não seja reintroduzido.
