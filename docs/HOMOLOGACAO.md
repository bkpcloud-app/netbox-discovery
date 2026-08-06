# netbox-discovery 1.11.21 — Matriz de Homologação

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

```text
BLOCKED: 0
Assets FAIL: 0
Checks FAIL: 0
Scheduler Network: ENABLED
APPLY: NÃO
```

## DCM

**Estado:** LIVE PARTIAL.

Validado ao vivo:

- Discovery V6 em seis redes `/24`;
- 110 hosts ativos e 101 assets reconciliados;
- 43 VMs delegadas ao inventário central do vCenter;
- identidade `WEAK` rebaixada corretamente;
- write guard final em política de bootstrap;
- scheduler Network desabilitado durante homologação.

## Primeiro APPLY — escrita parcial confirmada

Na 1.11.19, o primeiro APPLY criou parcialmente o `SW-CORE-AE` e parou ao reconciliar a MAC:

```text
MAC E8:B5:D0:72:9D:FC já pertence a dcim.interface ID 543
```

O PLAN posterior confirmou:

```text
Devices no site: 14
SW-CORE-AE: READY/NOOP
Motivos: SERIAL+MAC+IP+NAME
READY/CREATE restantes: 13
READY/NOOP: 14
REVIEW: 29
BLOCKED: 2
WRITE GUARD: PASS
```

## Segunda tentativa na 1.11.20 — nenhuma escrita

O preflight foi bloqueado antes da escrita:

```text
PREFLIGHT GLOBAL FINALIZE: BLOQUEADO - nenhuma escrita iniciada
SW-CORE-AE: MAC E8:B5:D0:72:9D:FC pertence a dcim.interface ID 543,
esperado interface ainda não existente
```

A mesma mensagem apareceu duas vezes.

### Causa confirmada

O Importer V5 legado:

- inferia a interface esperada apenas pelo IP presente no `spec`;
- não consultava o Device proprietário real da interface live;
- tratava a interface não inferida como conflito, mesmo quando ela pertencia ao próprio `existing_device_id`;
- avaliava a mesma MAC repetida em dois `specs`, gerando erro duplicado.

A proteção global nova estava correta; o falso bloqueio vinha da camada legada executada antes dela.

## Estado da 1.11.21

**Estado inicial:** CI PASS / NOT LIVE até atualização no DCM.

Contrato corrigido:

```text
READY/NOOP reconciliado
+ MAC atribuída a dcim.interface
+ interface.device.id = Device reconciliado
→ PASS

interface.device.id diferente do Device reconciliado
→ BLOQUEADO

mesma MAC repetida no mesmo registro
→ avaliada uma única vez
```

A regra consulta todas as `dcim.interfaces` e usa o owner real como autoridade. Ela não transfere MAC e não libera MAC pertencente a outro Device, VM ou objeto.

## Regressões obrigatórias

```text
interface 543 pertence ao SW-CORE-AE reconciliado → PASS
spec sem IP utilizável                            → owner real continua válido
mesma MAC em dois specs                           → zero duplicação de erro
interface 543 pertence a outro Device             → um bloqueio
novo Device reutilizando MAC existente            → bloqueio
MAC em virtualization.vminterface                 → bloqueio
MAC global duplicada                              → um bloqueio
```

## Próxima validação no DCM

- atualizar para 1.11.21;
- confirmar `netbox-discovery version`;
- não executar nova descoberta;
- executar `netbox-discovery import --apply` somente após atualização;
- confirmar `PREFLIGHT GLOBAL FINALIZE: OK`;
- validar criação dos 13 equipamentos restantes;
- executar auditoria e PLAN convergente depois do IMPORT;
- manter scheduler desabilitado até o fechamento.

## Critérios para LIVE PASS

```text
Self-test: PASS
Check: PASS
PREFLIGHT GLOBAL FINALIZE: OK
PREFLIGHT: OK
13 READY/CREATE processados sem erro
SW-CORE-AE preservado como READY/NOOP
nenhuma transferência de MAC
IMPORT: PASS
AUDIT: PASS
PLAN posterior convergente
scheduler ainda desabilitado durante homologação
```
