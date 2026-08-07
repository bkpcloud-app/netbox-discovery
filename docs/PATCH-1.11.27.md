# netbox-discovery 1.11.27

## Mudança do endpoint público do NetBox

O endpoint oficial do produto passa de:

```text
https://inventory.bkpcloud.app.br:8080
```

para:

```text
https://inventory.bkpcloud.app.br
```

A migração ocorre automaticamente durante o update somente quando `netbox.url` corresponde exatamente ao endpoint legado oficial.

## Política TLS definida para o endpoint oficial

Para essa migração, o produto grava:

```yaml
verify_ssl: false
```

A decisão é intencional: o reverse proxy em HTTPS/443 está operacional, porém alguns proxies Linux não confiam na cadeia apresentada. A coleta deve continuar usando TLS sem bloquear por validação da CA.

## Segurança da migração

- não remove `:8080` genericamente;
- não altera URLs customizadas de clientes;
- URLs customizadas também mantêm sua política SSL existente;
- Tenant, Site, redes, exclusões, comunidades, credenciais, automação e fontes Hypervisor permanecem preservados;
- a migração é idempotente;
- nenhum `--apply` é executado pelo update.

## Hypervisor/vCenter

A versão preserva integralmente o engine 5.1 introduzido na 1.11.26, incluindo a correção de VMs `READY/NOOP` com Site divergente do Host/Cluster parent.
