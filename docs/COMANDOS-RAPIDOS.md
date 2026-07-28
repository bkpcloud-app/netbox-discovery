# netbox-discovery 1.10.18 — Comandos rápidos

## Atualizar e concluir o reparo

```bash
netbox-discovery update run
netbox-discovery version
netbox-discovery run --apply
```

## Estado parcial esperado antes da correção

```text
VM ID 359 preservada
interface MGMT criada
MAC 00:50:56:9F:9E:70 atribuído
IP 10.1.1.111/24 ainda no Device 324
Device 324 ainda existente
```

Não criar interface ou mover IP manualmente.

## Saída esperada na 1.10.18

```text
Versão: 1.10.18
Planner: 4.7-product
READY/REPAIR_SAFE: 1
PREFLIGHT GLOBAL FINALIZE: OK
PRIMARY_IP_CLEARED_BEFORE_MOVE
Reparos seguros concluídos: 1
```

O produto executa:

```text
limpar primary_ip4 do Device
→ mover IP para a interface MGMT existente da VM
→ definir primary_ip4 da VM
→ remover somente o Device duplicado
→ AUDIT FINALIZE
```

## Proteção nova

```text
primary_ip4/primary_ip6/oob_ip vazio ou igual ao IP alvo → pode limpar
qualquer campo apontando para outro IP                  → BLOCKED antes da escrita
```

## Audit esperado

```text
REPAIR_DUPLICATE_DEVICE_REMOVED
REPAIR_IP_ON_VM
REPAIR_VM_PRIMARY_IP_OK
REPAIR_IDEMPOTENCY_DELEGATED
Assets FAIL: 0
Checks FAIL: 0
```

A interface já criada pela 1.10.17 deve ser reutilizada. Não deve aparecer outra `MGMT`.

## REVIEW residual

```text
10.1.1.54 → REVIEW
```

Pode permanecer assim sem impedir a conclusão.

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
