# Procedimento — Monitoramento Dell PowerVault no Zabbix

> Rascunho inicial criado para documentar a implantação de monitoramento das storages Dell PowerVault ME e MD3200 no ambiente BKPCLOUD.

## Escopo

Este documento cobre:

- Dell PowerVault ME4024 via API HTTPS;
- Dell PowerVault MD3200 via Dell MDSM/SMcli;
- execução das coletas pelo Proxy Zabbix `SNOC-AGL-DCM`;
- uso de cache local para evitar timeout nas coletas da MD3200;
- instalação, validação, troubleshooting e operação.

## Ambiente usado

- Proxy Zabbix: `SNOC-AGL-DCM`;
- Sistema operacional: CentOS Stream 8;
- MD3200 Controller A: `10.1.1.56`;
- MD3200 Controller B: `10.1.1.57`;
- ME4024 Controller A: `10.1.1.52`;
- ME4024 Controller B: `10.1.1.53`;
- Template ME: `ZBX-DELL-STG-POWERVAULT-ME-API`;
- Template MD3200: `ZBX-DELL-STG-POWERVAULT-MD3200`.

---

# 1. Dell PowerVault ME4024

## 1.1 Método de coleta

A ME4024 foi monitorada pela API HTTPS das duas controladoras.

A coleta usa usuário de leitura e consulta inventário, saúde e desempenho.

### Macros do template

```text
{$POWERVAULT.IP.A}
{$POWERVAULT.IP.B}
{$POWERVAULT.API.USER}
{$POWERVAULT.API.PASSWORD}
```

### Endereços usados

```text
Controller A: 10.1.1.52
Controller B: 10.1.1.53
```

## 1.2 Dados úteis monitorados

- saúde geral da storage;
- controladoras;
- portas e SFPs;
- discos;
- pools;
- disk groups;
- volumes;
- estatísticas de controladoras;
- estatísticas de disk groups;
- estatísticas de volumes;
- contadores selecionados de erro de disco;
- ICMP das duas controladoras.

## 1.3 Cuidados do template

- evitar triggers agressivas;
- evitar alertas por flutuação momentânea;
- não criar item `SSD life remaining` para discos HDD;
- tratar respostas `N/A` da API;
- manter inventário, saúde e desempenho separados;
- usar o mesmo padrão de nomes e descrições do ambiente BKPCLOUD.

## 1.4 Erros encontrados

### `SSD life remaining` em HDD

A descoberta criava o item em discos HDD. A API retornava `N/A`, deixando o item não suportado.

Correção:

- criar o item somente para discos identificados como SSD;
- não criar trigger de vida útil para HDD;
- proteger o pré-processamento contra `N/A`.

### Inventário sem parâmetro de senha

Erro observado:

```text
Cannot execute script: Required parameter is not set: password.
```

O item mestre de inventário deve usar a mesma macro de senha dos demais coletores:

```text
{$POWERVAULT.API.PASSWORD}
```

---

# 2. Dell PowerVault MD3200

## 2.1 Método de coleta

A MD3200 não utiliza a mesma API da linha ME. A coleta foi implementada com Dell MDSM/SMcli.

### Controladoras

```text
Controller A: 10.1.1.56
Controller B: 10.1.1.57
```

### Porta de gerenciamento validada

```text
TCP 2463
```

## 2.2 Instalação do Dell MDSM/SMcli

Foi utilizada a mídia:

```text
DELL_MDSS_Consolidated_RDVD_6_5_0_1.iso
```

SHA-256 validado:

```text
4b1309a9c59c264bca360cb45560ef45dfbbb9532fed078ce3875184bc7299ec
```

### Download controlado

O download foi limitado para evitar impacto no Proxy:

```bash
ISO="/root/DELL_MDSS_Consolidated_RDVD_6_5_0_1.iso"
URL="https://downloads.dell.com/FOLDER04066625M/1/DELL_MDSS_Consolidated_RDVD_6_5_0_1.iso"
LOG="/root/download-mdsm.log"

nohup nice -n 19 ionice -c 3 \
curl -4 --http1.1 -fL \
  --continue-at - \
  --limit-rate 1M \
  --retry 10 \
  --retry-delay 15 \
  --connect-timeout 30 \
  -o "$ISO" \
  "$URL" \
  >"$LOG" 2>&1 &
```

### Validação do arquivo

```bash
echo "4b1309a9c59c264bca360cb45560ef45dfbbb9532fed078ce3875184bc7299ec  /root/DELL_MDSS_Consolidated_RDVD_6_5_0_1.iso" | sha256sum -c -
```

