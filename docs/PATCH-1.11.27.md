# netbox-discovery 1.11.27

## NetBox público em HTTPS/443

Esta versão migra com segurança instalações existentes que ainda usam exatamente:

```text
https://inventory.bkpcloud.app.br:8080
```

para:

```text
https://inventory.bkpcloud.app.br
```

A migração é executada durante a instalação/atualização do produto e altera somente `netbox.url` quando o valor é exatamente o endpoint legado acima.

Não há remoção genérica de `:8080`. URLs de outros clientes ou endpoints customizados permanecem inalterados. Tenant, Site, redes, exclusões, comunidades, credenciais, opções de SSL, automação e fontes de virtualização são preservados.

## Hypervisor/vCenter

A versão mantém o engine Hypervisor 5.1 introduzido na 1.11.26, incluindo a correção de herança de Site para VMs existentes que chegam ao planner como `READY/NOOP` e possuem Host/Cluster parent autoritativo.

A escrita de Hypervisor continua explícita: `netbox-discovery hypervisor run` é dry-run e `--apply` não é acionado pela atualização.

## Validação

A regressão 1.11.27 cobre:

- migração do endpoint legado sem porta para HTTPS/443;
- preservação do restante do `config.yml`;
- suporte a URL sem aspas, com aspas simples ou duplas;
- idempotência da migração;
- proteção de URLs customizadas;
- proteção contra substituição fora da seção `netbox`.
