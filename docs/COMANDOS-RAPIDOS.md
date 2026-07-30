# netbox-discovery 1.11.0 — Comandos rápidos

## Atualizar e executar primeiro em dry-run

```bash
netbox-discovery update run
netbox-discovery version
netbox-discovery self-test
netbox-discovery run
```

Depois de revisar o PLAN:

```bash
netbox-discovery run --apply
```

## Versões esperadas

```text
Versão: 1.11.0
Discovery: 4.4-product
Classifier: 5.2-product
Planner: 4.9-product
Importer: 5.8-product
Auditor: 6.7-product
Pipeline: 3.0-product
Runner: 3.0-product
Identity engine: 1.0-product
```

## Informações novas no PLAN

```text
Nome efetivo/observado
Autoridade do nome
Discovery UID
Natureza física/virtual
Proveniência de identidade
Dados estruturados do protocolo
DELEGATED_VM/PASS com VM/interface/cluster/host
WRITE GUARD
Próxima evidência sugerida
```

Nem todos os marcadores aparecem em todo site. Eles dependem da evidência encontrada.

## Escrita permitida

```text
novo objeto físico HIGH                       → READY/CREATE
identidade exata sobre placeholder do produto → READY/UPDATE_SAFE
objeto existente forte com coleta fraca       → READY/NOOP
VM do inventário central                      → DELEGATED/NOOP
candidato virtual sem VM central               → REVIEW/NOOP
evidência insuficiente                         → REVIEW
evidência conflitante ou impacto anormal       → BLOCKED
```

## Nome manual

```text
Nome existente no NetBox   → preservado
Nome observado por SNMP    → exibido separadamente
PATCH automático de name   → bloqueado no importer
```

## Industrial e CFTV

Procure no relatório por:

```text
Siemens S7 structured identity
EtherNet/IP CIP Identity
BACnet device identity
Modbus device identification
ONVIF/WS-Discovery identity
CCTV model/vendor fingerprint
```

## Virtualização centralizada na filial

```text
Função desta instalação: network_proxy
Inventário de virtualização: CENTRALIZED
Hypervisor local: NÃO REQUERIDO
```

Não configure o vCenter em cada filial.

## Write guard

```text
WRITE GUARD: PASS
```

Se aparecer `BLOCK`, nenhuma ação elegível é escrita. Limites opcionais:

```bash
export NETBOX_DISCOVERY_MAX_CREATE=100
export NETBOX_DISCOVERY_MAX_UPDATE=150
export NETBOX_DISCOVERY_MAX_REPAIR=20
export NETBOX_DISCOVERY_MAX_TOTAL_CHANGES=200
export NETBOX_DISCOVERY_MAX_CHANGE_PERCENT=50
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

`PASS_WITH_WARNINGS` só é válido com `Assets FAIL: 0` e `Checks FAIL: 0`.

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
