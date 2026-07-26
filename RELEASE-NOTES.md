## V1.8.0 — Hypervisor integrado e endpoint BKPCLOUD

Release de produto que adiciona inventário de virtualização sem alterar o pipeline de rede existente.

### Endpoint

- fixa o NetBox em `https://inventory.bkpcloud.app.br:8080`;
- `init`/`configure` deixam de pedir a URL;
- runtime recusa `config.yml` apontando para outro NetBox.

### Hypervisor

- adiciona `netbox-discovery hypervisor`;
- conectores VMware vCenter/ESXi, Proxmox VE e Hyper-V WinRM/NTLM;
- comandos `configure`, `check`, `run`, `run --apply`, `status` e `scheduler`;
- scheduler independente do pipeline de rede;
- não existe `full-run`;
- escopo padrão por redes configuradas do Site, permitindo vCenter/manager central;
- cria/reconcilia Prefixes explícitos do Site, Clusters, hosts, VMs/containers, interfaces, MACs e IPs;
- Proxmox usa UUID quando disponível e identidade estável baseada em source/VMID como fallback;
- disco de VM é convertido corretamente para MB no modelo NetBox.

### Segurança e idempotência

- dry-run por padrão;
- replanejamento/preflight antes da primeira escrita;
- conflitos de IP, MAC, identidade, Role e Cluster Type viram REVIEW/bloqueio antes da escrita;
- preserva nomes manuais de Devices, VMs e interfaces já vinculadas;
- atualiza pinning de VM migrada entre hosts do mesmo cluster;
- não executa DELETE;
- credenciais Hypervisor ficam em `/etc/netbox-discovery/hypervisors.json` com proteção root-only;
- dependências de VMware/Hyper-V são instaladas juntas sob `/opt/netbox-discovery/vendor` somente quando um desses conectores é necessário.

## V1.7.0 — Estabilização de classificação e inventário

Release consolidada após a homologação do FFT, sem alteração da política de escrita: somente itens `READY` podem ser aplicados.

### Classificação e identidade

- reconhece WEG SRW01-ETH com evidência industrial forte;
- reconhece Siemens PAC3220 e SCALANCE XM416-4C;
- reconhece YTEK Monitory e interface web Aruba/HPE;
- reconhece o footprint CFTV observado (RTSP 554 + server port 8000 + UI Hikvision) como `VIDEO_SURVEILLANCE_DEVICE` HIGH sem inventar CAMERA/NVR/DVR;
- prioriza identidade física (ENTITY-MIB, SNMP e OUI) sobre banners de aplicação/TLS para fabricante;
- ignora nomes genéricos como `sysName Not Set`;
- aproveita modelo/serial explícitos de APC e Siemens S7;
- aproveita service tag válido do iDRAC quando o certificado contém apenas `SVCTAG`.

### Discovery e operação

- adiciona probe CFTV direcionado antes do Deep TCP 1000;
- mantém o Deep TCP 1000 como fallback;
- padroniza o timestamp do DISCOVER em UTC;
- PLAN passa a destacar ações realmente elegíveis para escrita (`READY`).

### Segurança

- preserva as proteções da V1.6.0 para MAC inválido, serial genérico, rede/broadcast e identidade LLDP;
- IP já atribuído a objeto externo do NetBox continua em `REVIEW`;
- nenhuma rotina de descoberta autentica em câmeras ou tenta credenciais padrão.

## V1.6.0 — Reconciliação segura e descoberta CFTV

Release de produto com correções de identidade observadas na homologação FFT e
enriquecimento de descoberta/classificação para câmeras IP e gravadores.

### Reconciliação

- MAC broadcast `FF:FF:FF:FF:FF:FF` nunca é usado como identidade;
- MAC zerado e MAC multicast/group nunca provocam merge;
- seriais genéricos como `SVCTAG`, `SERIALNUMBER`, `UNKNOWN` e similares são ignorados;
- LLDP chassis-id válido continua sendo evidência forte e pode gerar identidade estável;
- serial inválido não é propagado ao PLAN;
- evita o merge falso de dispositivos distintos observado no FFT.

