# netbox-discovery 1.11.17 — Write guard final

## Origem

No dry-run do DCM, o relatório nativo apresentou:

```text
WRITE_GUARD_LIMIT_EXCEEDED:CREATE=32>25,PERCENT=246%>20%
```

O PLAN final, porém, não tinha nenhuma mudança `READY/CREATE`. As ações `CREATE` restantes pertenciam a `REVIEW` ou a bloqueios específicos e não poderiam ser escritas.

## Causa

Planner V9 Core aplicava o write guard antes de Planner V9, V10 e V11 terminarem as políticas de identidade. Os 32 candidatos intermediários eram convertidos para `BLOCKED/NOOP`, impedindo camadas posteriores de reclassificá-los corretamente para `REVIEW`.

Como as camadas superiores também chamavam o guard, o cálculo ocorria várias vezes, mas a primeira mutação já era irreversível naquele PLAN.

## Correção

Planner V11 suspende temporariamente o guard compartilhado durante a construção nas camadas internas e restaura a função mesmo se ocorrer exceção.

Depois executa:

```text
recuperação de colisões seguras
→ identidade idempotente
→ poda de pré-requisitos
→ write guard final único
```

## Resultado esperado

Cenário reproduzido do DCM:

```text
32 candidatos intermediários
13 Devices existentes
políticas finais → REVIEW/NOOP
WRITE GUARD: PASS
eligible_total: 0
change_percent: 0
```

Controle de segurança:

```text
26 READY/CREATE finais
limite CREATE: 25
WRITE GUARD: BLOCK
26 registros → BLOCKED/NOOP
```

## Diagnóstico nativo

`netbox-discovery plan summary` agora mostra:

```text
WRITE GUARD: PASS|BLOCK
elegíveis
base
percentual
violações
```

## Segurança

- nenhuma alteração em `automation.apply`;
- nenhum APPLY automático;
- nenhum aumento de limite;
- REVIEW, DELEGATED e BLOCKED continuam sem escrita;
- mudanças finais acima do limite continuam bloqueadas;
- relatório permanece somente leitura.

## Homologação DCM

Após instalar a 1.11.17, deve ser executado novo dry-run. O PLAN antigo não é recalculado automaticamente pela atualização. Somente um novo `netbox-discovery run` produzirá decisões com a ordem corrigida.
