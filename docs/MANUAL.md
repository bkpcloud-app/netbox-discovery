# Manual Operacional — netbox-discovery

**Produto:** netbox-discovery  
**Versão:** 1.11.2 — PRODUCT V1  
**Distribuição oficial:** `bkpcloud-app/netbox-discovery`  
**Canal de produção:** `stable`  
**NetBox BKPCLOUD:** `https://inventory.bkpcloud.app.br:8080`

> `CI PASS` não equivale a `LIVE PASS`. Estado real em `docs/HOMOLOGACAO.md`.

## 1. Atualização

A atualização oficial não exige download ou instalação manual:

```bash
netbox-discovery update run
```

O updater consulta o canal `stable`, valida as versões, clona a release em área temporária, executa self-test, cria backup, instala, testa novamente e faz rollback automático se necessário.

Verificação:

```bash
netbox-discovery version
netbox-discovery self-test
netbox-discovery status
```

## 2. Execução Network

```bash
netbox-discovery run
netbox-discovery run --apply
```

Fluxo 1.11.2:

```text
DISCOVER V5 / 4.5-product
→ CLASSIFY V7 / 5.3-product
→ RECONCILE V5
→ PLAN V9 / 5.0-product
→ WRITE GUARD + PREFLIGHT GLOBAL FINALIZE
→ IMPORT V10 / 5.9-product
→ MAC RECONCILE
→ REPAIR_SAFE
→ AUDIT FINALIZE V9
```

`run` é read-only. `run --apply` recalcula o PLAN imediatamente antes da escrita.

## 3. Decisões

| Decisão/Ação | Significado | Escrita |
|---|---|---|
| `READY/CREATE` | novo Device validado | somente com `--apply` |
| `READY/UPDATE_SAFE` | enriquecimento ou correção protegida | somente com `--apply` |
| `READY/REPAIR_SAFE_VM_DUPLICATE` | corrige Device duplicado criado pelo produto | após preflight global |
| `READY/NOOP` | convergente ou preservado | não altera |
| `DELEGATED` | ownership da VM no inventário central | não |
| `REVIEW` | evidência insuficiente ou associação humana | não |
| `BLOCKED` | conflito forte ou write guard | não |

## 4. Windows Server e Workstation

A classificação interna e o destino no NetBox são:

```text
WINDOWS_SERVER      → SERVER-WINDOWS
WINDOWS_WORKSTATION → WORKSTATION-WINDOWS
DOMAIN_CONTROLLER   → SERVER-WINDOWS
```

A edição é aceita somente quando aparece em fonte forte:

```text
smb-os-discovery
smb-system-info
CPE Windows do serviço
OS CPE/fingerprint/classe com alta precisão
```

Exemplos reconhecidos:

```text
Windows Server 2025/2022/2019/2016/2012 R2/2012/2008 R2/2008
Windows 11/10/8.1/8/7/Vista/XP
```

Não são provas suficientes:

```text
porta 445 aberta
porta RDP aberta
Product_Version 10.0.x isolado
hostname ou padrão de nome
```

Sem prova, permanece `WINDOWS_HOST` e vai para REVIEW. Evidência forte conflitante gera `windows_family: CONFLICT` e não altera role.

### Correção segura de role existente

Uma troca `SERVER-WINDOWS ↔ WORKSTATION-WINDOWS` só pode ocorrer quando:

1. o Device foi criado pelo produto;
2. SERIAL, MAC ou IP apontam para esse mesmo Device;
3. a classificação é HIGH;
4. SMB/CPE/fingerprint forte comprova a edição;
5. o role atual já pertence à família Windows;
6. o PLAN marca `WINDOWS_ROLE_CORRECTION_EXPLICIT_OS`;
7. o importer revalida tudo antes do PATCH.

Device manual ou role de outra categoria nunca é alterado automaticamente.

## 5. Política de serial

O produto monta uma lista ordenada de candidatos com fonte e peso. Ordem geral:

```text
ONVIF/Hikvision ISAPI
Printer-MIB
FibreAlliance/storage
Dell iDRAC/service tag
S7/EtherNet-IP/BACnet/Modbus
ENTITY-MIB primário
ENTITY-MIB secundário
SNMP/descrição explícita
```

Campos disponíveis:

```text
serial
serial_source
serial_confidence
serial_candidates
serial_rejections
serial_conflict
serial_evidence_count
```

São rejeitados:

- `03000000` e outros valores conhecidos de fábrica/teste;
- sequências simples e caracteres repetidos;
- serial com menos de 5 ou mais de 64 caracteres;
- IP, MAC, modelo ou hostname usados como serial;
- marcadores como UNKNOWN, DEFAULT, SVCTAG e TO BE FILLED BY OEM.

Quando duas fontes fortes do mesmo nível retornam seriais diferentes:

```text
serial_confidence: CONFLICT
serial: vazio
escrita: bloqueada
```

O importer só preenche serial vazio com evidência HIGH ou MEDIUM e sem conflito.

## 6. Impressoras

Coleta read-only:

```text
prtGeneralPrinterName
prtGeneralSerialNumber
hrDeviceDescr
```

A versão 1.11.2:

