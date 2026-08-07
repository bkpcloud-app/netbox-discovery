# netbox-discovery 1.11.29

## Correção Hypervisor

A 1.11.28 bloqueava toda a escrita do pipeline multi-context quando qualquer objeto permanecia em `REVIEW`, mesmo que o `REVIEW` já existisse no dry-run e não fosse elegível para escrita.

Caso real observado em FVI:

- 5 VMs `*_replica` em `REVIEW` por divergência de serial/UUID.
- 281 objetos `READY` no plano global.
- 53 `RECLASSIFY_SAFE` válidos para correção de Site.
- Resultado anterior: nenhuma escrita iniciada.

A 1.11.29 mantém os objetos `REVIEW` intocados e permite os objetos `READY` somente quando:

1. não existe nenhum `BLOCKED` no plano ao vivo;
2. o conjunto completo de `REVIEW` permanece idêntico ao dry-run;
3. o conjunto de `RECLASSIFY_SAFE` permanece idêntico ao dry-run;
4. os preflights já existentes de identidade, parent, cluster, catálogo e import continuam aprovando cada escrita.

Se surgir um novo `REVIEW`, se um `REVIEW` mudar, se surgir `BLOCKED` ou se mudar o conjunto de reclassificações, o pipeline continua abortando antes da primeira escrita.

Nenhum objeto em `REVIEW` é escrito automaticamente.
