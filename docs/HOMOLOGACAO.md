# netbox-discovery 1.11.19 — Matriz de Homologação

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

Validado ao vivo até a 1.11.18:

- Discovery V6 em seis redes `/24`;
- 110 hosts ativos e 101 assets reconciliados;
- dry-run concluído sem escrita;
- 43 VMs delegadas ao inventário central do vCenter;
- write guard final em política de bootstrap;
- scheduler Network desabilitado durante homologação.

PLAN observado na 1.11.18:

```text
READY: 30
  READY/CREATE: 17
  READY/NOOP: 13
DELEGATED: 43
REVIEW: 26
BLOCKED: 2
WRITE GUARD: PASS
eligible_total: 17
live_devices: 13
change_percent: 131%
policy: SMALL_SITE_BOOTSTRAP_ABSOLUTE_ONLY
```

Os dois bloqueios reais permaneceram corretamente:

```text
10.28.1.20 | Kubernetes Ingress Controller Fake Certificate
10.28.1.25 | Kubernetes Ingress Controller Fake Certificate
motivo: DUPLICATE_DESIRED_NAME / RECONCILE_REVIEW_CANDIDATE
```

### Defeito revelado pela revisão dos 17 READY/CREATE

Quatorze candidatos possuíam identidade estável:

```text
5 switches com serial
8 access points com management MAC
1 UPS com serial
```

Três candidatos estavam incorretamente liberados com `Discovery UID: WEAK`:

```text
10.28.1.22 | SRV-DCAR03 | WINDOWS_HOST
10.28.1.23 | SRV-DCAR02 | WINDOWS_HOST
10.225.1.61 | SMS Agente SNMP | SMS_GATEWAY
```

As regras anteriores eram específicas para `PHYSICAL_DEVICE` e roles Windows conhecidas. `WINDOWS_HOST` e `HOST_OR_APPLIANCE` podiam escapar da proteção.

## Estado da 1.11.19

**Estado inicial:** CI PASS / NOT LIVE até novo PLAN do DCM.

Contrato corrigido:

```text
novo READY/CREATE
+ sem existing_device_id
+ discovery_uid WEAK
→ REVIEW/NOOP
→ remover interfaces e intenções de IP
```

A regra é final, independente de role e classe, e é executada antes do write guard.

Resultado esperado no DCM:

```text
READY/CREATE: 14
REVIEW: 29
BLOCKED: 2
DELEGATED: 43
WRITE GUARD: PASS
eligible_total: 14
nenhum novo READY/CREATE com discovery_uid WEAK
```

## Regressões obrigatórias

```text
WINDOWS_HOST com WEAK UID → REVIEW/NOOP
SMS_GATEWAY com WEAK UID → REVIEW/NOOP
qualquer role/classe nova com WEAK UID → REVIEW/NOOP
SERIAL ou MGMT-MAC estável → permanece READY
Device existente → não é rebaixado por esta regra
14 estáveis + 3 fracos sobre base 13 → eligible_total=14 e PASS
```

## Pendente no DCM

- atualizar para 1.11.19;
- gerar novo dry-run;
- confirmar os três candidatos em REVIEW;
- confirmar `READY/CREATE=14` e `WRITE GUARD: PASS`;
- revisar os 14 candidatos estáveis;
- manter scheduler desabilitado até convergência;
- não executar APPLY antes da validação final.

## Critérios para liberar APPLY

```text
Self-test: PASS
Check: PASS
WRITE GUARD: PASS
nenhum novo Device com discovery_uid WEAK em READY
BLOCKED reais analisados
READY/CREATE revisados
Erros: 0
Assets FAIL: 0
Checks FAIL: 0
PLAN posterior convergente
```
