# Manual Operacional — netbox-discovery

**Produto:** netbox-discovery  
**Versão:** 1.11.0 — PRODUCT V1  
**Distribuição oficial:** `bkpcloud-app/netbox-discovery`  
**Canal de produção:** `stable`  
**NetBox BKPCLOUD:** `https://inventory.bkpcloud.app.br:8080`

> `CI PASS` não equivale a `LIVE PASS`. Estado real em `docs/HOMOLOGACAO.md`.

## 1. Execução Network

```bash
netbox-discovery run
netbox-discovery run --apply
```

Fluxo 1.11.0:

```text
DISCOVER V5
→ CLASSIFY V7
→ RECONCILE V5
→ PLAN V9
→ WRITE GUARD + PREFLIGHT GLOBAL FINALIZE
→ IMPORT normal V10
→ MAC RECONCILE
→ REPAIR_SAFE
→ AUDIT FINALIZE V9
```

`run` é read-only. `run --apply` recalcula o PLAN imediatamente antes da escrita.

## 2. Decisões

| Decisão/Ação | Significado | Escrita |
|---|---|---|
| `READY/CREATE` | novo Device físico validado | somente com `--apply` |
| `READY/UPDATE_SAFE` | enriquecimento seguro | somente com `--apply` |
| `READY/REPAIR_SAFE_VM_DUPLICATE` | corrige Device duplicado criado pelo produto | após preflight global |
| `READY/NOOP` | inventário convergente ou identidade preservada | não altera |
| `DELEGATED` | ownership da VM no inventário central | não |
| `REVIEW` | evidência insuficiente ou associação humana necessária | não |
| `BLOCKED` | conflito forte ou write guard | não |

## 3. Autoridade dos dados

```text
Nome de Device existente     → NetBox
Nome observado               → SNMP, ONVIF, DNS ou protocolo
VM, cluster e VM interface   → vCenter central / NetBox virtualization
Fabricante/modelo/serial     → protocolo específico ou ENTITY-MIB
IP ativo                     → descoberta de rede
```

Um Device existente recebe:

```text
name_authority: NETBOX_EXISTING
name_write_allowed: false
```

O importer V10 bloqueia qualquer tentativa de PATCH do campo `name`.

## 4. Identidade consolidada

O motor `modules/product/identity.py` mantém:

```text
observed_name
observed_name_source
discovery_uid
asset_nature
asset_nature_source
identity_provenance
review_recommendations
```

O `discovery_uid` prefere serial, chassis MAC e MAC de gerenciamento. IP e nome não são usados como identidade forte quando existe opção melhor.

## 5. Industrial

A coleta é somente leitura e interpreta:

```text
Siemens S7
EtherNet/IP / CIP Identity
BACnet
Modbus Device Identification
SNMP sysObjectID / ENTITY-MIB
```

Papéis possíveis incluem:

```text
INDUSTRIAL_PLC
INDUSTRIAL_IO
INDUSTRIAL_SWITCH
INDUSTRIAL_COMMUNICATION
INDUSTRIAL_POWER_METER
INDUSTRIAL_DRIVE
INDUSTRIAL_MOTOR_PROTECTION
INDUSTRIAL_CONTROLLER
INDUSTRIAL_DEVICE
```

Modelo e fabricante só são elevados quando há evidência estruturada. Caso contrário, continuam genéricos e entram em REVIEW.

## 6. CFTV

ONVIF/WS-Discovery e fingerprints conhecidos classificam:

```text
CAMERA
NVR
DVR
VIDEO_ENCODER
VIDEO_SURVEILLANCE_DEVICE
```

Quando retornados pelo equipamento, fabricante, modelo, serial, firmware e hardware ID são preservados com a fonte da evidência.

## 7. Impressoras

Printer-MIB read-only:

```text
prtGeneralPrinterName
prtGeneralSerialNumber
hrDeviceDescr
```

Um tipo genérico criado pelo produto pode ser melhorado somente com match forte, confiança HIGH e modelo explícito. Nome manual permanece protegido.

## 8. Físico e virtual

A ordem de autoridade é:

