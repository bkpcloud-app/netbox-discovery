# netbox-discovery 1.11.11

## Correção

Corrige a ativação do scheduler Network em instalações antigas cujo `config.yml` foi preservado sem a seção `automation`.

O erro observado era:

```text
ERRO: automation.enabled não encontrado em config.yml
```

A instalação/atualização agora executa uma migração segura do arquivo preservado antes de liberar os comandos operacionais.

## Migração aplicada

Quando a seção não existe, o produto adiciona:

```yaml
automation:
  enabled: false
  apply: false
  schedule: daily
```

Quando a seção já existe, somente chaves ausentes são acrescentadas. Valores existentes não são sobrescritos.

## Segurança

- a migração não habilita o scheduler;
- `apply` nasce obrigatoriamente como `false` em configuração antiga;
- nenhuma descoberta é iniciada pela atualização;
- nenhum dado é escrito no NetBox;
- token, Tenant, Site, redes, exclusões e comunidades SNMP são preservados;
- permissões do `config.yml` são preservadas;
- arquivo malformado falha fechado em vez de criar uma segunda seção conflitante.

## Resultado esperado no FBA

Depois de atualizar para 1.11.11:

```bash
netbox-discovery scheduler enable
```

Deve habilitar o timer usando `OnCalendar=daily`, mantendo:

```yaml
automation:
  enabled: true
  apply: false
  schedule: daily
```

A execução recorrente permanece somente leitura:

```text
DISCOVER -> CLASSIFY -> RECONCILE -> PLAN
IMPORT automático: NÃO
```

## Validação

A regressão `tests/test_network_1_11_11.py` cobre:

- migração de configuração antiga sem `automation`;
- idempotência da migração;
- preservação de valores existentes;
- `apply: false` como padrão seguro;
- preservação do token e das permissões;
- falha fechada em configuração malformada;
- execução da migração pelo instalador antes do `check`;
- compatibilidade com o comando atual do scheduler.
