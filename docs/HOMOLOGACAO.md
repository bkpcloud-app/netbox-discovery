# netbox-discovery 1.10.10 — Matriz de Homologação

## Estados

```text
LIVE PASS     = validado ao vivo com evidência
LIVE PARTIAL  = parte relevante validada, fluxo completo pendente
CI PASS       = regressões automatizadas passaram
NOT LIVE      = ainda não validado ao vivo
```

CI PASS não equivale a LIVE PASS.

## Hypervisor — estado de referência

**Estado:** LIVE PASS na linha 1.10.8.

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

Execução real em 27/07/2026:

```text
Hosts ativos: 64
Assets reconciliados: 60
READY: 7
REVIEW: 47
BLOCKED: 6
READY/CREATE: 3
READY/NOOP: 4
NetBox write: NÃO
```

Diagnóstico detalhado mostrou que a maior classe de pendência era IP já pertencente a:

```text
virtualization.vminterface
```

Isso ocorreu em servidores Windows/Linux, appliances VMware e appliances Fortinet virtualizados já presentes no inventário Hypervisor.

Também foram observados switches físicos Dell classificados genericamente:

```text
10.1.1.31  SW-DCM-SERVERS  Dell N2024      → LINUX_HOST/LOW
10.1.1.38  SW_LINKS        PCT7024         → WEB_APPLIANCE/LOW
10.1.1.50  SW-SAN-AE1      Dell S4128F-ON  → SNMP_DEVICE/LOW
10.1.1.51  SW-SAN-AE2      Dell S4128F-ON  → SNMP_DEVICE/LOW
```

O APPLY Network não foi autorizado.

## 1.10.10 — ownership Network/Hypervisor

**Estado:** NOT LIVE até update + novo dry-run real.

Regra implementada:

```text
Network asset sem Device físico correspondente
+ todos os IPs já vinculados a virtualization.vminterface
→ DELEGATED
→ NOOP
→ OWNED_BY_HYPERVISOR_VM
```

Consequências esperadas:

- remove falso REVIEW do pipeline Network;
- não cria `dcim.device` para VM;
- não altera a VM/IP;
- IMPORT Network continua consumindo apenas `READY`.

Proteção adicional:

```text
MAC/asset com identidade VMware
+ sem correspondência VM no NetBox
→ REVIEW
→ VIRTUAL_MACHINE_CANDIDATE_NO_VM_MATCH
```

Isso protege principalmente novos `READY/CREATE` que possam ser VMs ainda não correlacionadas.

## 1.10.10 — Dell Network Switch

**Estado:** NOT LIVE até novo dry-run.

O classificador passa a priorizar hardware model/ENTITY-MIB Dell Networking sobre SSH/Linux/Web genérico.

Regressões cobrem:

```text
N2024      → NETWORK_SWITCH/HIGH
PCT7024    → NETWORK_SWITCH/HIGH
S4128F-ON  → NETWORK_SWITCH/HIGH
```

A regra é por família/modelo de hardware, não por IP, hostname, cliente ou Site.

## Resíduo propositalmente não resolvido nesta release

Storages/controladoras continuam conservadores até obtermos evidência suficiente para definir identidade de array versus controladora:

```text
ME4024
ME5024
MD3200BKP
ME4012
```

Não serão criados/mesclados automaticamente no escuro.

## Próxima validação live

```text
1. CI PASS 1.10.10
2. publicar stable
3. update no SNOC-AGL-DCM
4. netbox-discovery run
5. confirmar grande redução de REVIEW por DELEGATED
6. confirmar N2024/PCT7024/S4128F-ON como NETWORK_SWITCH/HIGH
7. revisar READY/CREATE, principalmente possíveis VMs sem match
8. analisar apenas o resíduo de storage/UNKNOWN
9. nenhum --apply até o PLAN físico estar correto
```

## Schedulers

```text
Auto-update stable: LIVE PASS
Network scheduler: DISABLED durante homologação
Hypervisor scheduler: DISABLED durante homologação
```
