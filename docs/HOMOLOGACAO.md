# netbox-discovery 1.11.23 — Matriz de Homologação

## Estados

```text
LIVE PASS     = validado ao vivo com evidência
LIVE PARTIAL  = parte relevante validada
CI PASS       = regressões automatizadas passaram
NOT LIVE      = ainda não validado em ambiente real
```

CI PASS não substitui LIVE PASS.

## FBA

**Estado:** LIVE PASS como referência funcional.

## DCM

**Estado:** LIVE PASS na 1.11.22.

Evidência final:

```text
IMPORT: 27/27 processados
Runtime blocked: 0
Erros: 0
MAC RECONCILE: PASS
AUDIT: PASS
Assets PASS: 27
Assets WARN: 0
Assets FAIL: 0
Checks PASS: 321
Checks WARN: 0
Checks FAIL: 0
READY/CREATE posterior: 0
READY/NOOP posterior: 27
Network scheduler: ENABLED
Hypervisor scheduler: DISABLED
```

## Histórico da correção de MAC

Na 1.11.19, um APPLY parcial do DCM parou porque a MAC já pertencia à `dcim.interface ID 543`.

A 1.11.20 adicionou o preflight global, mas o preflight legado não reconheceu corretamente o proprietário real da interface.

A 1.11.21 corrigiu o preflight legado.

A 1.11.22 corrigiu o runtime final:

```text
resolver MAC global
→ resolver dcim.interface vinculada
→ validar interface.device.id
→ se for o mesmo Device, reutilizar a interface live
→ somente sem vínculo usar busca/criação por nome
```

O DCM convergiu e foi encerrado como LIVE PASS.

## FPA — preparação

**Estado:** PLAN revisado; GO-LIVE pendente.

Plano observado:

```text
READY: 24
READY/CREATE: 23
READY/NOOP: 1
REVIEW: 111
BLOCKED: 5
WRITE GUARD: PASS
scheduler Network: DISABLED
```

As redes `10.3.1.0`, `10.3.2.0`, `10.3.5.0` e `10.3.100.0` pertencem ao Site FPA/Pacatuba conforme validação operacional. Nome de equipamento não deve ser usado para inferir outro Site.

## Estado da 1.11.23

**Estado inicial:** CI PASS / NOT LIVE até execução no FPA.

A versão adiciona o comando padrão:

```bash
netbox-discovery go-live
```

Contrato:

```text
IMPORT --apply
→ AUDIT
→ novo PLAN e summary
→ bloquear se restar READY/CREATE, UPDATE_SAFE ou REPAIR_SAFE_VM_DUPLICATE
→ preservar Tenant, Site, token, redes, exclusões e comunidades
→ forçar automation.apply=false
→ habilitar scheduler Network
→ verificar enabled=true e apply=false
→ status
```

Se qualquer etapa falhar, o GO-LIVE não é concluído. Se a validação final detectar estado inseguro, o scheduler é desabilitado antes do erro.

## Regressões obrigatórias da 1.11.23

```text
wrapper público reconhece go-live
comandos legados continuam delegados ao core
instalador ativa o wrapper público
go-live executa IMPORT antes do AUDIT
go-live executa PLAN antes da convergência
go-live bloqueia mudanças READY pendentes
go-live força APPLY=NÃO antes do scheduler
go-live verifica enabled=true e apply=false
falha final desabilita o scheduler
```

## Critérios para LIVE PASS no FPA

```text
netbox-discovery update run → 1.11.23
netbox-discovery go-live
IMPORT: erros 0
AUDIT: PASS
Assets FAIL: 0
Checks FAIL: 0
CONVERGÊNCIA: PASS
SCHEDULER NETWORK: ENABLED
APPLY AUTOMÁTICO: NÃO
GO-LIVE: PASS
```
