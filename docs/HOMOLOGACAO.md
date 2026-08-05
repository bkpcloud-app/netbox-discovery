# netbox-discovery 1.11.16 — Matriz de Homologação

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
- scheduler Network desabilitado durante homologação;
- auto-update ativo.

PLAN observado antes da 1.11.16:

```text
READY: 12
DELEGATED: 43
REVIEW: 11
BLOCKED: 34
NetBox write: NÃO
```

Pendente:

- atualizar para 1.11.16;
- validar `netbox-discovery plan summary`;
- analisar `plan blocked` e `plan review`;
- reduzir BLOCKED a zero antes de APPLY;
- APPLY controlado e auditoria posterior, se aprovados;
- habilitar scheduler somente após convergência.

## Estado da 1.11.16

**Estado inicial:** CI PASS / NOT LIVE.

### Contrato novo

```text
netbox-discovery plan summary
netbox-discovery plan blocked
netbox-discovery plan review
netbox-discovery plan ready
netbox-discovery plan delegated
```

Os comandos devem:

- selecionar o último PLAN do site configurado;
- mostrar Run ID e `NetBox write`;
- agrupar decisões, ações e motivos;
- listar detalhes sem alterar o NetBox;
- aceitar `--json`;
- preservar o comportamento normal de `netbox-discovery plan` para geração do PLAN.

### Correção de status

Para último RUN dry-run, o status deve apresentar:

```text
IMPORT: NÃO EXECUTADO NESTE RUN (dry-run)
AUDIT: NÃO EXECUTADO NESTE RUN (dry-run)
```

Não deve exibir IMPORT/AUDIT históricos como se pertencessem ao RUN atual.

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

A 1.11.16 não muda regras de escrita:

```text
READY/CREATE      → somente com --apply
READY/UPDATE_SAFE → somente com --apply
READY/NOOP        → sem escrita
DELEGATED         → sem escrita
REVIEW            → sem escrita
BLOCKED           → sem escrita
PLAN reports      → somente leitura
```
