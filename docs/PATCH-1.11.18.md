# netbox-discovery 1.11.18

## Problema observado no DCM

O PLAN final apresentou:

```text
eligible_total=17
live_devices=13
change_percent=131%
PERCENT=131%>20%
```

As 17 mudanças estavam abaixo do limite absoluto de 25 criações, mas a regra percentual tornava impossível o primeiro inventário de um site com base pequena.

Dois registros continuavam bloqueados por motivo real:

```text
10.28.1.20 → DUPLICATE_DESIRED_NAME
10.28.1.25 → DUPLICATE_DESIRED_NAME
```

## Correção

Planner V11 passa a usar duas políticas:

```text
base < 50 Devices
→ SMALL_SITE_BOOTSTRAP_ABSOLUTE_ONLY

base >= 50 Devices
→ ABSOLUTE_AND_PERCENT
```

No bootstrap, somente o percentual é adiado. Os limites absolutos continuam obrigatórios:

```text
CREATE: 25
UPDATE_SAFE: 50
REPAIR_SAFE_VM_DUPLICATE: 20
TOTAL: 75
```

A base mínima padrão é 50 e pode ser configurada com:

```text
NETBOX_DISCOVERY_PERCENT_MIN_BASE
```

## Relatório nativo

`netbox-discovery plan summary` e as visões detalhadas passam a mostrar:

```text
WRITE GUARD POLÍTICA
percentual=ATIVO|ADIADO
base mínima
```

## Segurança

A versão não habilita APPLY e não reduz limites absolutos.

Continuam sem escrita:

```text
REVIEW
DELEGATED
BLOCKED
READY/NOOP
DUPLICATE_DESIRED_NAME
conflitos de identidade
```

## Regressões

```text
17 CREATE sobre base 13  → PASS pelo bootstrap
26 CREATE sobre base 13  → BLOCK por CREATE=26>25
21 UPDATE sobre base 100 → BLOCK por PERCENT=21%>20%
```

A política percentual volta automaticamente quando a base atinge 50 Devices.
