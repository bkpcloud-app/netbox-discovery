## V1.11.2 — Windows role separation and serial quality

Release construída sobre o dry-run real do FBA para separar Windows Server de Workstation e aumentar a confiabilidade de serial em impressoras, câmeras, storage, industrial e servidores.

### Windows Server x Workstation

```text
WINDOWS_SERVER      → SERVER-WINDOWS
WINDOWS_WORKSTATION → WORKSTATION-WINDOWS
```

A edição só é aceita por SMB OS, CPE Windows ou fingerprint de SO com alta precisão. Porta RDP/SMB isolada e Product_Version genérico não decidem a edição. Conflito de evidência mantém REVIEW.

Correção automática de role existente exige Device criado pelo produto, match forte, confiança HIGH, fonte explícita e role atual dentro da família Windows. Device manual é preservado.

### Serial

- agrega candidatos de ONVIF/ISAPI, Printer-MIB, FibreAlliance, iDRAC, protocolos industriais, ENTITY-MIB e descrição explícita;
- registra fonte, confiança, candidatos, rejeições e conflitos;
- rejeita placeholder, teste, caracteres repetidos, serial curto/longo, IP, MAC, modelo e hostname;
- conflito entre fontes fortes deixa serial vazio e bloqueia escrita;
- importer só preenche serial vazio com evidência HIGH/MEDIUM sem conflito.

### Impressoras

- avalia todas as instâncias de `prtGeneralSerialNumber`;
- extrai serial rotulado de `hrDeviceDescr` quando explícito;
- rejeita valores padrão como `03000000`;
- mantém normalização de fabricante/modelo e nome manual protegido.

### Hikvision / ONVIF

Para candidatos fortes, tenta consulta anônima e read-only:

```text
GET /ISAPI/System/deviceInfo
POST /onvif/device_service → GetDeviceInformation
```

Quando permitido pelo equipamento, coleta fabricante, modelo, firmware, serial, hardware ID e nome. Sem resposta anônima, não inventa dados.

### Componentes

```text
network_v5.py       4.5-product
classifier_v7.py    5.3-product
planner_v9.py       5.0-product
importer_v10.py     5.9-product
auditor_v9.py       6.7-product
pipeline            3.0-product
runner              3.0-product
```

### Regressões

- Windows Server 2022 identificado como server;
- Windows 11 identificado como workstation;
- RDP genérico não decide edição;
- evidência Windows conflitante não altera role;
- Device manual não recebe correção;
- serial placeholder rejeitado;
- serial forte conflitante bloqueado;
- Printer-MIB escolhe serial válido;
- Hikvision XML retorna modelo, firmware e serial;
- importer recusa role arbitrário.

Estado inicial: **CI/NOT LIVE até novo dry-run no FBA**.

---

## V1.11.1 — Stable updater release and live dry-run corrections

Publicou a consolidação 1.11 no canal `stable` e corrigiu os pontos encontrados no primeiro dry-run do FBA: falsos positivos de CFTV, modelo Kyocera duplicado, serial Pantum placeholder, detalhes parciais de VM e write guard mais conservador.

---

## V1.11.0 — Consolidated identity, authority and write safety

- motor central de identidade e proveniência;
- industrial estruturado: S7, EtherNet/IP, BACnet e Modbus;
- CFTV por ONVIF/fingerprint;
- OUI virtual como candidato, não confirmação;
- nome existente protegido e PATCH de name proibido;
- VM central detalhada como DELEGATED;
- colisão segura de sysName por serial/MAC;
- write guard e preflight global.

---

## V1.10.19 — Identity quality and safe generic enrichment

Introduziu Printer-MIB, Moxa NPort 5210, colisão segura de nomes e preservação de identidade forte diante de perda transitória.

## V1.10.18 — Primary IP reassignment order

Corrigiu a ordem do REPAIR_SAFE: limpar primary/oob do Device antes de mover o IP para a interface da VM.
