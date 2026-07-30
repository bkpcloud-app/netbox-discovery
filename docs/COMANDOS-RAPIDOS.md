# netbox-discovery 1.11.2 — Comandos rápidos

## Atualizar e validar

Execute um por vez:

```bash
netbox-discovery update run
```

```bash
netbox-discovery version
```

```bash
netbox-discovery self-test
```

```bash
netbox-discovery status
```

```bash
netbox-discovery run
```

O último comando é dry-run. Não grava no NetBox.

## Versões esperadas

```text
Versão: 1.11.2
Discovery: 4.5-product
Classifier: 5.3-product
Planner: 5.0-product
Importer: 5.9-product
Auditor: 6.7-product
Pipeline: 3.0-product
Runner: 3.0-product
Identity engine: 1.0-product
```

## Windows no NetBox

```text
Windows Server comprovado     → SERVER-WINDOWS
Windows 11/10 comprovado      → WORKSTATION-WINDOWS
Edição não comprovada         → WINDOWS_HOST / REVIEW
Evidências fortes conflitantes → REVIEW
```

Fontes aceitas para separar:

```text
smb-os-discovery
smb-system-info
Windows CPE
OS fingerprint com alta precisão
```

RDP ou porta 445 isolados não bastam.

## Serial

Procure no PLAN por:

```text
Serial / fonte
Serial confidence
Serial candidates
Serial rejections
Serial conflict
```

Serial placeholder ou conflitante não é gravado.

Fontes principais:

```text
Hikvision ISAPI / ONVIF
Printer-MIB
FibreAlliance
Dell iDRAC
S7 / EtherNet-IP / BACnet / Modbus
ENTITY-MIB
```

## Impressoras

```text
prtGeneralPrinterName
prtGeneralSerialNumber
hrDeviceDescr
```

O produto avalia vários candidatos e rejeita valores padrão, inclusive `03000000`.

## Hikvision

Para candidatos fortes, a coleta tenta read-only:

```text
/ISAPI/System/deviceInfo
ONVIF GetDeviceInformation
```

Sem resposta anônima, não inventa serial.

## Virtualização centralizada

```text
Função desta instalação: network_proxy
Inventário de virtualização: CENTRALIZED
Hypervisor local: NÃO REQUERIDO
```

## Nome manual

```text
Nome existente no NetBox   → preservado
Nome observado por SNMP    → separado
PATCH automático de name   → bloqueado
```

## Write guard

```text
CREATE: 25
UPDATE_SAFE: 50
REPAIR_SAFE: 20
TOTAL: 75
PERCENT: 20%
```

Se aparecer `WRITE GUARD: BLOCK`, nenhuma ação elegível é escrita.

## Política

```text
READY/CREATE                    → escreve somente com --apply
READY/UPDATE_SAFE               → escreve somente com --apply
READY/REPAIR_SAFE_VM_DUPLICATE  → escreve após preflight
DELEGATED                       → não escreve
REVIEW                          → não escreve
BLOCKED                         → não escreve
DELETE de VM                    → NÃO
```

## APPLY

Somente depois de revisar e aprovar o dry-run:

```bash
netbox-discovery run --apply
```

CI PASS não significa LIVE PASS.
