# netbox-discovery 1.11.20 — Matriz de Homologação

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
- identidade `WEAK` rebaixada corretamente na 1.11.19;
- write guard final em política de bootstrap;
- scheduler Network desabilitado durante homologação.

PLAN validado na 1.11.19:

```text
READY: 27
  READY/CREATE: 14
  READY/NOOP: 13
DELEGATED: 43
REVIEW: 29
BLOCKED: 2
WRITE GUARD: PASS
eligible_total: 14
live_devices: 13
change_percent: 108%
policy: SMALL_SITE_BOOTSTRAP_ABSOLUTE_ONLY
```

Os dois bloqueios Kubernetes permaneceram corretamente:

```text
10.28.1.20 | Kubernetes Ingress Controller Fake Certificate
10.28.1.25 | Kubernetes Ingress Controller Fake Certificate
motivo: DUPLICATE_DESIRED_NAME / RECONCILE_REVIEW_CANDIDATE
```

## APPLY da 1.11.19 — falha ao vivo

Comando executado:

```bash
netbox-discovery import --apply
```

O Importer recalculou o mesmo PLAN e informou:

```text
PREFLIGHT GLOBAL FINALIZE: OK
PREFLIGHT: OK
```

Na primeira linha READY, `SW-CORE-AE`, ocorreu:

```text
MAC E8:B5:D0:72:9D:FC já pertence a dcim.interface ID 543
```

A falha aconteceu depois do início do loop de escrita. Portanto, o ciclo deve ser tratado como possível aplicação parcial do primeiro equipamento, mesmo sem os demais READY processados.

Causa:

- o Planner V2 já consultava MACs globais para identidades presentes no asset reconciliado;
- o MAC de gerenciamento podia existir apenas na interface final do PLAN;
- o preflight do Importer validava conflitos globais de IP, mas não todos os MACs finais;
- o conflito foi detectado tarde, depois da criação/match do Device e da interface.

## Estado da 1.11.20

**Estado inicial:** CI PASS / NOT LIVE até atualização e novo PLAN no DCM.

Contrato corrigido:

```text
PLAN V11
→ consulta estado global de MAC já carregado
→ verifica todo MAC presente nas interfaces finais
→ conflito vira BLOCKED/NOOP antes do write guard

IMPORT V12 --apply
→ consulta novamente dcim/mac-addresses e dcim/interfaces
→ valida todos os READY antes da primeira escrita
→ falha fechado se a consulta estiver indisponível
```

Resultado esperado após recalcular o PLAN contra o estado atual do DCM:

```text
SW-CORE-AE
→ BLOCKED/NOOP por MAC pertencente a outro Device/interface

outros candidatos estáveis sem conflito
→ permanecem READY

WRITE GUARD
→ recalculado somente sobre os READY restantes
```

O produto não transfere automaticamente a MAC da interface ID 543 e não remove o possível objeto parcial criado no APPLY anterior.

## Regressões obrigatórias

```text
novo Device + MAC em outro Device       → BLOCKED/NOOP no PLAN
existing_device_id igual ao owner MAC   → permitido
MAC em virtualization.vminterface       → BLOCKED/NOOP
MAC global duplicado                    → BLOCKED/NOOP
preflight IMPORT encontra conflito      → nenhuma nova escrita iniciada
consulta global de MAC falha            → APPLY bloqueado
cenário DCM parcial + 13 seguros         → conflito isolado; eligible_total=13
```

## Próxima validação no DCM

- atualizar para 1.11.20;
- executar somente `netbox-discovery plan`;
- revisar `netbox-discovery plan summary` e `plan blocked`;
- confirmar o bloqueio de `SW-CORE-AE` com referência à interface ID 543;
- confirmar os demais READY após o recálculo;
- manter scheduler desabilitado;
- não repetir APPLY antes da nova revisão.

## Critérios para liberar nova tentativa de APPLY

```text
Self-test: PASS
Check: PASS
WRITE GUARD: PASS
nenhum READY com discovery_uid WEAK
nenhum READY com MAC pertencente a outro objeto
SW-CORE-AE e possível objeto parcial analisados
BLOCKED reais analisados
READY/CREATE revisados
preflight global de IP e MAC ativo
scheduler desabilitado durante homologação
```
