# netbox-discovery

Produto BKPCLOUD para descoberta, classificação, reconciliação e inventário seguro de infraestrutura no NetBox.

**Versão atual:** 1.11.14 — PRODUCT V1  
**Distribuição:** repositório oficial `bkpcloud-app/netbox-discovery`  
**Canal de produção:** `stable`  
**NetBox BKPCLOUD:** `https://inventory.bkpcloud.app.br:8080`

## Atualização automática

A instalação e qualquer upgrade habilitam o timer de atualização do canal `stable`:

```bash
netbox-discovery update scheduler status
```

Política padrão:

```text
Frequência: diária
Persistent: true
Atraso aleatório: até 30 minutos
Validação: self-test antes e depois
Falha de instalação: rollback automático
```

Ao habilitar o scheduler Network ou Hypervisor, o timer correspondente também inicia o timer de atualização como dependência. Assim, instalações antigas continuam atualizadas mesmo quando o auto-update ainda não estava habilitado.

Desabilitar um scheduler de coleta não desabilita o auto-update.

## Primeira execução

```bash
netbox-discovery update run
netbox-discovery version
netbox-discovery check
netbox-discovery run
```

`netbox-discovery run` executa descoberta e PLAN sem escrita. A escrita só ocorre com `netbox-discovery run --apply`.

## Pipeline Network atual

```text
DISCOVER V6 / 4.6-product
→ CLASSIFY V8 / 5.6-product
→ RECONCILE V5 / 3.3-product
→ PLAN V11 / 5.3-product
→ WRITE GUARD + PREFLIGHT
→ IMPORT V12 / 6.1-product
→ AUDIT V11 / 6.9-product
```

Pipeline e Runner:

```text
Pipeline: 3.4-product
Runner: 3.4-product
```

## Redes grandes

Prefixos grandes, como `/16`, ativam automaticamente o modo `LARGE-CIDR`:

- divisão em lotes de até `/24`;
- execução paralela controlada;
- timeout e retry por lote;
- progresso visível;
- portas de infraestrutura, impressão, CFTV e OT no discovery primário;
- nenhuma escrita sem `--apply`.

## Schedulers

Network:

```bash
netbox-discovery scheduler enable
netbox-discovery scheduler status
netbox-discovery scheduler disable
```

Hypervisor:

```bash
netbox-discovery hypervisor scheduler enable
netbox-discovery hypervisor scheduler status
netbox-discovery hypervisor scheduler disable
```

Atualização:

```bash
netbox-discovery update scheduler enable
netbox-discovery update scheduler status
```

## Segurança de escrita

```text
READY/CREATE                    → somente com --apply
READY/UPDATE_SAFE               → somente com --apply
READY/REPAIR_SAFE_VM_DUPLICATE  → somente após preflight e write guard
READY/NOOP                      → não altera
DELEGATED                       → não altera
REVIEW                          → não altera
BLOCKED                         → não altera
```

O produto preserva nomes existentes e não executa PATCH automático de `name`.

## Documentação obrigatória

Cada release deve manter a versão exata em:

```text
README.md
docs/MANUAL.md
docs/COMANDOS-RAPIDOS.md
docs/HOMOLOGACAO.md
RELEASE-NOTES.md
SECURITY.md
docs/PATCH-<VERSÃO>.md
```

O CI bloqueia a publicação quando qualquer documento obrigatório fica em versão anterior.
