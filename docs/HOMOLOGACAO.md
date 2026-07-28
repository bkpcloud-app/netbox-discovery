# netbox-discovery 1.10.12 — Matriz de Homologação

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

## 1.10.10 — ownership Network/Hypervisor

**Estado:** LIVE PASS no dry-run real de 28/07/2026.

```text
DELEGATED/HYPERVISOR: 41
```

As VMs/appliances com IP já atribuído a `virtualization.vminterface` deixaram de gerar falso REVIEW e passaram a `DELEGATED/NOOP`.

## 1.10.10 — Dell Network Switch

**Estado:** LIVE PASS.

```text
10.1.1.31 SW-DCM-SERVERS Dell N2024      → NETWORK_SWITCH/HIGH
10.1.1.38 SW_LINKS       Dell PCT7024    → NETWORK_SWITCH/HIGH
10.1.1.50 SW-SAN-AE1     Dell S4128F-ON  → NETWORK_SWITCH/HIGH
10.1.1.51 SW-SAN-AE2     Dell S4128F-ON  → NETWORK_SWITCH/HIGH
```

## 1.10.11 — PowerVault / FA-MIB

**Estado:** LIVE PARTIAL.

Dry-run real de 28/07/2026 mostrou:

```text
ME4024 10.1.1.52
role=STORAGE/HIGH
product=DELL EMC ME4024
serial=CN0PJ27VFCG0091F01VNA00
connUnitId=208000C0FFF069900000000000000000

ME5024 10.1.1.55
role=STORAGE/HIGH
product=DELL EMC ME5024
serial=SGFTJ22265E8428
connUnitId=208000C0FF5E84280000000000000000
```

Isso comprova ao vivo que a leitura FCMGMT/FibreAlliance e classificação `STORAGE/HIGH` funcionam.

Porém, a evidência não foi estável em todas as controladoras em todas as execuções. No APPLY seguinte:

```text
10.1.1.52 → FA-MIB presente / STORAGE
10.1.1.53 → FA-MIB ausente / SNMP_DEVICE
10.1.1.58 → FA-MIB presente / ME4012 com serial, connUnitId=000...000
10.1.1.59 → FA-MIB ausente / SNMP_DEVICE
```

Portanto 1.10.11 não recebe LIVE PASS completo para reconciliação multi-controladora.

## Primeiro APPLY Network real — 1.10.11

**Estado:** LIVE PARTIAL.

PLAN imediatamente antes da escrita:

```text
Assets planejados: 60
READY: 13
REVIEW: 3
BLOCKED: 2
READY/CREATE: 9
READY/NOOP: 4
```

IMPORT:

```text
PREFLIGHT: OK
Assets READY processados: 13
Runtime blocked: 0
Erros: 0
NetBox write: SIM
```

AUDIT:

```text
Status: PASS_WITH_WARNINGS
Assets PASS: 9
Assets WARN: 4
Assets FAIL: 0
Checks PASS: 153
Checks WARN: 8
Checks FAIL: 0
```

Idempotency preview dos 13 READY escritos:

```text
READY/CREATE: 0
READY/UPDATE_SAFE: 0
READY/NOOP: 13
```

Isso valida ao vivo preflight, escrita de READY, exclusão de REVIEW/BLOCKED, AUDIT e idempotência do conjunto aplicado.

## Safety finding do APPLY 1.10.11

O APPLY também revelou um problema importante de anti-flap:

Execução anterior:

```text
10.1.1.111 SRV-AE11
management_mac=00:50:56:9F:9E:70
asset_class=VIRTUAL_MACHINE_CANDIDATE
REVIEW=VIRTUAL_MACHINE_CANDIDATE_NO_VM_MATCH
```

Execução do APPLY:

```text
10.1.1.111 SRV-AE11
management_mac não observado
asset_class=HOST_OR_APPLIANCE
READY/CREATE
```

O Device foi criado fisicamente porque a evidência VMware desapareceu de uma única coleta.

**Conclusão:** nenhuma nova autorização de APPLY Network até a proteção 1.10.12 ser validada ao vivo.

## 1.10.12 — identidade anti-flap

**Estado:** NOT LIVE até update + dry-run real.

Implementação:

```text
classificação atual
+ histórico forte do mesmo Site/IP por até 48h
→ preserva somente identidade forte ausente por falha transitória
```

Cobertura:

- VMware OUI / `VIRTUAL_MACHINE_CANDIDATE`;
- storage FA-MIB com serial/connUnitId forte;
- current strong physical identity pode substituir histórico VMware;
- serial/FA atual divergente vira conflito;
- all-zero connUnitId é inválido;
- histórico não injeta MAC antigo como MAC de interface.

## 1.10.12 — ownership VM por nome único

**Estado:** NOT LIVE.

```text
VM candidate + nome único de VM no mesmo Tenant/Site
→ DELEGATED/NOOP
```

Se já existe Device físico:

```text
→ BLOCKED
→ PHYSICAL_DEVICE_CONFLICT_WITH_HYPERVISOR_VM:<id>
```

O objetivo live imediato é detectar `SRV-AE11` como conflito/delegação Hypervisor mesmo se o MAC atual não aparecer.

## 1.10.12 — FA-MIB retry e zero ID

**Estado:** NOT LIVE.

- até três tentativas read-only da árvore FA-MIB;
- `connUnitId=000...000` não é usado como identidade;
- serial válido continua permitindo classificar `STORAGE/HIGH`;
- histórico forte pode preencher uma leitura FA transitoriamente ausente.

## 1.10.12 — AUDIT detalhado

**Estado:** NOT LIVE.

WARN/FAIL passam a aparecer diretamente no terminal em `AUDIT PENDÊNCIAS DETALHADAS`.

## Próxima validação live

```text
1. CI PASS 1.10.12
2. publicar stable
3. update no SNOC-AGL-DCM
4. netbox-discovery run   # somente dry-run
5. confirmar SRV-AE11 não READY
6. confirmar VM por nome único como DELEGATED ou conflito físico BLOCKED
7. confirmar ME4024/ME4012 com identidade estável ou histórico anti-flap visível
8. revisar resíduo
9. não executar --apply nessa validação
```

## Schedulers

```text
Auto-update stable: LIVE PASS
Network scheduler: DISABLED durante homologação
Hypervisor scheduler: DISABLED durante homologação
```