- avalia todas as instâncias de serial retornadas;
- extrai somente rótulos explícitos de serial das descrições;
- rejeita placeholder;
- normaliza fabricante e modelo;
- mantém nome manual protegido;
- melhora Device Type genérico apenas em Device criado pelo produto e com identidade HIGH.

## 7. Hikvision e CFTV

CFTV só é classificado com evidência específica: ONVIF, modelo conhecido, UI/portas coerentes ou fingerprint explícito. OUI ou web genérica não bastam.

Para candidatos fortes, a coleta tenta de forma anônima e somente leitura:

```text
GET  /ISAPI/System/deviceInfo
POST /onvif/device_service → GetDeviceInformation
```

Dados possíveis:

```text
manufacturer
model
firmware
serial
hardware_id
device_name
```

Se o equipamento exigir autenticação, a coleta não força acesso, não inventa valores e mantém o ativo em REVIEW quando necessário.

## 8. Autoridade dos dados

```text
Nome de Device existente     → NetBox
Nome observado               → SNMP, ONVIF, DNS ou protocolo
Role Windows                 → edição comprovada por SMB/CPE/fingerprint
VM, cluster e VM interface   → vCenter central / NetBox virtualization
Fabricante/modelo/serial     → protocolo específico ou ENTITY-MIB
IP ativo                     → descoberta de rede
```

O importer proíbe PATCH automático de `name`.

## 9. Identidade consolidada

O motor mantém:

```text
observed_name
observed_name_source
discovery_uid
asset_nature
asset_nature_source
identity_provenance
review_recommendations
```

`discovery_uid` prefere serial, chassis MAC e MAC de gerenciamento. IP e nome só entram em identidade fraca quando nenhuma fonte melhor existe.

## 10. Industrial

A coleta é somente leitura e interpreta Siemens S7, EtherNet/IP/CIP, BACnet, Modbus Device Identification, SNMP sysObjectID e ENTITY-MIB.

Papéis possíveis:

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

Sem modelo/função estruturados, permanece genérico e em REVIEW.

## 11. Físico e virtual

Ordem de autoridade:

1. IP ou MAC pertencente a `virtualization.vminterface`: VM confirmada.
2. Inventário central do vCenter: VM confirmada.
3. Hardware com modelo e serial fortes: físico confirmado.
4. OUI VMware/Hyper-V/KVM/Xen/VirtualBox: apenas candidato.
5. Evidência insuficiente: UNKNOWN/REVIEW.

OUI virtual isolado nunca autoriza criar Device físico duplicado.

## 12. Virtualização centralizada

Em filiais:

```yaml
product:
  execution_role: network_proxy
virtualization:
  mode: centralized
```

Status esperado:

```text
Inventário de virtualização: CENTRALIZED
Hypervisor local: NÃO REQUERIDO
```

`DELEGATED_VM` apresenta VM, interface, MAC, cluster, host físico, site e forma de correlação.

## 13. Colisão de nomes SNMP

Dois equipamentos físicos podem publicar o mesmo `sysName`. A resolução automática exige confiança HIGH, serial ou MAC único e ausência de conflito de IP.

Exemplo:

```text
SW-BA17-LB43JZ
SW-BA17-KPC2C1
```

O nome observado permanece `SW-BA17`.

## 14. Gerenciamento OOB

Um iDRAC com service tag correspondente a servidor físico recebe `oob_parent_candidate`. Criação independente permanece em REVIEW até associação segura.

## 15. Write guard

Limites padrão:

```text
CREATE: 25
UPDATE_SAFE: 50
REPAIR_SAFE: 20
TOTAL: 75
PERCENT: 20%
```

Variáveis opcionais:

```text
NETBOX_DISCOVERY_MAX_CREATE
NETBOX_DISCOVERY_MAX_UPDATE
NETBOX_DISCOVERY_MAX_REPAIR
NETBOX_DISCOVERY_MAX_TOTAL_CHANGES
NETBOX_DISCOVERY_MAX_CHANGE_PERCENT
```

Se um limite for excedido, ações elegíveis viram BLOCKED antes da primeira escrita.

## 16. REPAIR_SAFE de VM duplicada

Ordem protegida:

```text
revalidar ownership
→ limpar primary/oob do Device
→ mover IP para virtualization.vminterface
→ definir primary IPv4 da VM
→ remover somente o Device duplicado criado pelo produto
→ auditar convergência
```

A VM nunca é removida.

## 17. Auditoria

LIVE PASS exige:

```text
PREFLIGHT GLOBAL FINALIZE: OK
WRITE GUARD: PASS
Runtime blocked: 0
Erros: 0
Assets FAIL: 0
Checks FAIL: 0
preview posterior sem mudança elegível inesperada
```

## 18. Caminhos

```text
Aplicação:              /opt/netbox-discovery
Configuração:           /opt/netbox-discovery/config.yml
Config Hypervisor:      /etc/netbox-discovery/hypervisors.json
Relatórios:             /opt/netbox-discovery/reports
Backups de update:      /var/lib/netbox-discovery/update-backups
Lock global:            /var/lock/netbox-discovery-global.lock
```
