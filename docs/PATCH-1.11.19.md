# netbox-discovery 1.11.19

## Problema observado no DCM

O dry-run da 1.11.18 funcionou corretamente quanto ao bootstrap do write guard:

```text
WRITE GUARD: PASS
READY/CREATE: 17
REVIEW: 26
BLOCKED: 2
DELEGATED: 43
```

A revisão detalhada dos 17 candidatos revelou três novos Devices com identidade fraca:

```text
10.28.1.22 | SRV-DCAR03 | WINDOWS_HOST | WEAK:E20071661A46DCF5
10.28.1.23 | SRV-DCAR02 | WINDOWS_HOST | WEAK:90940A43CCE4886A
10.225.1.61 | SMS Agente SNMP | SMS_GATEWAY | WEAK:429D39959FBE898B
```

Eles tinham nome e evidência de serviço, mas não possuíam serial nem management MAC estável.

## Causa

As proteções anteriores eram específicas:

- Windows Server/Workstation já classificados;
- novos `PHYSICAL_DEVICE`;
- impressoras;
- VMs e virtual candidates.

Roles genéricas como `WINDOWS_HOST` e classes como `HOST_OR_APPLIANCE` podiam terminar em `READY/CREATE` sem passar por uma validação global de identidade.

## Correção

O Planner V11 agora executa uma proteção final antes do write guard:

```text
sem existing_device_id
+ decision=READY
+ action=CREATE
+ discovery_uid começa com WEAK:
→ decision=REVIEW
→ action=NOOP
→ remover interfaces
→ remover intenções de IP
→ remover diffs e reparos
→ motivo NEW_DEVICE_REQUIRES_STABLE_IDENTITY
```

A regra é independente de role e `asset_class`.

## Identidades estáveis

Novos Devices podem permanecer elegíveis quando possuem identidade estável, como:

```text
SERIAL:<fabricante>:<serial>
MGMT-MAC:<mac>
```

Devices existentes não são rebaixados por essa regra.

## Resultado esperado no DCM

```text
READY/CREATE: 14
REVIEW: 29
BLOCKED: 2
DELEGATED: 43
WRITE GUARD: PASS
eligible_total: 14
```

Os 14 candidatos estáveis são:

- 5 switches com serial;
- 8 access points com management MAC;
- 1 UPS com serial.

Os dois conflitos Kubernetes permanecem `BLOCKED`.

## Segurança preservada

- `run` continua sem escrita;
- `--apply` continua obrigatório para qualquer alteração;
- scheduler e `automation.apply` não são alterados;
- bootstrap adia somente o percentual;
- limites absolutos continuam ativos;
- candidatos `WEAK` não entram no write guard nem no Importer;
- nenhuma exclusão automática foi adicionada.

## Homologação

Após atualizar para 1.11.19, executar novo dry-run e confirmar:

```text
nenhum novo READY/CREATE com discovery_uid WEAK
READY/CREATE=14
WRITE GUARD=PASS
BLOCKED=2
NetBox write=NÃO
```
