# netbox-discovery

Produto BKPCLOUD para descoberta, reconciliação e inventário seguro de infraestrutura no NetBox.

**Versão atual:** 1.11.0 — PRODUCT V1  
**Distribuição:** repositório público oficial `bkpcloud-app/netbox-discovery`  
**Canal padrão:** `stable`  
**NetBox BKPCLOUD:** `https://inventory.bkpcloud.app.br:8080`

> A documentação faz parte da release. O self-test e o CI bloqueiam publicação quando os documentos obrigatórios divergem do `VERSION`.

## Pipelines

### Network

```bash
netbox-discovery run
netbox-discovery run --apply
```

```text
DISCOVER V5
→ CLASSIFY V7
→ RECONCILE V5
→ PLAN V9
→ WRITE GUARD + PREFLIGHT GLOBAL FINALIZE
→ IMPORT READY normal V10
→ MAC RECONCILE
→ REPAIR_SAFE
→ AUDIT FINALIZE V9
```

### Hypervisor centralizado

O inventário de virtualização pode ser executado no coletor central. Proxies de filial usam `execution_role: network_proxy` e consultam os objetos já existentes no NetBox; não precisam configurar nem executar vCenter localmente.

```bash
netbox-discovery hypervisor configure
netbox-discovery hypervisor check
netbox-discovery hypervisor run
netbox-discovery hypervisor run --compare
netbox-discovery hypervisor run --apply
netbox-discovery hypervisor status
```

## 1.11.0 — identidade consolidada, autoridade e segurança

A 1.11.0 reúne em uma única release as melhorias de descoberta, classificação, reconciliação, nomes, virtualização, aplicação e auditoria.

### Motor único de identidade

`modules/product/identity.py` concentra:

- normalização e proveniência de fabricante, modelo, serial e firmware;
- `discovery_uid` estável por serial, chassis ou MAC;
- nome observado separado do nome efetivo administrado no NetBox;
- natureza física, virtual confirmada, candidata virtual ou desconhecida;
- recomendações objetivas para ativos em REVIEW.

### Equipamentos industriais

O classificador interpreta evidências estruturadas e read-only de:

```text
Siemens S7
EtherNet/IP / CIP Identity
BACnet
Modbus Device Identification
SNMP sysObjectID / ENTITY-MIB
```

Quando o protocolo fornece dados, o inventário mantém fabricante, modelo, serial, firmware, função industrial e fonte da evidência. Sem prova suficiente, continua genérico e vai para REVIEW; o produto não inventa modelo.

### Câmeras, NVRs e DVRs

ONVIF/WS-Discovery e fingerprints conhecidos distinguem câmera, NVR, DVR, encoder e equipamento de videomonitoramento ainda não resolvido. Fabricante, modelo, serial e firmware são utilizados quando realmente retornados pelo equipamento.

### Físico versus virtual

A correspondência com `virtualization.vminterface` no NetBox é autoritativa. OUI VMware, Hyper-V, KVM, Xen ou VirtualBox sozinho gera apenas `VIRTUAL_CANDIDATE`; nunca confirma uma VM nem autoriza criar um Device físico duplicado.

### Virtualização centralizada

Itens já pertencentes a VMs aparecem como `DELEGATED_VM/PASS`, incluindo VM, interface, MAC, cluster, host físico, site e forma de correlação. A filial não executa vCenter local.

### Nomes no NetBox

```text
Device existente no NetBox → nome protegido
Nome observado por SNMP/ONVIF/DNS → registrado separadamente
PATCH automático de name → proibido no importer
```

Nomes genéricos criados pelo produto podem ter identidade técnica enriquecida, mas um nome alterado manualmente não é desfeito pelo schedule.

### Nomes SNMP repetidos

Equipamentos físicos HIGH com `sysName` igual podem coexistir quando serial ou MAC demonstram identidades distintas. O PLAN usa sufixo determinístico por serial/MAC e mantém o `sysName` como nome observado.

### iDRAC e gerenciamento OOB

Quando o service tag identifica um servidor físico existente, o PLAN apresenta o pai provável e mantém o OOB em REVIEW até uma associação segura, evitando criar um servidor independente por engano.

