# Segurança do repositório

**Versão da política:** 1.11.2

O `netbox-discovery` é distribuído em repositório público. Código e documentação podem ser públicos; dados operacionais e credenciais de clientes não podem.

## Nunca versionar

- configuração real de cliente;
- tokens, communities e senhas;
- credenciais VMware, Proxmox, Hyper-V, ONVIF, NetBox ou iDRAC;
- chaves privadas;
- relatórios, journals, logs e backups reais.

## Decisões Network

```text
READY/CREATE                    → escreve somente com --apply
READY/UPDATE_SAFE               → escreve somente com --apply
READY/REPAIR_SAFE_VM_DUPLICATE  → escreve após write guard e preflight
READY/NOOP                      → não altera
DELEGATED                       → não escreve
REVIEW                          → não escreve
BLOCKED                         → não escreve
```

## Autoridade e nomes

```text
Nome de Device existente → autoridade do NetBox
Nome SNMP/ONVIF/DNS      → observação separada
PATCH automático de name → proibido no importer
```

## Windows Server x Workstation

Role de Windows só pode ser separado por fonte forte:

```text
SMB OS explícito
CPE Windows
fingerprint/classe de SO com alta precisão
```

RDP, porta aberta ou hostname isolado não autorizam troca.

Correção automática `SERVER-WINDOWS ↔ WORKSTATION-WINDOWS` exige:

1. Device criado pelo produto;
2. match forte por serial, MAC ou IP;
3. confiança HIGH;
4. fonte SMB/CPE/fingerprint forte;
5. role atual dentro da família Windows;
6. PLAN com `WINDOWS_ROLE_CORRECTION_EXPLICIT_OS`;
7. revalidação no importer.

Device manual ou role fora dessa família é bloqueado.

## Serial

O serial é tratado como identidade forte e recebe validação específica.

São proibidos:

- placeholders, sequências de teste e caracteres repetidos;
- IP ou MAC usados como serial;
- serial igual a modelo ou hostname;
- escrita com `serial_confidence` LOW/NONE/CONFLICT;
- escolha automática quando fontes fortes equivalentes divergem.

O PLAN deve manter fonte, candidatos, rejeições e conflito. O importer só preenche serial vazio quando a evidência é HIGH ou MEDIUM e não há conflito.

## Printer-MIB

A coleta é read-only e limitada a identidade:

```text
prtGeneralPrinterName
prtGeneralSerialNumber
hrDeviceDescr
```

Nenhum SNMP SET é executado. Valores padrão não são gravados.

## Hikvision e ONVIF

A coleta adicional é anônima e somente leitura:

```text
GET /ISAPI/System/deviceInfo
ONVIF GetDeviceInformation
```

Ela só é tentada em candidatos fortes de CFTV. Não força autenticação, não tenta senha e não executa controle de câmera. Falha ou HTTP 401/403 significa apenas ausência de enriquecimento.

## Coleta industrial

São permitidas somente consultas de identificação read-only por SNMP, Siemens S7 information, EtherNet/IP CIP Identity, BACnet information e Modbus device identification. Não há SNMP SET nem comando de controle de processo.

## Físico versus virtual

Correspondência com `virtualization.vminterface` e inventário central é autoritativa. OUI VMware/Hyper-V/KVM/Xen/VirtualBox sozinho é apenas candidato e nunca autoriza criar Device físico duplicado.

## Virtualização centralizada

Filiais operam como `network_proxy`. Ausência de vCenter local não é falha. A VM nunca é removida pelo pipeline Network.

## Write guard

Antes da primeira escrita, o PLAN mede CREATE, UPDATE_SAFE, REPAIR_SAFE, total e percentual. Limites padrão:

```text
CREATE: 25
UPDATE_SAFE: 50
REPAIR_SAFE: 20
TOTAL: 75
PERCENT: 20%
```

Impacto acima do limite converte ações elegíveis em BLOCKED/NOOP.

## Preflight global

Antes da escrita:

1. recalcular PLAN V9;
2. validar write guard;
3. reler Device, VM, interfaces, IPs, MACs e relações;
4. bloquear drift ou consulta incompleta;
5. criar journal;
6. somente então permitir POST/PATCH/DELETE protegido.

## REPAIR_SAFE e DELETE

Não existe DELETE genérico no Network. A VM nunca é removida. O único DELETE automático permitido é Device duplicado de VM integralmente criado pelo produto e sem vínculo manual.

## Concorrência e rastreabilidade

Network, Hypervisor, Compare e Update compartilham lock global.

- cada runner recebe `run_id`;
- POST/PATCH/DELETE não recebem retry cego;
- falha parcial fica registrada;
- não usar correções manuais em massa para contornar o produto.

## Credenciais Hypervisor

```text
/etc/netbox-discovery/hypervisors.json
```

Permissão esperada: `0600`.

## Homologação

`CI PASS` não significa `LIVE PASS`. A primeira execução de uma release no site deve ser dry-run.
