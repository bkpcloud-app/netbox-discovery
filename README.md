# netbox-discovery

Produto BKPCLOUD para descoberta, reconciliação e inventário seguro de infraestrutura no NetBox.

**Versão atual:** 1.10.11 — PRODUCT V1  
**Distribuição:** repositório público oficial `bkpcloud-app/netbox-discovery`  
**Canal padrão:** `stable`  
**NetBox BKPCLOUD:** `https://inventory.bkpcloud.app.br:8080`

> A documentação faz parte da release. O self-test e o CI bloqueiam publicação quando os documentos obrigatórios divergem do `VERSION`.

## Pipelines

### Rede

```text
netbox-discovery run
DISCOVER → CLASSIFY → RECONCILE → PLAN
```

Com escrita explícita:

```text
netbox-discovery run --apply
DISCOVER → CLASSIFY → RECONCILE → PLAN → IMPORT → AUDIT
```

### Hypervisor

```text
netbox-discovery hypervisor configure
netbox-discovery hypervisor check
netbox-discovery hypervisor run
netbox-discovery hypervisor run --compare
netbox-discovery hypervisor run --apply
netbox-discovery hypervisor status
```

Conectores: VMware, Proxmox VE e Microsoft Hyper-V.

## PowerVault / storage FibreAlliance — 1.10.11

Storages com duas controladoras não podem ser fundidos apenas porque respondem com o mesmo `sysName`.

A partir da 1.10.11, o discovery tenta obter identidade do array pelo FCMGMT/FibreAlliance MIB:

```text
.1.3.6.1.3.94.1.6.1
```

E usa, quando expostos pelo equipamento:

```text
connUnitId       → identidade persistente do storage
connUnitType     → exige storage-subsystem(11)
connUnitProduct  → modelo
connUnitSn       → serial
```

Política:

```text
mesmo connUnitId em dois IPs de gerenciamento
→ mesmo storage
→ RECONCILE pode unir os IPs/controladoras em um único asset

diferentes connUnitId
→ não fundir

sem identidade FA suficiente
→ continuar REVIEW/BLOCKED
```

O SNMP EngineID não é usado como identidade do array, pois pode representar a controladora individual.

O diagnóstico Network mostra a evidência quando disponível:

```text
Storage FA-MIB: id=... product=... serial=... type=storage-subsystem(11)
```

A release permanece sem escrita automática: somente `READY` pode ser importado e somente após `--apply` explícito.

## Ownership entre Network e Hypervisor — 1.10.10

Quando um IP descoberto pelo Network já pertence no NetBox a `virtualization.vminterface`:

```text
→ DELEGATED
→ NOOP
→ owner Hypervisor
→ nenhuma escrita Network
```

Um asset com identidade VMware, mas sem VM correspondente, permanece:

```text
REVIEW
VIRTUAL_MACHINE_CANDIDATE_NO_VM_MATCH
```

## Dell Networking — 1.10.10

Modelos físicos de switch Dell identificados por ENTITY-MIB/modelo de hardware têm prioridade sobre fingerprints genéricos Linux/SSH/Web/SNMP.

Validados no DCM:

```text
N2024      → NETWORK_SWITCH / HIGH
PCT7024    → NETWORK_SWITCH / HIGH
S4128F-ON  → NETWORK_SWITCH / HIGH
```

## Diagnóstico automático do PLAN Network — 1.10.9+

`netbox-discovery run` mostra:

```text
NETWORK PLAN DIAGNÓSTICO
NETWORK DELEGADOS AO HYPERVISOR
NETWORK NOVOS OBJETOS READY
NETWORK AJUSTES READY
NETWORK PENDÊNCIAS POR MOTIVO
NETWORK PENDÊNCIAS DETALHADAS
```

Para READY/REVIEW/BLOCKED o produto mostra evidências relevantes sem exigir JSON/Python ad-hoc.

## Política Network

```text
READY       → elegível para escrita somente com --apply
DELEGATED   → pertencente a outro pipeline; NOOP no Network
REVIEW      → não escreve
BLOCKED     → não escreve
run         → dry-run
run --apply → IMPORT apenas de READY + AUDIT
```

## Hypervisor LIVE PASS — 1.10.8+

Após o APPLY multi-contexto e compare final:

```text
Objetos comparados: 282
OK: 282
MISMATCH: 0
MISSING: 0
AMBIGUOUS: 0
COMPARE STATUS: OK
```

## Identidade e reconciliação

Regras conservadoras:

- nome sozinho não autoriza migração forte;
- serial/UUID, IP e MAC são evidências fortes quando inequívocas;
- para storage FibreAlliance, `connUnitId` válido pode ser identidade forte do array;
- MAC de gerenciamento autoritativo é usado no Network;
- MACs auxiliares não fundem assets sozinhos;
- ausência em coleta não vira DELETE automático.

## Estrutura Tenant/Site

```text
Tenant Group [opcional]
└── Tenant
    └── Site
```

O produto é genérico e não contém hardcode de cliente.

## Segurança operacional

```text
Network run                 = dry-run
Network run --apply         = escrita de READY + AUDIT
DELEGATED                   = nunca escreve no Network
Hypervisor run              = dry-run
Hypervisor run --compare    = read-only
Hypervisor run --apply      = escrita após preflight
REVIEW/BLOCKED              = não escrevem
DELETE Hypervisor           = nunca automático
```

Network, Hypervisor, Compare e Update compartilham lock global. POST/PATCH não recebem retry cego.

## Operação

```bash
netbox-discovery version
netbox-discovery status
netbox-discovery self-test
netbox-discovery health

netbox-discovery run
netbox-discovery run --apply

netbox-discovery hypervisor check
netbox-discovery hypervisor run
netbox-discovery hypervisor run --compare
netbox-discovery hypervisor run --apply

netbox-discovery update status
netbox-discovery update check
netbox-discovery update run
```

## Caminhos

```text
Aplicação:              /opt/netbox-discovery
Configuração principal: /opt/netbox-discovery/config.yml
Config Hypervisor:      /etc/netbox-discovery/hypervisors.json
Config por Site:        /opt/netbox-discovery/config/sites/
Relatórios:             /opt/netbox-discovery/reports
Backups:                /opt/netbox-discovery/backups
Lock global:            /var/lock/netbox-discovery-global.lock
```

## Homologação

**CI PASS não equivale a LIVE PASS.**

A matriz oficial fica em `docs/HOMOLOGACAO.md`.

## Documentação obrigatória

- `README.md`
- `docs/MANUAL.md`
- `docs/COMANDOS-RAPIDOS.md`
- `docs/HOMOLOGACAO.md`
- `RELEASE-NOTES.md`
- `SECURITY.md`