### Write guard

Antes do APPLY, o PLAN mede CREATE, UPDATE_SAFE, REPAIR_SAFE e percentual de mudança. Um volume anormal transforma os itens elegíveis em BLOCKED antes da primeira escrita. O importer recalcula o PLAN V9 imediatamente antes de escrever.

Limites podem ser ajustados por ambiente:

```text
NETBOX_DISCOVERY_MAX_CREATE
NETBOX_DISCOVERY_MAX_UPDATE
NETBOX_DISCOVERY_MAX_REPAIR
NETBOX_DISCOVERY_MAX_TOTAL_CHANGES
NETBOX_DISCOVERY_MAX_CHANGE_PERCENT
```

### Run ID

Cada execução completa recebe um `run_id` único no relatório do runner para rastreabilidade operacional.

## 1.10.19 — qualidade de identidade do inventário

A 1.10.19 introduziu Printer-MIB, Moxa NPort 5210, nomes SNMP repetidos com identidade forte e preservação de Device Type específico diante de perda transitória de evidência.

### Impressoras

O DISCOVER consulta Printer-MIB de forma read-only e incorpora, quando disponíveis:

```text
prtGeneralPrinterName
prtGeneralSerialNumber
hrDeviceDescr
```

Um Device criado pelo produto com tipo genérico só pode receber um Device Type exato quando há match forte, confiança HIGH e fabricante/modelo explícitos. Device manual ou tipo não genérico nunca é substituído automaticamente.

### Moxa NPort 5210

```text
sysObjectID: .1.3.6.1.4.1.8691.2.7
Role: INDUSTRIAL_COMMUNICATION
Manufacturer: Moxa
Model: NPort 5210
Confidence: HIGH
```

### Preservação da identidade existente

Quando uma coleta momentânea perde evidência, mas SERIAL/MAC/IP apontam para um Device existente com identidade não genérica, o PLAN mantém o objeto live:

```text
LIVE_IDENTITY_PRESERVED_OVER_WEAK_OBSERVATION
```

## 1.10.18 — liberar primary IP antes de transferir o endereço

O reparo de Device duplicado de VM limpa primeiro a referência primary/oob do Device, depois move o IP para `virtualization.vminterface`, define primary IPv4 da VM quando necessário e só então remove o Device integralmente criado pelo produto.

## Caminhos de REPAIR_SAFE

```text
1. MAC VMware corresponde exatamente a uma interface live
2. VM única + uma interface sem MAC + MAC VMware forte
3. VM única + zero interfaces + MAC VMware forte → criar MGMT protegida
```

Todos os caminhos exigem:

- Device, interfaces e IP criados pelo produto;
- nenhum serial, rack, location, cluster, cabo ou objeto relacionado;
- exatamente um IP observado;
- VM inequívoca e sem outro primary IPv4;
- MAC VMware único e sem ownership conflitante.

## Segurança operacional

```text
netbox-discovery run          = dry-run
netbox-discovery run --apply  = escrita somente de READY
DELEGATED / REVIEW / BLOCKED  = não escrevem
DELETE de VM                  = proibido
DELETE de Device              = somente REPAIR_SAFE com ownership integral do produto
```

Network, Hypervisor, Compare e Update compartilham lock global. POST/PATCH/DELETE não recebem retry cego.

## Dell PowerVault MD32xx

```text
sysObjectID = .1.3.6.1.4.1.674.10893.2.31
2 endpoints válidos → 1 Device STORAGE com MGMT + MGMT-2
```

## Caminhos

```text
Aplicação:              /opt/netbox-discovery
Configuração principal: /opt/netbox-discovery/config.yml
Config Hypervisor:      /etc/netbox-discovery/hypervisors.json
Relatórios:             /opt/netbox-discovery/reports
Backups:                /opt/netbox-discovery/backups
Lock global:            /var/lock/netbox-discovery-global.lock
```

## Homologação

**CI PASS não equivale a LIVE PASS.** Estado oficial em `docs/HOMOLOGACAO.md`.
