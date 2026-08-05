# netbox-discovery 1.11.16 — PLAN nativo e status por RUN

## Objetivo

Eliminar comandos Python improvisados para analisar o PLAN e impedir que o `status` misture um dry-run atual com IMPORT/AUDIT de execuções antigas.

## Comandos novos

```bash
netbox-discovery plan summary
netbox-discovery plan blocked
netbox-discovery plan review
netbox-discovery plan ready
netbox-discovery plan delegated
netbox-discovery plan all
```

Opções:

```bash
netbox-discovery plan blocked --limit 20
netbox-discovery plan summary --json
```

## Dados apresentados

```text
Site
Run ID
Run status
NetBox write
arquivo do PLAN
decisões
ações
motivos agrupados
IP
nome
role
diffs seguros
```

## Segurança

Os comandos são somente leitura. Eles não chamam Importer, não executam `--apply` e não alteram o NetBox.

## Status corrigido

Quando o último RUN é dry-run:

```text
IMPORT: NÃO EXECUTADO NESTE RUN (dry-run)
AUDIT: NÃO EXECUTADO NESTE RUN (dry-run)
```

Relatórios históricos deixam de ser apresentados como se pertencessem ao RUN atual.

## Compatibilidade

`netbox-discovery plan` sem subcomando continua gerando o PLAN pelo Planner V11. A funcionalidade existente não foi removida.
