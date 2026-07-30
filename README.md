# netbox-discovery

Produto BKPCLOUD para descoberta, reconciliação e inventário seguro de infraestrutura no NetBox.

**Versão atual:** 1.11.2 — PRODUCT V1  
**Distribuição:** repositório público oficial `bkpcloud-app/netbox-discovery`  
**Canal padrão:** `stable`  
**NetBox BKPCLOUD:** `https://inventory.bkpcloud.app.br:8080`

> A documentação faz parte da release. O self-test e o CI bloqueiam publicação quando os documentos obrigatórios divergem do `VERSION`.

## Atualização e primeira execução

```bash
netbox-discovery update run
netbox-discovery version
netbox-discovery self-test
netbox-discovery run
```

`netbox-discovery run` é sempre dry-run. A escrita só ocorre com `netbox-discovery run --apply` depois da revisão do PLAN.

## Pipeline Network

```text
DISCOVER V5 / 4.5-product
→ CLASSIFY V7 / 5.3-product
→ RECONCILE V5
→ PLAN V9 / 5.0-product
→ WRITE GUARD + PREFLIGHT GLOBAL
→ IMPORT V10 / 5.9-product
→ MAC RECONCILE
→ REPAIR_SAFE
→ AUDIT FINALIZE V9
```

## Windows Server x Workstation

A versão 1.11.2 separa explicitamente no NetBox:

```text
Windows Server                 → SERVER-WINDOWS
Windows 11/10/8/7 Workstation → WORKSTATION-WINDOWS
```

A separação só ocorre quando a edição é comprovada por evidência forte, como:

```text
smb-os-discovery
smb-system-info
CPE de serviço Windows
fingerprint de SO com alta precisão
```

Portas Windows ou uma versão genérica de RDP não bastam para decidir. Sem prova, o ativo permanece `WINDOWS_HOST` em REVIEW. Evidências fortes conflitantes também permanecem em REVIEW.

A correção automática de role de um Device existente exige simultaneamente:

- Device criado pelo `netbox-discovery`;
- match forte por serial, MAC ou IP;
- confiança HIGH;
- edição comprovada por SMB/CPE/fingerprint forte;
- role atual dentro da família Windows Server/Workstation.

Device manual nunca recebe troca automática de role.

## Qualidade de serial

O produto reúne candidatos de serial vindos de:

```text
ONVIF / Hikvision ISAPI
Printer-MIB
FibreAlliance / storage
Dell iDRAC service tag
Siemens S7, EtherNet/IP, BACnet e Modbus
ENTITY-MIB e descrições SNMP explícitas
```

A seleção considera a autoridade da fonte. São rejeitados:

- valores padrão, de teste ou placeholders;
- serial curto demais, longo demais ou repetitivo;
- IP ou MAC usado como serial;
- valor igual ao modelo ou nome do equipamento;
- candidatos fortes conflitantes.

O PLAN registra `serial_candidates`, `serial_rejections`, `serial_confidence` e `serial_conflict`. Serial conflitante não é gravado.

## Impressoras

A coleta read-only usa:

```text
prtGeneralPrinterName
prtGeneralSerialNumber
hrDeviceDescr
```

Ela avalia todos os candidatos de serial, rejeita valores padrão e normaliza fabricante/modelo. Um nome manual existente no NetBox continua protegido.

## Hikvision e CFTV

CFTV exige evidência específica; fabricante por MAC ou uma página web genérica não bastam. Para candidatos fortes, a coleta tenta de forma read-only e sem credencial:

```text
Hikvision ISAPI /ISAPI/System/deviceInfo
ONVIF GetDeviceInformation
```

Quando o equipamento permite consulta anônima, o produto obtém fabricante, modelo, firmware, serial, hardware ID e nome. Quando exige autenticação, nenhum serial é inventado e o ativo continua em REVIEW com a evidência disponível.

## Industrial

O classificador interpreta evidências read-only de Siemens S7, EtherNet/IP/CIP, BACnet, Modbus Device Identification, SNMP sysObjectID e ENTITY-MIB. Modelo e função só são elevados com prova estruturada.

## Virtualização centralizada

Filiais usam:

```yaml
product:
  execution_role: network_proxy
virtualization:
  mode: centralized
```

O coletor central mantém vCenter, clusters, hosts, VMs, interfaces e IPs. A descoberta da filial consulta o NetBox e marca IPs de VM como `DELEGATED_VM/PASS`; não cria Device físico duplicado.

## Autoridade de nomes

```text
Device existente no NetBox → nome protegido
Nome SNMP/ONVIF/DNS       → observado separadamente
PATCH automático de name  → proibido no importer
```

## Colisão de sysName

Dois equipamentos físicos HIGH podem publicar o mesmo `sysName` quando serial ou MAC provam identidades distintas. O nome efetivo recebe sufixo determinístico e o `sysName` original permanece como nome observado.

## Write guard

Limites padrão:

```text
CREATE:      25
UPDATE_SAFE: 50
REPAIR_SAFE: 20
TOTAL:       75
PERCENT:     20%
```

Impacto anormal transforma todas as ações elegíveis em `BLOCKED/NOOP` antes da primeira escrita.

## Segurança operacional

```text
netbox-discovery run          = dry-run
netbox-discovery run --apply  = escrita somente de READY
DELEGATED / REVIEW / BLOCKED  = não escrevem
DELETE de VM                  = proibido
Nome manual                   = protegido
```

Network, Hypervisor, Compare e Update compartilham lock global. POST/PATCH/DELETE não recebem retry cego.

## Caminhos

```text
Aplicação:              /opt/netbox-discovery
Configuração principal: /opt/netbox-discovery/config.yml
Config Hypervisor:      /etc/netbox-discovery/hypervisors.json
Relatórios:             /opt/netbox-discovery/reports
Backups de update:      /var/lib/netbox-discovery/update-backups
Lock global:            /var/lock/netbox-discovery-global.lock
```

## Homologação

**CI PASS não equivale a LIVE PASS.** O primeiro uso de cada release no site deve ser `netbox-discovery run`, sem `--apply`. Estado oficial em `docs/HOMOLOGACAO.md`.
