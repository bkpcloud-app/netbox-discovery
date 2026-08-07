# netbox-discovery 1.11.28

## Correção crítica do endpoint NetBox HTTPS/443

A 1.11.27 migrou corretamente instalações legadas de:

```text
https://inventory.bkpcloud.app.br:8080
```

para:

```text
https://inventory.bkpcloud.app.br
```

porém o carregador central `lib/config.py` ainda mantinha o endpoint bloqueado antigo com `:8080`. Isso fazia o bootstrap rejeitar a própria configuração recém-migrada e acionar rollback.

A 1.11.28 corrige a origem da inconsistência:

- `LOCKED_NETBOX_URL` passa a ser `https://inventory.bkpcloud.app.br`;
- a URL pública HTTPS/443 é aceita pelo carregador central;
- o endpoint legado `:8080` deixa de ser aceito após a migração;
- URLs NetBox de terceiros/customizadas continuam bloqueadas pelo produto;
- a migração segura da 1.11.27 é preservada;
- configuração, Tenant, Site, redes, credenciais, automação e fontes de hypervisor continuam preservados;
- nenhuma escrita Hypervisor é executada automaticamente durante update;
- o engine Hypervisor 5.1 e a correção de Site de VMs da 1.11.26 permanecem intactos.

## Regressão adicionada

A regressão 1.11.28 valida diretamente `lib.config.load_config()` e impede nova divergência entre a migração e o endpoint bloqueado pelo produto.
