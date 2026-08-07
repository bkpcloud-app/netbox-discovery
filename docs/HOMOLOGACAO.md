# netbox-discovery 1.11.33 — Matriz de Homologação

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

**Estado:** LIVE PASS para o pipeline Network histórico e LIVE PASS para o pipeline Hypervisor multi-contexto validado nas versões 1.11.29+.

Evidência histórica do Network:

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
```

Evidência do Hypervisor multi-contexto:

```text
PREFLIGHT GLOBAL: OK
Contextos escritos: 12
Reclassificações seguras: 53
Audit multi-contexto: PASS
MISMATCH: 0
MISSING: 0
```

## Histórico da correção de MAC

Na 1.11.19, um APPLY parcial do DCM parou porque uma MAC já pertencia a uma `dcim.interface` existente.

A 1.11.20 adicionou o preflight global, a 1.11.21 corrigiu o owner no preflight legado e a 1.11.22 corrigiu o runtime final:

```text
resolver MAC global
→ resolver dcim.interface vinculada
→ validar interface.device.id
→ se for o mesmo Device, reutilizar a interface live
→ somente sem vínculo usar busca/criação por nome
```

## GO-LIVE controlado

O fluxo controlado continua disponível:

```bash
netbox-discovery go-live
```

Contrato:

```text
IMPORT --apply
→ AUDIT
→ novo PLAN e summary
→ bloquear mudanças READY pendentes que impeçam convergência
→ preservar Tenant, Site, token, redes, exclusões e communities
→ forçar automation.apply=false
→ habilitar scheduler Network
→ verificar enabled=true e apply=false
→ status
```

## Instalação direta de unidade nova — contrato 1.11.33

Para unidades autorizadas a operar com escrita automática desde a primeira coleta, o procedimento oficial documentado é:

```bash
curl -fsSL https://raw.githubusercontent.com/bkpcloud-app/netbox-discovery/stable/install-from-github.sh -o /tmp/netbox-discovery-install.sh && bash /tmp/netbox-discovery-install.sh && netbox-discovery init && netbox-discovery check && netbox-discovery scheduler enable && netbox-discovery run --apply
```

Requisitos do `init` para esse modo:

```text
NetBox: https://inventory.bkpcloud.app.br
Habilitar execução automática: SIM
Permitir IMPORT automático: SIM
Salvar: SIM
Testar NetBox: SIM
```

Resultado esperado:

```text
CONFIG: OK
scheduler Network: ENABLED
primeiro RUN executado imediatamente
IMPORT/AUDIT conforme registros READY e proteções
próximas execuções agendadas usam automation.apply=true
```

## Regressões obrigatórias atuais

```text
configurador usa HTTPS/443 sem :8080
updater não aceita VERSION antigo por cache como evidência de up-to-date
documentação principal contém o comando oficial de instalação limpa
documentação principal contém o endpoint oficial sem :8080
wrapper público reconhece go-live
comandos legados continuam delegados ao core
instalador ativa o wrapper público
Network run --apply executa IMPORT e AUDIT
scheduler Network e Hypervisor permanecem independentes
REVIEW/DELEGATED/BLOCKED não escrevem
```

## Critérios gerais para LIVE PASS de unidade nova

```text
netbox-discovery version → versão stable atual
netbox-discovery check → PASS
CONFIG: OK
Tenant/Site corretos
NetBox URL sem :8080
primeiro RUN sem erro fatal
AUDIT sem FAIL crítico
scheduler no estado planejado
modo de APPLY coerente com a política da unidade
```
