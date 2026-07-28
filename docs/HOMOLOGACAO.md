# netbox-discovery 1.10.14 — Matriz de Homologação

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

## Network — funções já LIVE PASS

```text
1.10.10 ownership por IP → DELEGATED
1.10.10 Dell N2024/PCT7024/S4128F-ON → NETWORK_SWITCH/HIGH
1.10.12 VM por nome único → DELEGATED
1.10.12 Device físico + VM → BLOCKED
1.10.13 precedência de ownership por IP → DELEGATED preservado
```

## Primeiro APPLY Network real

**Estado:** LIVE PARTIAL.

```text
PREFLIGHT: OK
Assets READY processados: 13
Runtime blocked: 0
Erros: 0
NetBox write: SIM
```

Idempotência:

```text
READY/CREATE: 0
READY/UPDATE_SAFE: 0
READY/NOOP: 13
```

O APPLY revelou um Device físico duplicado para uma VM quando uma coleta perdeu temporariamente o MAC VMware.

## Estado live imediatamente antes da 1.10.14

Dry-run 1.10.13:

```text
Planner: 4.3-product
READY/CREATE: 0
READY/UPDATE_SAFE: 0
DELEGATED/HYPERVISOR: 42
REVIEW: 1
BLOCKED: 3
```

Pendências:

```text
Web Appliance de baixa confiança → REVIEW
Dell MD3200BKP com dois endpoints → BLOCKED
Device físico duplicado de uma VM → BLOCKED
```

## 1.10.14 — Dell MD32xx dual-controller

**Estado:** NOT LIVE até a execução final.

Classificação exige:

```text
sysObjectID=.1.3.6.1.4.1.674.10893.2.31
sysName não genérico
```

Merge exige:

```text
exatamente dois endpoints
mesma identidade OID/nome
STORAGE/HIGH
sem serial conflitante
IPs consecutivos
```

Resultado esperado:

```text
1 Device STORAGE
2 interfaces MGMT
2 IPs
```

Regressões cobrem classificação e proteção contra par inválido.

## 1.10.14 — REPAIR_SAFE_VM_DUPLICATE

**Estado:** NOT LIVE até a execução final.

O planner promove o conflito para READY apenas se todas as proteções comprovarem que o Device duplicado foi criado integralmente pelo produto e não recebeu nenhum vínculo manual.

Esperado:

```text
READY/REPAIR_SAFE: 1
Device duplicado → VM inequívoca
IP → virtualization.vminterface
VM primary IPv4 preenchido se vazio
Device duplicado removido
```

Nenhuma VM é removida.

## 1.10.14 — preflight global

**Estado:** NOT LIVE.

Antes da primeira escrita:

```text
valida READY normal
valida REPAIR_SAFE
relê relações live
PREFLIGHT GLOBAL FINALIZE: OK
NetBox write até aqui: NÃO
REPAIR JOURNAL criado
```

Qualquer erro aborta tudo antes da etapa final.

## 1.10.14 — recuperação parcial

**Estado:** CI/NOT LIVE.

```text
IP já na VM + Device duplicado ainda existente
→ RECOVERY_AFTER_IP_MOVE
→ novo preflight
→ conclui somente limpeza segura
```

## 1.10.14 — audit combinado

**Estado:** NOT LIVE.

O audit final valida:

- READY normal e MD32xx;
- Device duplicado ausente;
- IP na interface correta da VM;
- primary IPv4 correto;
- novo PLAN mostra o asset reparado como `DELEGATED/NOOP`.

## Única validação live prevista

Após CI PASS e publicação no `stable`:

```bash
netbox-discovery update run
netbox-discovery version
netbox-discovery run --apply
```

Não haverá uma sequência separada de microtestes. O próprio comando executa o PLAN e o preflight global antes da escrita.

Critério de conclusão:

```text
MD32xx criado como 1 STORAGE com 2 MGMT
REPAIR_SAFE concluído
Web Appliance fraco permanece REVIEW se não houver nova evidência
AUDIT FINALIZE: PASS ou PASS_WITH_WARNINGS sem FAIL
novo PLAN sem CREATE/UPDATE/REPAIR pendente
```

## Schedulers

```text
Auto-update stable: LIVE PASS
Network scheduler: DISABLED durante homologação
Hypervisor scheduler: DISABLED durante homologação
```
