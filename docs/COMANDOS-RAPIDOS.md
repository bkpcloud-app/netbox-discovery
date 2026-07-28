# netbox-discovery 1.10.14 — Comandos rápidos

## Atualizar e executar a finalização

```bash
netbox-discovery update run
netbox-discovery version
netbox-discovery run --apply
```

O próprio `run --apply` executa descoberta, PLAN, preflight global, import, reparo seguro e audit. Não é necessário executar um dry-run separado quando a release final já foi autorizada para a homologação live.

## Saída esperada antes da escrita

```text
Planner: 4.4-product
READY/CREATE: ...
READY/UPDATE_SAFE: ...
READY/REPAIR_SAFE: ...

PREFLIGHT GLOBAL FINALIZE: OK
NetBox write até aqui: NÃO
REPAIR JOURNAL: ...
```

## MD32xx

```text
10.x.x.56 + 10.x.x.57
mesmo sysObjectID exato
mesmo sysName
exatamente dois endpoints consecutivos
→ 1 STORAGE
→ MGMT + MGMT-2
```

Sem todas as evidências, continua `REVIEW/BLOCKED`.

## Device duplicado de VM

Saída do PLAN:

```text
READY/REPAIR_SAFE
Device ID <id> -> VM ID <id>
IP -> VM interface ID <id>
```

Proteções:

```text
Device/interface/IP criados pelo produto
sem serial/rack/location/cluster/cabos/objetos relacionados
VM e interface únicas
IP único
```

Ação:

```text
move IP para a VM
→ define primary IPv4 se vazio
→ remove somente o Device duplicado criado pelo produto
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
Status: PASS
Assets FAIL: 0
Checks FAIL: 0
```

Relatórios:

```text
/opt/netbox-discovery/reports/<SITE>-repair-journal-*.json
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
