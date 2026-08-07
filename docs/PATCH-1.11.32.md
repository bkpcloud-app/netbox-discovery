# netbox-discovery 1.11.32

## Atualizador sem falso `ATUALIZADO` por cache do GitHub Raw

Após a publicação da 1.11.31 foi observado em produção que um agente 1.11.30 continuava exibindo `ATUALIZADO: 1.11.30`, embora o branch `stable` já estivesse em 1.11.31.

A causa era a leitura de `stable/VERSION` via `raw.githubusercontent.com` imediatamente após o merge, que podia devolver temporariamente uma cópia em cache.

A 1.11.32 acrescenta um parâmetro `cache_bust` único em cada consulta de versão e envia `Cache-Control: no-cache` e `Pragma: no-cache`.

Assim, o updater deixa de aceitar uma resposta antiga do CDN como evidência de que não existe atualização.

A correção da 1.11.31 para o configurador HTTPS/443 permanece incluída nesta versão.
