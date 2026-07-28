# netbox-discovery 1.10.11 — Matriz de Homologação

## Estados

```text
LIVE PASS     = validado ao vivo com evidência
LIVE PARTIAL  = parte relevante validada, fluxo completo pendente
CI PASS       = regressões automatizadas passaram
NOT LIVE      = ainda não validado ao vivo
```

CI PASS não equivale a LIVE PASS.

## Hypervisor — estado de referência

**Estado:** LIVE PASS.

Validação final real:

```text
Objetos comparados: 282
OK: 282
MISMATCH: 0
MISSING: 0
AMBIGUOUS: 0
CLUSTER: OK=2
HOST: OK=22
PREFIX: OK=12
VM: OK=246
COMPARE STATUS: OK
```

## Network DCM — baseline 1.10.9

```text
Hosts ativos: 64
Assets reconciliados: 60
READY: 7
REVIEW: 47
BLOCKED: 6
NetBox write: NÃO
```

A maior classe de falso REVIEW era IP já pertencente a `virtualization.vminterface`.

## 1.10.10 — ownership Network/Hypervisor

**Estado:** LIVE PASS no dry-run real de 28/07/2026.

Resultado:

```text
Hosts ativos: 64
Assets reconciliados: 60
READY: 9
DELEGATED/HYPERVISOR: 41
REVIEW: 4
BLOCKED: 6
NetBox write: NÃO
```

As 41 VMs/appliances já inventariadas pelo Hypervisor foram corretamente convertidas de falso REVIEW para `DELEGATED/NOOP`.

Duas VMs sem correspondência permaneceram protegidas:

```text
10.1.1.111 SRV-AE11  → VIRTUAL_MACHINE_CANDIDATE_NO_VM_MATCH
10.1.1.168 SRV-GEP11 → VIRTUAL_MACHINE_CANDIDATE_NO_VM_MATCH
```

## 1.10.10 — Dell Network Switch

**Estado:** LIVE PASS no dry-run real.

```text
10.1.1.31 SW-DCM-SERVERS Dell N2024      → NETWORK_SWITCH/HIGH
10.1.1.38 SW_LINKS       Dell PCT7024    → NETWORK_SWITCH/HIGH
10.1.1.50 SW-SAN-AE1     Dell S4128F-ON  → NETWORK_SWITCH/HIGH
10.1.1.51 SW-SAN-AE2     Dell S4128F-ON  → NETWORK_SWITCH/HIGH
```

Todos apareceram como `READY/CREATE`, sem hardcode de IP/Site.

## Resíduo live após 1.10.10

```text
10.1.1.52 / .53 → ME4024, mesmo nome, identidades de controladora distintas
10.1.1.54       → UNKNOWN / Seagate OUI
10.1.1.55       → ME5024
10.1.1.56 / .57 → MD3200BKP
10.1.1.58 / .59 → ME4012
```

Os pares permaneceram BLOCKED em vez de serem unidos apenas pelo nome. Isso é o comportamento seguro esperado antes da 1.10.11.

## 1.10.11 — PowerVault / FibreAlliance FA-MIB

**Estado:** NOT LIVE até update + novo dry-run real.

Implementação:

```text
DISCOVER
→ consulta FCMGMT/FibreAlliance .1.3.6.1.3.94.1.6.1
→ exige connUnitType=storage-subsystem(11)
→ coleta connUnitId / connUnitProduct / connUnitSn
→ CLASSIFY STORAGE/HIGH
→ RECONCILE por serial ou FA connUnitId
```

Regra de merge:

```text
mesmo connUnitId → merge forte das interfaces/IPs de gerenciamento
diferente connUnitId → não merge
sem connUnitId válido → permanece conservador
```

O SNMP EngineID não é usado como identidade do array.

Regressões automatizadas cobrem:

- mesmo FA `connUnitId` em dois IPs/controladoras;
- `storage-subsystem(11)` → STORAGE/HIGH;
- serial/modelo vindos do FA-MIB;
- IDs diferentes não são unidos;
- identidade de array independente do MAC de gerenciamento da controladora.

### Próxima validação live

```text
1. publicar 1.10.11 stable após CI PASS
2. update no SNOC-AGL-DCM
3. netbox-discovery run
4. observar Storage FA-MIB nos PowerVault
5. confirmar se .52/.53 e .58/.59 compartilham connUnitId real
6. confirmar ME5024/.54 somente se a evidência FA provar relação
7. MD3200 pode permanecer REVIEW/BLOCKED se não expuser FA-MIB
8. nenhum --apply até revisão do novo PLAN
```

## Schedulers

```text
Auto-update stable: LIVE PASS
Network scheduler: DISABLED durante homologação
Hypervisor scheduler: DISABLED durante homologação
```
