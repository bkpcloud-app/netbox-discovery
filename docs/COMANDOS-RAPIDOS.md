# netbox-discovery 1.11.23 — Comandos rápidos

## Atualizar e validar

```bash
netbox-discovery update run
netbox-discovery version
netbox-discovery check
netbox-discovery status
```

## Analisar o último PLAN

```bash
netbox-discovery plan summary
netbox-discovery plan blocked
netbox-discovery plan review
netbox-discovery plan ready
netbox-discovery plan delegated
```

Todos são somente leitura.

## Colocar a unidade em produção

Depois da aprovação do PLAN:

```bash
netbox-discovery go-live
```

O comando executa IMPORT, AUDIT, novo PLAN, valida convergência e habilita o scheduler Network com `APPLY=NÃO`.

Resultado esperado:

```text
GO-LIVE: PASS
SCHEDULER NETWORK: ENABLED
APPLY AUTOMÁTICO: NÃO
```

## Identidade para novos Devices

```text
Discovery UID SERIAL ou MGMT-MAC → pode permanecer READY
Discovery UID WEAK               → REVIEW/NOOP
```

## Propriedade global de MAC

```text
MAC sem vínculo                          → permitido
MAC no mesmo Device existente           → reutiliza a interface live
MAC em outro Device/VM/objeto            → BLOCKED/NOOP
nome da interface live diferente        → MAC tem precedência, sem nova interface
mesma MAC repetida no mesmo registro     → preserva a mesma interface
consulta global indisponível             → APPLY bloqueado
```

## Dry-run

```bash
netbox-discovery run
```

## APPLY manual excepcional

```bash
netbox-discovery import --apply
```

No fluxo padrão de unidade nova, use `netbox-discovery go-live`.

Se houver erro depois de `PREFLIGHT: OK`, trate como possível escrita parcial e recalcule o PLAN.

## Scheduler

```bash
netbox-discovery scheduler enable
netbox-discovery scheduler disable
netbox-discovery scheduler status
```

## Segurança

```text
run               = sem escrita
go-live           = escrita READY + AUDIT + convergência + scheduler APPLY=NÃO
import --apply     = escrita manual READY após proteções
WEAK new Device   = REVIEW/NOOP
MAC conflict      = BLOCKED/NOOP
same owner MAC    = reutiliza interface
REVIEW            = não escreve
DELEGATED         = não escreve
BLOCKED           = não escreve
```
