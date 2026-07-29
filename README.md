# netbox-discovery

Produto BKPCLOUD para descoberta, reconciliação e inventário seguro de infraestrutura no NetBox.

**Versão atual:** 1.10.19 — PRODUCT V1  
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
DISCOVER V4
→ CLASSIFY V6
→ RECONCILE V5
→ PLAN V8
→ PREFLIGHT GLOBAL FINALIZE
→ IMPORT READY normal V9
→ MAC RECONCILE
→ REPAIR_SAFE
→ AUDIT FINALIZE V8
```

### Hypervisor

```bash
netbox-discovery hypervisor configure
netbox-discovery hypervisor check
netbox-discovery hypervisor run
netbox-discovery hypervisor run --compare
netbox-discovery hypervisor run --apply
netbox-discovery hypervisor status
```

## 1.10.19 — qualidade de identidade do inventário

A 1.10.19 transforma evidência que antes terminava como objeto genérico em identidade útil, sem tornar a escrita menos conservadora.

### Impressoras

O DISCOVER consulta Printer-MIB de forma read-only e incorpora, quando disponíveis:

```text
prtGeneralPrinterName
prtGeneralSerialNumber
hrDeviceDescr
```

Fabricante, modelo e serial explícitos passam pelo CLASSIFY V6. Um Device já criado pelo produto com tipo genérico só pode receber um Device Type exato quando:

```text
match forte por SERIAL/MAC/IP
+ confiança HIGH
+ Device criado pelo netbox-discovery
+ tipo atual reconhecidamente genérico
+ fabricante/modelo exatos no novo discovery
```

Device manual ou tipo não genérico nunca é substituído automaticamente.

### Moxa NPort 5210

O `sysObjectID .1.3.6.1.4.1.8691.2.7` é classificado como:

```text
Role: INDUSTRIAL_COMMUNICATION
Manufacturer: Moxa
Model: NPort 5210
Confidence: HIGH
```

### Nomes SNMP repetidos

Dois equipamentos físicos HIGH com o mesmo `sysName` não permanecem bloqueados apenas pelo nome quando possuem identidades fortes distintas. O PLAN cria nomes determinísticos com sufixo de serial ou MAC, por exemplo:

```text
SW-BA17-LB43JZ
SW-BA17-KPC2C1
```

A regra não é aplicada quando existe identidade fraca, conflito de IP, objeto existente ou ambiguidade de serial/MAC.

### Preservação da identidade existente

Quando uma coleta momentânea perde evidência, mas SERIAL/MAC/IP apontam para um Device existente com identidade não genérica, o PLAN mantém o objeto live e registra:

```text
LIVE_IDENTITY_PRESERVED_OVER_WEAK_OBSERVATION
```

Não existe escrita nesse caminho. Também são reconhecidos aliases de fabricante, como `Dell Inc.` e `Dell`, para não gerar drift falso.

## 1.10.18 — liberar primary IP antes de transferir o endereço

A execução live da 1.10.17 criou corretamente a interface `MGMT` e o MAC VMware na VM ID 359. O NetBox, porém, bloqueou a transferência do IP porque `10.1.1.111/24` ainda estava configurado como primary IPv4 do Device duplicado:

```text
Cannot reassign IP address while it is designated as the primary IP for the parent object
```

A 1.10.18 corrige a ordem do reparo:

```text
1. revalidar Device, VM, interface, IP, MAC e ownership
2. confirmar que primary_ip4/primary_ip6/oob_ip do Device estão vazios ou apontam para o mesmo IP alvo
3. limpar a referência primary/oob do Device
4. mover o IP para virtualization.vminterface
5. definir primary IPv4 da VM, se vazio
6. remover somente o Device duplicado criado pelo produto
7. auditar convergência e idempotência
```

Se qualquer primary/oob do Device apontar para outro IP, o reparo bloqueia antes da transferência e antes do DELETE.

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
