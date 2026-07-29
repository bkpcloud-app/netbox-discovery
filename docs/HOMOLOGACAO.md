# netbox-discovery 1.10.19 — Matriz de Homologação

## Estados

```text
LIVE PASS     = validado ao vivo com evidência
LIVE PARTIAL  = parte relevante validada, fluxo completo pendente
CI PASS       = regressões automatizadas passaram
NOT LIVE      = ainda não validado ao vivo
```

CI PASS não equivale a LIVE PASS.

## Hypervisor

**Estado:** LIVE PASS.

```text
Objetos comparados: 282
OK: 282
MISMATCH: 0
MISSING: 0
AMBIGUOUS: 0
COMPARE STATUS: OK
```

O bloco Hypervisor está encerrado e não depende da homologação Network 1.10.19.

## Network — Site DCM

**Estado:** LIVE PASS em 29/07/2026 com a 1.10.18.

```text
ownership Hypervisor → PASS
Dell switches → PASS
MD32xx multi-endpoint → PASS
ME4/ME5 storage → PASS
preflight global → PASS
IMPORT normal → PASS
MAC RECONCILE → PASS
REPAIR_SAFE de Device duplicado de VM → PASS
idempotência → PASS
Assets FAIL: 0
Checks FAIL: 0
```

## Network — Site FBA, execução de origem 1.10.18

**Estado do ciclo 1.10.18:** LIVE PASS em 29/07/2026.

### Descoberta e plano

```text
Hosts ativos: 288
Assets reconciliados: 283
Devices antes: 175
READY: 175
REVIEW: 69
BLOCKED: 2
READY/CREATE: 4
READY/UPDATE_SAFE: 0
READY/NOOP: 171
DELEGATED/HYPERVISOR: 37
```

### APPLY

```text
PREFLIGHT GLOBAL FINALIZE: OK
Assets READY processados: 175/175
Runtime blocked: 0
Erros: 0
MAC RECONCILE: PASS
Devices após: 179
```

### Audit e idempotência

```text
Status: PASS_WITH_WARNINGS
Assets PASS: 170
Assets WARN: 5
Assets FAIL: 0
Checks PASS: 1809
Checks WARN: 11
Checks FAIL: 0
READY/CREATE posterior: 0
READY/UPDATE_SAFE posterior: 0
READY/NOOP posterior: 175
```

O ciclo foi seguro e idempotente. As 69 pendências e 2 bloqueios não escreveram.

### Lacunas de qualidade encontradas no FBA

```text
impressoras com Generic Printer
servidores/appliances com Unknown Server
Moxa NP5210_4618 como WEB_APPLIANCE LOW
2 switches físicos HIGH com o mesmo sysName SW-BA17
Ubiquiti e Topdata existentes degradados por coleta fraca
Dell Inc. versus Dell gerando drift falso
```

Essas lacunas motivaram a 1.10.19. Não são falhas do APPLY 1.10.18.

## Network 1.10.19 — qualidade de identidade

**Estado:** NOT LIVE até a execução final no FBA.

### Funções novas cobertas por CI

```text
Printer-MIB → fabricante/modelo/serial explícitos
Moxa NPort 5210 por sysObjectID exato
Device Type genérico do produto → tipo exato HIGH
preservação de identidade live forte sobre coleta fraca
aliases de fabricante sem drift falso
colisão de sysName resolvida somente por serial/MAC forte
revalidação do upgrade no importer antes do PATCH
```

### Critério de LIVE PASS

Executar uma única vez no FBA:

```bash
netbox-discovery update run
netbox-discovery version
netbox-discovery run --apply
```

A homologação exige:

```text
Versão: 1.10.19
PREFLIGHT GLOBAL FINALIZE: OK
Runtime blocked: 0
Erros: 0
MAC RECONCILE: PASS
Assets FAIL: 0
Checks FAIL: 0
preview posterior sem READY/CREATE, READY/UPDATE_SAFE ou READY/REPAIR_SAFE elegível
```

Também deve ser verificado no relatório:

```text
Printer-MIB somente quando houver resposta real
UPDATE_SAFE apenas em Device criado pelo produto e ainda genérico
objetos manuais/específicos preservados
SW-BA17 distintos por nome determinístico ou ainda bloqueados com motivo seguro
nenhuma regressão em DELEGATED Hypervisor
```

Até essa evidência, o estado correto da release é **CI/NOT LIVE**.

## Segurança operacional

```text
netbox-discovery run          → dry-run
netbox-discovery run --apply  → escreve somente READY
REVIEW/BLOCKED/DELEGATED      → não escrevem
DELETE de VM                  → proibido
Device Type manual/específico → não substituído
```

## Schedulers

```text
Auto-update stable: LIVE PASS
Network scheduler: DISABLED
Hypervisor scheduler: DISABLED
```

A habilitação dos schedulers é decisão operacional separada.