1. IP ou MAC pertencente a `virtualization.vminterface`: VM confirmada.
2. Inventário central do vCenter: VM confirmada.
3. Hardware com modelo e serial fortes: físico confirmado.
4. OUI VMware, Hyper-V, KVM, Xen ou VirtualBox: apenas `VIRTUAL_CANDIDATE`.
5. Evidência insuficiente: `UNKNOWN` ou REVIEW.

Um `VIRTUAL_CANDIDATE` sem VM central correspondente não pode virar `READY/CREATE` de Device físico.

## 9. Virtualização centralizada

Em filiais:

```yaml
product:
  execution_role: network_proxy
virtualization:
  mode: centralized
```

O status deve mostrar:

```text
Inventário de virtualização: CENTRALIZED
Hypervisor local: NÃO REQUERIDO
```

O PLAN exibe os delegados com VM, interface, MAC, cluster, host físico, site e forma de correlação. Não se configura vCenter em cada filial.

## 10. Colisão de nomes SNMP

Dois equipamentos físicos podem publicar o mesmo `sysName`. O PLAN só resolve automaticamente quando existem:

- confiança HIGH;
- serial ou MAC único;
- nenhum conflito de IP;
- nenhum Device existente ambíguo.

Exemplo:

```text
SW-BA17-LB43JZ
SW-BA17-KPC2C1
```

O `sysName` original continua como nome observado.

## 11. Gerenciamento OOB

Um iDRAC com service tag correspondente a um servidor existente recebe `oob_parent_candidate`. A criação independente é mantida em REVIEW até associação segura ao equipamento físico.

## 12. Write guard

O PLAN calcula impacto antes da escrita:

```text
CREATE
UPDATE_SAFE
REPAIR_SAFE_VM_DUPLICATE
TOTAL
percentual sobre Devices existentes
```

Limites padrão:

```text
CREATE: 100
UPDATE_SAFE: 150
REPAIR_SAFE: 20
TOTAL: 200
PERCENT: 50%
```

Podem ser ajustados por:

```text
NETBOX_DISCOVERY_MAX_CREATE
NETBOX_DISCOVERY_MAX_UPDATE
NETBOX_DISCOVERY_MAX_REPAIR
NETBOX_DISCOVERY_MAX_TOTAL_CHANGES
NETBOX_DISCOVERY_MAX_CHANGE_PERCENT
```

Se um limite for excedido, itens elegíveis viram BLOCKED antes da primeira escrita.

## 13. Preservação de identidade live

Uma perda transitória de SNMP, banner ou fingerprint não rebaixa uma identidade específica já existente:

```text
LIVE_IDENTITY_PRESERVED_OVER_WEAK_OBSERVATION
```

Esse caminho é `READY/NOOP`.

## 14. REPAIR_SAFE de VM duplicada

Ordem protegida:

```text
1. revalidar Device, VM, interface, IP e MAC
2. bloquear primary/oob divergente
3. limpar referência primary/oob que aponta para o IP alvo
4. mover IP para virtualization.vminterface
5. definir primary IPv4 da VM se vazio
6. remover somente MACs e Device criados pelo produto
7. auditar convergência e idempotência
```

A VM nunca é removida.

## 15. Audit final

O audit confirma:

```text
Assets FAIL: 0
Checks FAIL: 0
novo PLAN sem CREATE/UPDATE_SAFE/REPAIR_SAFE elegível
```

`PASS_WITH_WARNINGS` só é aceitável com FAIL zero e WARN detalhado.

## 16. Run ID

Cada execução completa recebe:

```text
RUN ID: <SITE>-<UTC>-<8 HEX>
```

O identificador é salvo no relatório do runner.

## 17. Caminhos

```text
Aplicação:              /opt/netbox-discovery
Configuração:           /opt/netbox-discovery/config.yml
Config Hypervisor:      /etc/netbox-discovery/hypervisors.json
Relatórios:             /opt/netbox-discovery/reports
Backups:                /opt/netbox-discovery/backups
Lock global:            /var/lock/netbox-discovery-global.lock
```
