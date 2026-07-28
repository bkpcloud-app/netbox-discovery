# netbox-discovery 1.10.18 — Matriz de Homologação

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

## Network — funções LIVE PASS

```text
ownership por IP → DELEGATED
Dell N2024/PCT7024/S4128F-ON → NETWORK_SWITCH/HIGH
VM por nome único → DELEGATED
Dell MD3200BKP .56/.57 → 1 STORAGE com MGMT + MGMT-2
preflight global base → PASS
IMPORT normal → PASS
MAC RECONCILE de Devices → PASS
```

## APPLY real da 1.10.17 — 28/07/2026, Site DCM

### PLAN

```text
Planner: 4.7-product
READY/CREATE: 0
READY/UPDATE_SAFE: 0
READY/REPAIR_SAFE: 1
DELEGATED/HYPERVISOR: 42
REVIEW: 1
BLOCKED: 0
```

### SRV-AE11 — parte validada

**Estado:** LIVE PARTIAL.

A 1.10.17 validou ao vivo:

```text
Device ID 324
VM ID 359
interface MGMT criada na VM
MAC 00:50:56:9F:9E:70 criado/atribuído
primary_mac_address da interface definido
PREFLIGHT GLOBAL FINALIZE: OK
IMPORT normal: 12/12
MAC RECONCILE: PASS
```

A transferência do IP foi bloqueada pelo próprio NetBox:

```text
HTTP 400
Cannot reassign IP address while it is designated as the primary IP for the parent object
```

Resultado seguro:

```text
VM preservada
interface MGMT preservada
MAC VMware preservado
IP 10.1.1.111/24 permaneceu no Device
Device 324 permaneceu existente
nenhum DELETE do Device ocorreu
```

A causa confirmada foi ordem de operação: o IP ainda era `primary_ip4` do Device quando o PATCH tentou reatribuí-lo à VM interface.

## 1.10.18 — correção da ordem primary IP → reassignment

**Estado:** NOT LIVE até a execução final.

A nova ordem é:

```text
revalidar reparo
→ confirmar primary/oob vazio ou igual ao IP alvo
→ limpar primary_ip4/primary_ip6/oob_ip do Device
→ mover IP para virtualization.vminterface
→ definir primary_ip4 da VM
→ remover somente o Device duplicado
→ auditar
```

Proteção adicional:

```text
primary/oob apontando para outro IP
→ BLOCKED antes do IP move e antes do DELETE
```

## Única validação live da 1.10.18

```bash
netbox-discovery update run
netbox-discovery version
netbox-discovery run --apply
```

Critério de conclusão:

```text
Versão: 1.10.18
Planner: 4.7-product
READY/REPAIR_SAFE: 1 antes da escrita
PREFLIGHT GLOBAL FINALIZE: OK
PRIMARY_IP_CLEARED_BEFORE_MOVE
Reparos seguros concluídos: 1
Device ID 324 ausente
VM ID 359 preservada
uma única interface MGMT na VM
MAC 00:50:56:9F:9E:70 único nessa interface
IP 10.1.1.111/24 atribuído à virtualization.vminterface
VM primary IPv4 correto
novo PLAN: SRV-AE11 DELEGATED/NOOP
Assets FAIL: 0
Checks FAIL: 0
```

O `10.1.1.54` pode continuar `REVIEW`.

## Schedulers

```text
Auto-update stable: LIVE PASS
Network scheduler: DISABLED durante homologação
Hypervisor scheduler: DISABLED durante homologação
```
