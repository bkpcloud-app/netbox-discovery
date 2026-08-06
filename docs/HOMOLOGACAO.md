# netbox-discovery 1.11.22 — Matriz de Homologação

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

**Estado:** LIVE PARTIAL.

Validado ao vivo:

- Discovery V6 em seis redes `/24`;
- 110 hosts ativos e 101 assets reconciliados;
- 43 VMs delegadas ao vCenter;
- identidade `WEAK` rebaixada;
- write guard em política de bootstrap;
- scheduler Network desabilitado.

## Primeiro APPLY — escrita parcial confirmada

Na 1.11.19, o primeiro APPLY criou parcialmente o `SW-CORE-AE` e parou:

```text
MAC E8:B5:D0:72:9D:FC já pertence a dcim.interface ID 543
```

O PLAN posterior confirmou:

```text
Devices no site: 14
SW-CORE-AE: READY/NOOP
READY/CREATE restantes: 13
READY/NOOP: 14
REVIEW: 29
BLOCKED: 2
WRITE GUARD: PASS
```

## Segunda tentativa — preflight bloqueado

Na 1.11.20, nenhuma escrita foi iniciada. O preflight legado não reconheceu que a interface `543` pertencia ao próprio Device.

A 1.11.21 corrigiu esse falso bloqueio e o preflight passou.

## Terceira tentativa — runtime tardio ainda incorreto

Na 1.11.21:

```text
PREFLIGHT GLOBAL FINALIZE: OK
PREFLIGHT: OK
ERRO em SW-CORE-AE: MAC E8:B5:D0:72:9D:FC já pertence a dcim.interface ID 543
```

### Causa confirmada

O runtime do Importer V2 ainda executava:

```text
procurar interface pelo nome do spec
→ criar/preservar interface
→ somente depois validar a MAC
```

Quando o nome do `spec` divergia do nome da interface live `543`, o Importer podia criar uma interface adicional e depois falhar ao descobrir que a MAC já estava vinculada à interface original.

Essa tentativa não avançou para os outros 13 Devices. Ela deve ser tratada como possível criação de interface parcial no `SW-CORE-AE`.

## Estado da 1.11.22

**Estado inicial:** CI PASS / NOT LIVE até atualização no DCM.

Contrato corrigido:

```text
resolver MAC global
→ resolver dcim.interface vinculada
→ validar interface.device.id
→ se for o mesmo Device, reutilizar a interface live
→ somente sem vínculo usar busca/criação por nome
```

Regras:

```text
interface 543 pertence ao SW-CORE-AE reconciliado → PRESERVED_BY_MAC
nome live diferente do nome do spec               → não cria nova interface
interface pertence a outro Device                 → bloqueio antes da criação
MAC em VM/outro objeto                            → bloqueio antes da criação
MAC sem vínculo                                   → fluxo normal
```

## Regressões obrigatórias

```text
interface 543 no mesmo Device + nome diferente    → reutiliza 543
mesma MAC em dois specs                            → reutiliza 543 nas duas passagens
interface em outro Device                         → bloqueia antes de ORIG_ENSURE_INTERFACE
MAC em virtualization.vminterface                 → bloqueia antes da criação
MAC sem atribuição                                 → segue fluxo normal
nenhum POST de interface no cenário parcial       → obrigatório
```

## Próxima validação no DCM

- atualizar para 1.11.22;
- executar `netbox-discovery import --apply`;
- confirmar `PREFLIGHT GLOBAL FINALIZE: OK`;
- confirmar `PREFLIGHT: OK`;
- confirmar `SW-CORE-AE` preservado por MAC;
- validar os 13 equipamentos restantes;
- executar AUDIT e PLAN convergente;
- manter scheduler desabilitado até o fechamento.

## Critérios para LIVE PASS

```text
Self-test: PASS
Check: PASS
PREFLIGHT GLOBAL FINALIZE: OK
PREFLIGHT: OK
SW-CORE-AE sem nova interface duplicada
13 READY/CREATE processados sem erro
IMPORT: PASS
AUDIT: PASS
PLAN posterior convergente
```
