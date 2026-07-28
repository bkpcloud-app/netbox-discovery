# netbox-discovery 1.10.16 — Comandos rápidos

## Atualizar e executar a finalização

```bash
netbox-discovery update run
netbox-discovery version
netbox-discovery run --apply
```

O próprio `run --apply` executa descoberta, PLAN, preflight global, import, reconciliação de MAC, garantia de MAC na interface única da VM, reparo seguro e audit.

## Saída esperada antes da escrita

```text
Planner: 4.6-product
READY/CREATE: ...
READY/UPDATE_SAFE: ...
READY/REPAIR_SAFE: ...

PREFLIGHT GLOBAL FINALIZE: OK
NetBox write até aqui: NÃO
REPAIR JOURNAL: ...
```

Para o caso de VM com uma única interface sem MAC:

```text
READY/REPAIR_SAFE | <nome> | Device ID <id> -> VM ID <id>
VM MAC: <mac> -> interface única ID <id>
Evidência VM MAC: VM única por nome + uma interface sem MAC + VMware MAC forte
```

## Reparo de Device duplicado de VM

Caminhos aceitos:

```text
MAC VMware corresponde exatamente a uma interface live
```

ou:

```text
VM única
+ exatamente uma interface live
+ interface sem outro MAC
+ exatamente um MAC VMware forte
+ MAC sem outro owner
```

Ação:

```text
cria/atribui MAC à virtualization.vminterface
→ define primary MAC da interface
→ move IP para a VM
→ define primary IPv4 se vazio
→ remove somente o Device duplicado criado pelo produto
```

VM com mais de uma interface permanece `BLOCKED`.

## Reconciliação de MAC de Devices

Depois do IMPORT normal:

```text
===== MAC RECONCILE =====
Status: PASS
JSON MAC: /opt/netbox-discovery/reports/<SITE>-mac-reconcile-*.json
```

O produto cria ou atribui o MAC esperado mesmo quando o IP já estava vinculado à interface correta. MAC pertencente a outro objeto bloqueia no preflight.

## MD32xx

```text
10.x.x.56 + 10.x.x.57
mesmo sysObjectID exato
mesmo sysName
exatamente dois endpoints consecutivos
→ 1 STORAGE
→ MGMT + MGMT-2
```

## Falha de preflight

```text
PREFLIGHT GLOBAL FINALIZE: BLOQUEADO
NetBox write: NÃO
```

Não corrigir manualmente e não repetir cegamente.

## Recuperação

```text
RECOVERY_AFTER_IP_MOVE
```

Indica que o IP já está na VM e o produto concluirá somente a limpeza segura restante após novo preflight.

## Audit

```text
===== AUDIT FINALIZE RESULTADO =====
Status: PASS ou PASS_WITH_WARNINGS
Assets FAIL: 0
Checks FAIL: 0
```

Para o fallback de interface única, o audit também exige:

```text
REPAIR_VM_MAC_OK
```

Relatórios:

```text
/opt/netbox-discovery/reports/<SITE>-repair-journal-*.json
/opt/netbox-discovery/reports/<SITE>-mac-reconcile-*.json
/opt/netbox-discovery/reports/<SITE>-import-finalize-*.json
/opt/netbox-discovery/reports/<SITE>-audit-finalize-*.json
```

## Dry-run normal

```bash
netbox-discovery run
```

## Hypervisor

```bash
netbox-discovery hypervisor check
netbox-discovery hypervisor run
netbox-discovery hypervisor run --compare
netbox-discovery hypervisor run --apply
```

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
READY/NOOP                      → não altera
DELEGATED                       → não escreve
REVIEW                          → não escreve
BLOCKED                         → não escreve
DELETE genérico                 → NÃO
```

CI PASS não significa LIVE PASS.
