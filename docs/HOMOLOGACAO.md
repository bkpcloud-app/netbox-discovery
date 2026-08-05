# netbox-discovery 1.11.17 — Matriz de Homologação

## Estados

```text
LIVE PASS     = validado ao vivo com evidência
LIVE PARTIAL  = parte relevante validada
CI PASS       = regressões automatizadas passaram
NOT LIVE      = ainda não validado em ambiente real
```

CI PASS não substitui LIVE PASS.

## Linha de base FBA

**Estado:** LIVE PASS como referência funcional.

```text
BLOCKED: 0
Assets FAIL: 0
Checks FAIL: 0
Audit: PASS_WITH_WARNINGS
Scheduler Network: ENABLED
APPLY: NÃO
Auto-update preflight: configurado
```

## DCM

**Estado atual:** LIVE PARTIAL.

Validado:

- configuração e redes preservadas;
- Discovery V6 concluído em redes grandes;
- dry-run concluído sem escrita no NetBox;
- 109 hosts descobertos e 100 assets reconciliados no ciclo observado;
- relatório nativo do PLAN funcionando na 1.11.16;
- scheduler Network desabilitado durante homologação;
- auto-update ativo.

PLAN observado:

```text
READY: 12
DELEGATED: 43
REVIEW: 11
BLOCKED: 34
NetBox write: NÃO
```

O relatório revelou:

```text
WRITE_GUARD_LIMIT_EXCEEDED: CREATE=32>25, PERCENT=246%>20%
```

Mas o resumo final apresentava apenas 13 ações `CREATE`, todas fora de READY:

```text
REVIEW/CREATE: 11
BLOCKED/CREATE: 2
READY/CREATE: 0
```

Diagnóstico: o guard de uma camada intermediária foi aplicado antes das políticas finais transformarem candidatos fracos em `REVIEW`. Esse é o defeito corrigido na 1.11.17.

Pendente no DCM:

- atualizar para 1.11.17;
- executar novo dry-run completo;
- confirmar write guard calculado sobre decisões finais;
- comparar novo PLAN com o ciclo anterior;
- analisar BLOCKED e REVIEW restantes;
- não executar APPLY enquanto houver inconsistência ou mudança não aprovada;
- habilitar scheduler somente após convergência.

## Estado da 1.11.17

**Estado inicial:** CI PASS / NOT LIVE até novo dry-run observado no DCM.

### Contrato corrigido

```text
camadas intermediárias não aplicam guard mutável
→ todas as políticas finais são executadas
→ Planner V11 consolida decisões
→ write guard é aplicado uma única vez
```

Critérios específicos:

```text
32 candidatos intermediários sobre 13 Devices
→ reclassificados para REVIEW/NOOP
→ WRITE GUARD PASS
→ eligible_total=0
→ nenhum falso WRITE_GUARD_LIMIT_EXCEEDED
```

Controle positivo:

```text
26 READY/CREATE finais
→ limite CREATE=25 excedido
→ WRITE GUARD BLOCK
→ todos os 26 bloqueados
```

O relatório `netbox-discovery plan summary` deve mostrar o guard efetivo, incluindo elegíveis, base, percentual e violações.

## Critérios gerais para liberar scheduler

```text
Self-test: PASS
Check: PASS
write guard calculado sobre decisões finais
sem falso GLOBAL_WRITE_GUARD
WRITE GUARD: PASS
Erros: 0
Assets FAIL: 0
Checks FAIL: 0
PLAN posterior convergente
```

## Segurança

A 1.11.17 não reduz os limites de proteção:

```text
READY/CREATE      → somente com --apply
READY/UPDATE_SAFE → somente com --apply
READY/NOOP        → sem escrita
DELEGATED         → sem escrita
REVIEW            → sem escrita
BLOCKED           → sem escrita
PLAN reports      → somente leitura
```

A correção altera apenas o momento do cálculo: o guard protege as mudanças finais reais, não candidatos intermediários que não serão escritos.
