# netbox-discovery 1.10.19 — Comandos rápidos

## Atualizar e executar a validação live final

```bash
netbox-discovery update run
netbox-discovery version
netbox-discovery run --apply
```

Não existe etapa manual no NetBox entre esses comandos.

## Versões esperadas

```text
Versão: 1.10.19
Discovery: 4.3-product
Classifier: 5.1-product
Planner: 4.8-product
Importer: 5.7-product
Auditor: 6.6-product
Pipeline: 2.9-product
Runner: 2.8-product
```

## Melhorias que devem aparecer no PLAN

```text
Printer-MIB: name=... serial=...
Moxa / NPort 5210 / INDUSTRIAL_COMMUNICATION
PRODUCT_GENERIC_DEVICE_TYPE_UPGRADE
LIVE_IDENTITY_PRESERVED_OVER_WEAK_OBSERVATION
COLLISION_SAFE_NAME_FROM_STRONG_IDENTITY
```

Nem todos os marcadores precisam existir em todo site. Eles aparecem somente quando a evidência correspondente for encontrada.

## Escrita permitida

```text
novo objeto físico HIGH                → READY/CREATE
tipo genérico do produto para tipo exato HIGH → READY/UPDATE_SAFE
objeto existente forte com coleta fraca → READY/NOOP
objeto Hypervisor                      → DELEGATED/NOOP
evidência insuficiente                 → REVIEW
evidência conflitante                  → BLOCKED
```

## Proteção do Device Type

```text
Device manual                          → não altera
tipo atual específico                  → não altera
confidence diferente de HIGH           → não altera
fabricante/modelo genérico             → não altera
Device criado pelo produto + tipo genérico + identidade exata → UPDATE_SAFE
```

## Audit esperado

```text
PREFLIGHT GLOBAL FINALIZE: OK
Runtime blocked: 0
Erros: 0
MAC RECONCILE: PASS
Assets FAIL: 0
Checks FAIL: 0
READY/CREATE após audit: 0
READY/UPDATE_SAFE após audit: 0
READY/REPAIR_SAFE após audit: 0
```

`PASS_WITH_WARNINGS` continua válido somente com `Assets FAIL: 0` e `Checks FAIL: 0`.

## Status

```bash
netbox-discovery version
netbox-discovery status
netbox-discovery self-test
netbox-discovery health
```

## Política

```text
READY/CREATE                    → escreve com --apply
READY/UPDATE_SAFE               → escreve com --apply
READY/REPAIR_SAFE_VM_DUPLICATE  → escreve após preflight global
DELEGATED                       → não escreve
REVIEW                          → não escreve
BLOCKED                         → não escreve
DELETE de VM                    → NÃO
```

CI PASS não significa LIVE PASS.
