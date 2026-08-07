# netbox-discovery 1.11.24 — Initial-site bootstrap guard

## Objetivo

Corrigir o bloqueio indevido de unidades praticamente vazias que possuem mais de 25 equipamentos físicos fortemente identificados no primeiro inventário.

## Regra

O write guard passa a distinguir três estágios:

```text
0–9 Devices existentes   → INITIAL_SITE_BOOTSTRAP_ABSOLUTE_ONLY
                            CREATE máximo: 50
                            TOTAL máximo: 75

10–49 Devices existentes → SMALL_SITE_BOOTSTRAP_ABSOLUTE_ONLY
                            CREATE máximo: 25
                            TOTAL máximo: 75

50+ Devices existentes   → ABSOLUTE_AND_PERCENT
                            CREATE máximo: 25
                            percentual máximo: 20%
```

Os limites de `UPDATE_SAFE`, `REPAIR_SAFE_VM_DUPLICATE` e `TOTAL` não foram ampliados.

## Caso FVI

Com 2 Devices existentes e 27 novos candidatos físicos com identidade estável, o PLAN deixa de bloquear por `CREATE=27>25` e passa a aceitar o bootstrap inicial dentro do teto de 50.

A mudança não transforma `REVIEW` em `READY`, não relaxa identidade estável, não altera proteção global de MAC e não permite escrita de `BLOCKED`, `REVIEW` ou `DELEGATED`.

## Operação

```bash
netbox-discovery update run
netbox-discovery run
```

Depois da revisão do novo PLAN, o fechamento continua sendo:

```bash
netbox-discovery go-live
```
