# netbox-discovery 1.11.30

## VMware `_replica`: UUID renovado e Site autoritativo

A coleta em produção mostrou cinco VMs VMware com sufixo exato `_replica` resolvidas pelo vCenter para `MIZU/FVI`, mas mantidas em `REVIEW` porque o UUID atual da origem divergia do serial/UUID armazenado no NetBox.

Essas réplicas são objetos próprios e podem ter o UUID renovado sem serem confundidas com a VM principal. A 1.11.30 adiciona uma exceção restrita para esse caso.

### Regra segura

A atualização automática do UUID só é permitida quando todas as condições abaixo forem verdadeiras:

- objeto é VM VMware;
- nome termina exatamente em `_replica`;
- existe exatamente uma VM com esse nome no NetBox;
- o objeto encontrado é o mesmo `existing_id` do PLAN;
- o único conflito do PLAN é `serial/UUID da VM diverge do objeto existente`.

Nesse cenário o UUID recebido do vCenter passa a ser autoritativo, a VM pode receber `UPDATE_SAFE` e também `RECLASSIFY_SAFE` para o Tenant/Site resolvido pelo host/cluster.

Qualquer VM sem `_replica`, qualquer outro provider, nome duplicado ou conflito adicional continua em `REVIEW` e não recebe escrita automática.

### Caso esperado em FVI

As VMs abaixo devem deixar de aparecer como `AMBIGUOUS` após APPLY:

- `SRV-VI01_replica`
- `SRV-IVI02_replica`
- `SRV-IVI01_replica`
- `SRV-BKP-VI_replica`
- `SNOC-MZVI_replica`

Resultado esperado do compare final: `MISMATCH=0`, `MISSING=0`, `AMBIGUOUS=0`.