### Endereçamento

- o resultado do discovery é restrito aos hosts válidos dos prefixos configurados;
- endereços IPv4 de rede e broadcast não entram no pipeline mesmo que Nmap receba resposta;
- exclusões configuradas também são aplicadas ao resultado do discovery primário.

### CFTV

- adiciona TCP 8000 e portas complementares de CFTV ao discovery/rescue;
- adiciona UDP 3702 e `wsdd-discover` seguro para WS-Discovery/ONVIF;
- mantém RTSP 554, 34567 e 37777 como evidências;
- fingerprints para Hikvision, Dahua, Axis, Vivotek, Hanwha Vision, Bosch, Pelco,
  Uniview, Reolink, Intelbras, Avigilon, TP-Link VIGI/Tapo e Ubiquiti Protect;
- classifica `CAMERA`, `NVR`, `DVR`, `VIDEO_ENCODER`;
- quando há fabricante/portas de CFTV mas não há prova do papel exato, usa
  `VIDEO_SURVEILLANCE_DEVICE` com confiança MEDIUM para forçar REVIEW, em vez de
  assumir câmera incorretamente;
- adiciona modelos genéricos e roles correspondentes no PLAN.

### Segurança operacional

- nenhuma tentativa de senha padrão;
- nenhuma autenticação forçada;
- nenhuma alteração em câmera/NVR/DVR;
- discovery continua read-only até `run --apply`.

## V1.5.2 — Correção do instalador e sincronização de versão

Correções identificadas durante a homologação de upgrade em proxy:

- sincroniza `VERSION` da raiz e `netbox-discovery/VERSION`;
- corrige o loop do `install.sh`: `config.ymbin` passa a ser `config.yml bin`;
- o código novo em `bin`, `lib` e `modules` volta a ser instalado corretamente;
- corrige a detecção de `/opt/netbox-discovery/config.yml` no `bootstrap.sh`;
- mantém a configuração operacional existente durante upgrade;
- preserva a correção de DNS reverso da V1.5.1.

## V1.5.1 — Correção de DNS reverso

Homologação em um proxy novo identificou uma dependência de DNS reverso
não tratada pelo produto.

Correções:

- `dig` passa a ser instalado automaticamente pelo bootstrap;
- RHEL/CentOS utiliza `bind-utils`;
- Debian/Ubuntu utiliza `dnsutils`;
- reverse DNS passa a ser enriquecimento não fatal;
- ausência de PTR, timeout ou falha de resolução não interrompe `DISCOVER`;
- upgrades preservam a configuração existente.

Erro que originou a correção:

```text
FileNotFoundError: [Errno 2] No such file or directory: 'dig'
```

# netbox-discovery 1.5.0 — PRODUCT V1

Consolida Evidence V4 + CLASSIFY + RECONCILE + PLAN + IMPORT 4.1 + AUDIT 5.1 e corrige a última inconsistência de identidade/contagem encontrada na homologação FBA.

Esta release substitui o fluxo de instalação por stages.

## Distribuição oficial

A versão 1.5.0 passa a ser distribuída pelo repositório público:

```text
bkpcloud-app/netbox-discovery
```

Foi validada instalação real em Proxy zerado, onde `git`, Python, Nmap e utilitários SNMP não estavam previamente disponíveis.

O fluxo oficial agora:

```text
GitHub público
→ install-from-github.sh
→ instala Git quando necessário
→ clone HTTPS
→ bootstrap
→ dependências
→ produto
→ init
```

O `bootstrap.sh` também foi ajustado para não apresentar `CONFIG: ERRO` como se fosse falha em uma instalação nova. Antes do `init`, a ausência de `config.yml` é comportamento esperado.

Para upgrade em um Proxy já configurado, o instalador preserva a configuração operacional existente. O scheduler é instalado, porém fica desabilitado até ação explícita.