### Montagem da ISO

```bash
mkdir -p /mnt/dell-mdsm
mount -o loop,ro,exec /root/DELL_MDSS_Consolidated_RDVD_6_5_0_1.iso /mnt/dell-mdsm
```

### Instalação somente do cliente

A instalação foi limitada ao `SMclient`, sem Host Agent, RDAC, failover ou multipath.

Arquivo de propriedades:

```bash
cat > /root/mdsm-smclient-only.properties <<'EOF'
INSTALLER_UI=SILENT
CHOSEN_INSTALL_SET=Custom
CHOSEN_INSTALL_FEATURE_LIST=SMclient
USER_REQUESTED_RESTART=NO
EOF
```

Instalação:

```bash
cd /mnt/dell-mdsm/linux/mdsm

./SMIA-LINUXX64.bin \
  -i silent \
  -f /root/mdsm-smclient-only.properties
```

## 2.3 Permissões para o usuário Zabbix

O SMcli precisa gravar arquivos em `/var/opt/SM`. Sem isso, a consulta pode retornar saúde correta, mas encerrar com código 27.

Exemplo observado:

```text
storage_health = optimal
return_code = 27
```

Foi necessário liberar acesso ao usuário `zabbix` por ACL.

```bash
dnf install -y acl
install -d -o zabbix -g zabbix -m 0750 /var/lib/zabbix

setfacl -m u:zabbix:--x /var /var/opt

find /var/opt/SM -type d \
  -exec setfacl -m u:zabbix:rwx,m::rwx,d:u:zabbix:rwx,d:m::rwx {} +

find /var/opt/SM -type f ! -name 'LAUNCHER_ENV' \
  -exec setfacl -m u:zabbix:rw- {} +

setfacl -m u:zabbix:r-- /var/opt/SM/LAUNCHER_ENV
```

## 2.4 Teste direto do SMcli

```bash
runuser -u zabbix -- \
  env HOME=/var/lib/zabbix \
  /usr/bin/SMcli \
  10.1.1.56 10.1.1.57 \
  -S \
  -c "show storageArray healthStatus;"
```

Resultado esperado:

```text
Storage array health status = optimal.
```

## 2.5 Coletas usadas no levantamento

### Saúde

```bash
SMcli 10.1.1.56 10.1.1.57 -S -c "show storageArray healthStatus;"
```

### Perfil completo

```bash
SMcli 10.1.1.56 10.1.1.57 -S -c "show storageArray profile;"
```

### Performance dos volumes

```bash
SMcli 10.1.1.56 10.1.1.57 -S -c "show allVirtualDisks performanceStats;"
```

### Outras consultas úteis

```text
show storageArray summary;
show storageArray batteryAge;
show storageArray hotSpareCoverage;
show storageArray longRunningOperations;
show storageArray unreadableSectors;
show storageArray virtualDiskDistribution;
show storageArray connections;
show storageArray time;
show allVirtualDisks summary;
show allPhysicalDisks summary;
show allPhysicalDiskChannels stats;
```

## 2.6 Resultado do levantamento

O ambiente retornou:

```text
Storage: optimal
Discos: 24
Volumes: 2
Baterias: 2
Canais físicos: 2
```

## 2.7 Problema de timeout no Zabbix

A execução direta do coletor demorava aproximadamente 14 segundos.

Quando os itens mestres de saúde, inventário e performance eram disparados juntos pelo Zabbix, o SMcli concorria consigo mesmo e os processos ultrapassavam o timeout do Proxy.

Apenas aumentar o `Timeout` não resolve corretamente esse desenho.

## 2.8 Solução adotada: cache local

Arquitetura final:

```text
SMcli executa fora do Zabbix
        ↓
systemd executa as coletas serialmente
        ↓
JSON é gravado em cache local
        ↓
Zabbix lê o JSON em milissegundos
```

### Diretório do cache

```text
/var/lib/zabbix/md3200-cache/
```

### Arquivos gerados

```text
health.json
performance.json
inventory.json
```

### Serviço e timer

```text
dell-md3200-cache.service
dell-md3200-cache.timer
```

O timer executa a cada minuto e o script respeita os intervalos internos configurados:

```text
HEALTH_INTERVAL=120
PERFORMANCE_INTERVAL=300
INVENTORY_INTERVAL=1800
```

### Status do timer

```bash
systemctl status dell-md3200-cache.timer
systemctl list-timers --all | grep dell-md3200-cache
```

