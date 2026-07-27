# netbox-discovery

Produto BKPCLOUD para descoberta, reconciliação e inventário seguro de infraestrutura no NetBox.

**Versão atual:** 1.10.10 — PRODUCT V1  
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

## Ownership entre Network e Hypervisor — 1.10.10

O dry-run Network 1.10.9 mostrou que grande parte dos `REVIEW` do DCM eram VMs que já tinham IP vinculado no NetBox a:

```text
virtualization.vminterface
```

Esses objetos não devem virar `dcim.device` e também não representam trabalho pendente do pipeline Network.

A partir da 1.10.10:

```text
IP de Network já pertencente a virtualization.vminterface
→ decisão DELEGATED
→ action NOOP
→ owner Hypervisor
→ nenhuma escrita Network
```

O diagnóstico mostra:

```text
DELEGATED/HYPERVISOR: N
NETWORK DELEGADOS AO HYPERVISOR
```

Proteção adicional: um asset com MAC VMware/asset class de VM, mas ainda sem correspondência no inventário Hypervisor, vira `REVIEW` com:

```text
VIRTUAL_MACHINE_CANDIDATE_NO_VM_MATCH
```

Assim o pipeline Network não cria uma VM como equipamento físico por engano.

## Dell Networking — 1.10.10

Modelos físicos de switch Dell identificados por ENTITY-MIB/modelo de hardware agora têm prioridade sobre fingerprints genéricos de Linux/SSH, SNMP ou Web.

Exemplos observados no DCM:

```text
N2024
PCT7024 / PowerConnect 7024
S4128F-ON
```

Todos são tratados como `NETWORK_SWITCH` quando o modelo de hardware confirma a família.

Isso é importante porque sistemas Dell Networking podem expor SSH/Linux, mas o asset continua sendo um switch físico.

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

O PLAN revisa/bloqueia confiança insuficiente, role desconhecida, OOB sem parent, conflito de identidade, IP pertencente a outro Device e drift destrutivo.

## Hypervisor LIVE PASS — 1.10.8

Após o APPLY multi-contexto e compare final:

```text
Objetos comparados: 282
OK: 282
MISMATCH: 0
MISSING: 0
AMBIGUOUS: 0
COMPARE STATUS: OK
```

A VM acompanha Tenant/Site do Host/Cluster, Cluster/Site usa migração coordenada e o compare é read-only.

## Identidade e reconciliação

Regras conservadoras:

- nome sozinho não autoriza migração forte;
- serial/UUID, IP e MAC são evidências fortes quando inequívocas;
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
