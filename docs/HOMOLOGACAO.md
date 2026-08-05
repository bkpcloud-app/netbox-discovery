# netbox-discovery 1.11.14 — Matriz de Homologação

## Estados

```text
LIVE PASS     = validado ao vivo com evidência
LIVE PARTIAL  = parte relevante validada
CI PASS       = regressões automatizadas passaram
NOT LIVE      = ainda não validado ao vivo
```

CI PASS não equivale a LIVE PASS.

## Componentes da release

```text
Discovery V6:   4.6-product
Classifier V8:  5.6-product
Reconciler V5:  3.3-product
Planner V11:    5.3-product
Importer V12:   6.1-product
Auditor V11:    6.9-product
Pipeline:        3.4-product
Runner:          3.4-product
```

## Hypervisor central

**Estado histórico:** LIVE PASS.

```text
Objetos comparados: 282
OK: 282
MISMATCH: 0
MISSING: 0
AMBIGUOUS: 0
COMPARE STATUS: OK
```

O coletor central permanece responsável por vCenters. Filiais configuradas como `network_proxy` não executam Hypervisor local.

## FBA — linha de base

**Ciclo 1.10.18 em 29/07/2026:** LIVE PASS.

```text
Hosts ativos: 288
Assets reconciliados: 283
Devices após APPLY: 179
DELEGATED/HYPERVISOR: 37
Assets FAIL: 0
Checks FAIL: 0
```

As versões 1.11.x adicionaram proteção de nome, qualidade de serial, Windows Server/Workstation, correções idempotentes de Device Type, recuperação de switches e Planner V11.

## DCM — redes grandes

Redes configuradas:

```text
10.1.1.0/24
10.19.0.0/16
10.28.1.0/24
10.225.1.0/24
```

### Execução 1.11.11

**Estado:** FAIL conhecido.

O discovery V5 atingiu o timeout fixo de 900 segundos ao processar o `/16`. Nenhuma escrita foi executada no NetBox.

### Correção 1.11.12/1.11.13

**Estado:** CI PASS / NOT LIVE no DCM até nova execução completa.

Cobertura automatizada:

- divisão do `/16` em lotes `/24`;
- eliminação de sobreposição;
- paralelismo controlado;
- timeout e retry por lote;
- portas de infraestrutura, CFTV e OT;
- entrada direta e Runner apontando para Discovery V6;
- execução sem escrita quando não existe `--apply`.

## Auto-update e schedulers — 1.11.14

**Estado:** CI PASS / NOT LIVE até validação em cliente.

Contrato validado por regressão:

- instalador habilita `netbox-discovery-update.timer`;
- update timer é diário, persistente e possui atraso aleatório;
- scheduler Network inicia o update timer como dependência;
- scheduler Hypervisor inicia o update timer como dependência;
- não utiliza `Also=`, evitando que a desativação da coleta desligue atualizações;
- `automation.apply` continua preservado e não é ativado pela atualização.

## Documentação — 1.11.14

**Estado:** CI PASS.

A release só pode ser publicada quando a versão exata estiver presente em:

```text
README.md
docs/MANUAL.md
docs/COMANDOS-RAPIDOS.md
docs/HOMOLOGACAO.md
RELEASE-NOTES.md
SECURITY.md
docs/PATCH-1.11.14.md
```

## Critério para LIVE PASS da 1.11.14

No DCM:

```text
Discovery LARGE-CIDR concluído
PLAN gerado
NetBox write: NÃO
nenhum lote com falha definitiva
sem scheduler APPLY habilitado
```

Depois disso, o PLAN deve ser revisado antes de qualquer `--apply`.
