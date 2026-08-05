# netbox-discovery 1.11.15 — Matriz de Homologação

## Estados

```text
LIVE PASS     = validado ao vivo com evidência
LIVE PARTIAL  = parte relevante validada
CI PASS       = regressões automatizadas passaram
NOT LIVE      = ainda não validado em ambiente real
```

CI PASS não substitui LIVE PASS.

## Linha de base FBA

**Estado:** LIVE PASS na 1.11.10/1.11.11, mantido como referência funcional.

```text
READY: 188
REVIEW: 64
BLOCKED: 0
READY/CREATE: 0
READY/UPDATE_SAFE: 0
READY/NOOP: 188
Assets FAIL: 0
Checks FAIL: 0
Audit: PASS_WITH_WARNINGS
```

## DCM

**Estado atual:** LIVE PARTIAL.

Validado:

- configuração preservada;
- atualização até 1.11.14;
- self-test e check PASS;
- Discovery V6 carregado;
- auto-update timer ativo;
- scheduler Network mantido desabilitado durante homologação;
- nenhum APPLY executado no ciclo de redes grandes.

Pendente:

- novo dry-run completo com a lista final de redes;
- análise do PLAN;
- APPLY controlado, se aprovado;
- auditoria posterior;
- ativação do scheduler Network.

## Estado da 1.11.15

**Estado:** CI PASS / NOT LIVE até atualização e primeira execução automática observada em cliente.

### Contrato novo

Cada serviço agendado executa:

```text
UPDATE PREFLIGHT
→ valida versão stable
→ instala e testa quando necessário
→ rollback/quarentena em falha de candidato
→ coleta com a versão instalada válida
```

Falha temporária de acesso ao GitHub não cancela a coleta. O evento deve permanecer visível no journal e no estado do updater.

### Critérios de LIVE PASS da 1.11.15

```text
versão instalada 1.11.15 ou superior
update scheduler ENABLED
serviço automático mostra update preflight antes do RUN
sem update disponível: coleta inicia normalmente
com GitHub indisponível: coleta continua na versão atual
com update válido: instala, self-test PASS e coleta inicia
APPLY permanece conforme config, sem alteração pelo updater
```

## Critérios gerais para liberar scheduler

```text
Self-test: PASS
Check: PASS
BLOCKED: 0
WRITE GUARD: PASS
Erros: 0
Assets FAIL: 0
Checks FAIL: 0
PLAN posterior convergente
```

## Segurança

A 1.11.15 não muda regras de escrita:

```text
READY/CREATE      → somente com --apply
READY/UPDATE_SAFE → somente com --apply
READY/NOOP        → sem escrita
DELEGATED         → sem escrita
REVIEW            → sem escrita
BLOCKED           → sem escrita
```