### Execução manual

```bash
systemctl start dell-md3200-cache.service
journalctl -u dell-md3200-cache.service --no-pager -n 100
```

## 2.9 Bug corrigido no atualizador de cache

Erro observado:

```text
linha 19: out: variável não associada
```

Causa:

Uma variável local era utilizada na mesma declaração antes de receber valor, com `set -u` ativo.

Forma incorreta:

```bash
local out="$out_dir/$mode.json" tmp="$out.tmp.$$"
```

Forma correta:

```bash
local out tmp age now
out="$out_dir/$mode.json"
tmp="$out.tmp.$$"
age=999999
```

## 2.10 Validação final do cache

Resultado validado:

```text
available = 1
return_code = 0
storage_health = optimal
cache_stale = 0
errors =
```

Arquivos confirmados:

```text
/var/lib/zabbix/md3200-cache/10.1.1.56__10.1.1.57/health.json
/var/lib/zabbix/md3200-cache/10.1.1.56__10.1.1.57/performance.json
/var/lib/zabbix/md3200-cache/10.1.1.56__10.1.1.57/inventory.json
```

## 2.11 Configuração do host no Zabbix

Template:

```text
ZBX-DELL-STG-POWERVAULT-MD3200
```

Proxy:

```text
SNOC-AGL-DCM
```

Macros:

```text
{$MD3200.IP.A} = 10.1.1.56
{$MD3200.IP.B} = 10.1.1.57
{$MD3200.SMCLI} = /usr/bin/SMcli
```

## 2.12 Timeout do Proxy

Durante a implantação foi usado:

```text
Timeout=30
```

Arquivo:

```text
/etc/zabbix/zabbix_proxy.conf
```

Depois da adoção do cache, o Zabbix não depende mais de uma execução longa do SMcli em cada item.

---

# 3. Operação e troubleshooting

## Verificar o Proxy

```bash
systemctl --no-pager --full status zabbix-proxy
grep -E '^[[:space:]]*Timeout=' /etc/zabbix/zabbix_proxy.conf
```

## Verificar o coletor

```bash
ls -lh /usr/lib/zabbix/externalscripts/dell_md3200.py
ls -lh /usr/lib/zabbix/externalscripts/dell_md3200_cache.py
```

## Verificar o cache

```bash
find /var/lib/zabbix/md3200-cache \
  -maxdepth 3 \
  -type f \
  -printf '%M %u:%g %s bytes %p\n'
```

## Testar leitura do cache como Zabbix

```bash
runuser -u zabbix -- \
  /usr/lib/zabbix/externalscripts/dell_md3200_cache.py \
  health \
  10.1.1.56 \
  10.1.1.57 \
  300
```

## Ver logs do serviço

```bash
journalctl -u dell-md3200-cache.service \
  --since "30 minutes ago" \
  --no-pager \
  -n 200
```

## Verificar cache desatualizado

O retorno deve mostrar:

```text
cache_stale = 0
```

Quando aparecer `cache_stale = 1`, verificar:

1. estado do timer;
2. estado do serviço;
3. comunicação TCP 2463;
4. permissões em `/var/opt/SM`;
5. execução manual do SMcli;
6. logs do systemd.

---

# 4. Diretrizes operacionais

- não executar vários comandos SMcli simultaneamente;
- manter as coletas serializadas;
- não instalar Host Agent, RDAC ou multipath no Proxy apenas para monitoramento;
- não gerar alerta por uma única amostra de latência alta;
- usar persistência nas triggers;
- separar saúde, inventário e performance;
- tratar erros históricos como informação, não incidente imediato;
- documentar qualquer alteração de firmware, IP ou credencial;
- não armazenar senhas reais no GitHub;
- usar macros secretas no Zabbix para credenciais.

---

# 5. Arquivos principais do projeto

```text
ZBX-DELL-STG-POWERVAULT-ME-API.yaml
ZBX-DELL-STG-POWERVAULT-MD3200-v1.1.0.yaml
dell_md3200.py
dell_md3200_cache.py
dell-md3200-cache-update.sh
dell-md3200-cache.service
dell-md3200-cache.timer
install-md3200-cache.sh
```

## Observação

Este documento registra o procedimento validado no ambiente BKPCLOUD. Antes de reutilizar em outro ambiente, revisar:

- endereços IP;
- caminho do SMcli;
- versão do Zabbix;
- distribuição Linux;
- permissões;
- SELinux;
- intervalos e thresholds.
