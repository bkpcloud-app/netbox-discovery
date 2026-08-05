# netbox-discovery 1.11.18 — Matriz de Homologação

## Estados

```text
LIVE PASS     = validado ao vivo com evidência
LIVE PARTIAL  = parte relevante validada
CI PASS       = regressões automatizadas passaram
NOT LIVE      = ainda não validado em ambiente real
```

CI PASS não substitui LIVE PASS.

## FBA

**Estado:** LIVE PASS como referência funcional.

```text
BLOCKED: 0
Assets FAIL: 0
Checks FAIL: 0
Scheduler Network: ENABLED
APPLY: NÃO
```

## DCM

**Estado:** LIVE PARTIAL.

Validado:

- Discovery V6 em redes grandes;
- 109 hosts e 100 assets no ciclo observado;
- dry-run sem escrita;
- relatório nativo do PLAN;
- write guard calculado sobre decisões finais;
- scheduler Network desabilitado durante homologação.

PLAN da 1.11.17:

```text
READY: 12
DELEGATED: 43
REVIEW: 26
BLOCKED: 19
WRITE GUARD: BLOCK
eligible_total: 17
live_devices: 13
change_percent: 131%
violação: PERCENT=131%>20%
```

Dos 19 bloqueados:

```text
17 = somente limite percentual
2  = DUPLICATE_DESIRED_NAME / RECONCILE_REVIEW_CANDIDATE
```

Os dois conflitos reais são:

```text
10.28.1.20
10.28.1.25
```

## Estado da 1.11.18

**Estado inicial:** CI PASS / NOT LIVE até novo PLAN do DCM.

Contrato:

```text
base < 50 Devices
→ SMALL_SITE_BOOTSTRAP_ABSOLUTE_ONLY
→ percentual adiado
→ limites absolutos obrigatórios

base >= 50 Devices
→ ABSOLUTE_AND_PERCENT
→ percentual ativo
```

Regressões obrigatórias:

```text
17 CREATE finais sobre base 13 → PASS pelo bootstrap
26 CREATE finais sobre base 13 → BLOCK por CREATE=26>25
21 UPDATE_SAFE sobre base 100 → BLOCK por PERCENT=21%>20%
REVIEW/DELEGATED/BLOCKED/READY-NOOP → fora de eligible_total
```

Pendente no DCM:

- atualizar para 1.11.18;
- gerar novo dry-run;
- confirmar `WRITE GUARD: PASS` com política de bootstrap;
- confirmar que apenas os dois conflitos Kubernetes permanecem BLOCKED;
- revisar os 17 READY/CREATE antes de qualquer APPLY;
- manter scheduler desabilitado até convergência.

## Critérios para liberar APPLY

```text
Self-test: PASS
Check: PASS
WRITE GUARD: PASS
política exibida corretamente
BLOCKED reais analisados
READY/CREATE revisados
Erros: 0
Assets FAIL: 0
Checks FAIL: 0
PLAN posterior convergente
```
