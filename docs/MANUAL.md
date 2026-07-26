# Manual Operacional — netbox-discovery

**Produto:** netbox-discovery
**Versão:** 1.8.0 — PRODUCT V1
**Objetivo:** descobrir ativos de rede, identificar/classificar, reconciliar identidades, planejar alterações, importar com segurança no NetBox e auditar o resultado.
**Distribuição oficial:** repositório público `bkpcloud-app/netbox-discovery` via HTTPS.

---

## 1. O que o produto faz

O `netbox-discovery` automatiza o ciclo de inventário de rede para NetBox:

```text
DISCOVER
   ↓
CLASSIFY
   ↓
RECONCILE
   ↓
PLAN
   ↓
IMPORT
   ↓
AUDIT
```

### DISCOVER

Localiza hosts ativos e coleta evidências sem gravar no NetBox.

A versão V1 utiliza múltiplas fontes, entre elas:

- descoberta TCP/UDP;
- Nmap e fingerprint de serviços;
- HTTP/TLS;
- SSH host key;
- SMB/RDP;
- protocolos de descoberta industrial;
- SNMP System;
- ENTITY-MIB;
- interfaces/MAC/IP via SNMP;
- LLDP/Bridge;
- deep scan residual somente em hosts com pouca evidência.

O resultado é salvo em JSON/CSV para as etapas seguintes.

### CLASSIFY

Transforma as evidências em uma classificação do ativo.

Exemplos de informações que podem ser inferidas:

- função/role;
- fabricante;
- modelo;
- plataforma;
- tipo de equipamento;
- nível de confiança.

O classificador não deve inventar informação quando a evidência não é suficiente.

### RECONCILE

Resolve o problema:

> IP não é necessariamente um equipamento.

Exemplos:

```text
3 IPs do mesmo FortiGate
→ 1 Device

2 IPs do mesmo NAS
→ 1 Device

ESXi + interface de gerenciamento/iDRAC
→ identidade física reconciliada
```

A reconciliação utiliza evidências como serial, MAC, hostname, identidade SNMP e outras informações disponíveis.

### PLAN

Compara o inventário descoberto com o NetBox atual.

Cada asset recebe uma decisão:

| Decisão | Significado |
|---|---|
| `READY` | Pode participar da escrita automática |
| `REVIEW` | Requer revisão; não é importado automaticamente |
| `BLOCKED` | Existe conflito; nunca é importado automaticamente |

Também define a ação:

| Ação | Significado |
|---|---|
| `CREATE` | Device ainda não existe |
| `UPDATE_SAFE` | Existem alterações consideradas seguras |
| `NOOP` | Já está coerente; nenhuma alteração necessária |
| `CONFLICT` | Há conflito de identidade/IP |

Regras importantes do PLAN:

- baixa confiança vira `REVIEW`;
- role desconhecida vira `REVIEW`;
- conflito de identidade/IP vira `BLOCKED`;
- IPs são consultados na tabela global do NetBox;
- um IP já associado a outro objeto não é criado novamente.

### IMPORT

A escrita é explicitamente protegida.

Somente registros `READY` são importados.

```text
READY   → pode escrever
REVIEW  → ignora
BLOCKED → ignora
NOOP    → não altera
```

O importador:

- recalcula o PLAN antes da escrita;
- faz preflight global de IP;
- evita criar IP duplicado;
- preserva inventário existente quando não há evidência segura para substituir;
- foi projetado para reexecução idempotente;
- pode retomar após uma execução parcial sem duplicar o que já foi criado.

### AUDIT

Após um import, confere o resultado diretamente no NetBox em modo somente leitura.

Verifica, entre outros:

- Device;
- Tenant;
- Site;
- serial;
- role;
- plataforma;
- fabricante/modelo;
- interfaces;
- IPs;
- Primary IPv4;
- OOB;
- conflitos/duplicidades;
- idempotência.

Resultados possíveis:

```text
PASS
PASS_WITH_WARNINGS
FAIL
```

`PASS_WITH_WARNINGS` com `Checks FAIL: 0` significa que não foi detectada falha crítica, mas existem diferenças preservadas ou situações que merecem revisão humana.

---

## 2. Segurança do produto

O comportamento padrão é **read-only**.

### Sem escrita

```bash
netbox-discovery run
```

Executa:

```text
DISCOVER → CLASSIFY → RECONCILE → PLAN
```

Não grava no NetBox.

### Com escrita

```bash
netbox-discovery run --apply
```

Executa:

```text
DISCOVER → CLASSIFY → RECONCILE → PLAN → IMPORT → AUDIT
```

Apenas `READY` é elegível para import automático.

### Regras de segurança consolidadas

- escrita exige `--apply` em execução manual;
- `REVIEW` não é importado automaticamente;
- `BLOCKED` nunca é importado;
- import faz novo PLAN antes de escrever;
- preflight consulta IPs globalmente;
- reexecução é idempotente;
- AUDIT é read-only;
- `init` e `configure` nunca iniciam discovery;
- instalador nunca habilita o scheduler sozinho;
- inventário preexistente não vazio é preservado quando há dúvida.

---

## 3. Pipeline Hypervisor — V1.8.0

O módulo de virtualização pertence ao mesmo executável, mas é operacionalmente independente do discovery de rede.

```bash
netbox-discovery hypervisor configure
netbox-discovery hypervisor check
netbox-discovery hypervisor run
netbox-discovery hypervisor run --apply
netbox-discovery hypervisor status
```

Plataformas suportadas:

- VMware vCenter e ESXi standalone via vSphere API/pyVmomi;
- Proxmox VE via API REST, com API Token preferencial;
- Microsoft Hyper-V via WinRM/NTLM.

### Escopo

Por padrão uma source central (por exemplo um vCenter atendendo várias filiais) é filtrada pelas redes CIDR configuradas para o Site. Um host entra quando seu IP de gerenciamento pertence ao Site; uma VM entra quando está em host incluído ou possui IP pertencente às redes do Site. `scope_mode=all` pode ser escolhido explicitamente no configure.

### Objetos

O PLAN Hypervisor contempla:

- Prefixes das redes explicitamente configuradas para o Site;
- Cluster Types e Clusters;
- Devices físicos com role `HYPERVISOR`;
- Virtual Machines e containers;
- interfaces físicas/virtuais;
- MACAddress;
- IPAddress;
- Primary IP quando a origem fornece indicação segura.

Portgroups/bridges/switches virtuais são evidência de relacionamento; o produto não inventa Prefixes a partir somente do nome de uma rede virtual.

### Preservação e reconciliação

O produto identifica objetos existentes por serial/UUID, IP e outros vínculos fortes. O `name` já existente no NetBox não é atualizado automaticamente. Isso permite, por exemplo, renomear manualmente um Device ou VM no NetBox sem o scheduler desfazer a alteração. O mesmo princípio preserva interfaces já vinculadas ao mesmo IP/MAC.

VMs em cluster podem ter a associação ao host físico atualizada quando uma migração é comprovada pela API.

Nenhuma rotina Hypervisor executa DELETE. Ausência temporária em uma coleta não remove objeto do NetBox.

### Credenciais

As sources ficam em:

```text
/etc/netbox-discovery/hypervisors.json
```

O arquivo é exigido com modo `0600` e, quando executado como root, proprietário root. Segredos não entram em relatórios. Dependências VMware/Hyper-V são instaladas juntas e isoladas em `/opt/netbox-discovery/vendor` no primeiro uso de um desses conectores; Proxmox não exige pacote Python adicional.

### Schedulers separados

```bash
netbox-discovery hypervisor scheduler enable
netbox-discovery scheduler enable
```

Não existe `full-run`. A recomendação é agendar Hypervisor primeiro e Network depois, com horários independentes.

---

## 4. Requisitos

Para instalação por GitHub público, o Proxy precisa inicialmente de:

```text
root
acesso HTTPS à Internet/GitHub
curl (o comando oficial instala se estiver ausente)
dnf, yum ou apt-get
```

O instalador oficial cuida das dependências do produto:

```text
git
Python 3.6 ou superior
nmap
snmpget
snmpwalk
```

O scheduler utiliza systemd quando habilitado.

O caminho padrão da aplicação é:

```text
/opt/netbox-discovery
```

O comando global é:

```text
/usr/local/bin/netbox-discovery
```

---

## 5. Instalação em um Proxy novo

A distribuição oficial é feita pelo repositório público:

```text
https://github.com/bkpcloud-app/netbox-discovery
```

Não é necessário copiar ZIP, cadastrar Deploy Key ou autenticar o Proxy no GitHub.

### Instalação recomendada — Proxy zerado

Execute como `root`:

```bash
bash -lc '
set -euo pipefail
if ! command -v curl >/dev/null 2>&1; then
    if command -v dnf >/dev/null 2>&1; then dnf install -y curl ca-certificates
    elif command -v yum >/dev/null 2>&1; then yum install -y curl ca-certificates
    elif command -v apt-get >/dev/null 2>&1; then apt-get update && apt-get install -y curl ca-certificates
    else echo "ERRO: não encontrei dnf, yum ou apt-get"; exit 1
    fi
fi
curl -fsSL https://raw.githubusercontent.com/bkpcloud-app/netbox-discovery/main/install-from-github.sh | bash
'
```

O `install-from-github.sh`:

- instala `git` caso esteja ausente;
- clona `bkpcloud-app/netbox-discovery` por HTTPS;
- executa o `bootstrap.sh`;
- instala as dependências de discovery/SNMP;
- chama o instalador do produto;
- preserva configuração de instalação anterior;
- não inicia discovery;
- não habilita scheduler.

Em um Proxy novo, a saída esperada termina semelhante a:

```text
NETBOX-DISCOVERY PRODUCT V1 INSTALADO
Versão: 1.8.0
CONFIG: ainda não criada (comportamento esperado).
PRÓXIMO PASSO: netbox-discovery init
```

A ausência de `/opt/netbox-discovery/config.yml` imediatamente após uma instalação nova **não é falha**. A configuração é criada pelo `init`.

Em instalação nova, o próximo comando é:

```bash
netbox-discovery init
```

---

## 6. Configuração inicial de um novo cliente/site

Execute:

```bash
netbox-discovery init
```

O assistente solicita:

```text
Cliente/Tenant
Site
NetBox fixo BKPCLOUD (somente exibição)
Token do NetBox
Validação SSL
Redes CIDR
Exclusões
SNMP
Comunidades SNMP
Automação
Agenda
Import automático
```

No final ele mostra um resumo e pergunta se deve salvar.

**O `init` nunca inicia uma varredura.**

Depois:

```bash
netbox-discovery check
```

Resultado esperado:

```text
CONFIG: OK
TENANT: ...
SITE: ...
NETBOX URL: https://inventory.bkpcloud.app.br:8080
DISCOVER: OK
CLASSIFY: OK
RECONCILE: OK
PLAN: OK
IMPORT: OK
AUDIT: OK
```

---

## 7. Alterar uma configuração

Use:

```bash
netbox-discovery configure
```

O mesmo assistente apresenta os valores atuais e permite preservá-los ou alterá-los.

Também não inicia discovery.

---

## 8. Primeira execução em um site novo

### Passo 1 — modo seguro

```bash
netbox-discovery run
```

Essa execução vai até o PLAN e não escreve no NetBox.

No final, observe principalmente:

```text
READY
REVIEW
BLOCKED
CREATE
UPDATE_SAFE
NOOP
```

### Passo 2 — escrita real

Quando o PLAN estiver aceitável:

```bash
netbox-discovery run --apply
```

O produto executará o pipeline completo e fará AUDIT automaticamente.

### Passo 3 — conferir o resultado

```bash
netbox-discovery status
```

---

## 9. Comandos principais

### Ajuda

```bash
netbox-discovery help
```

### Versão

```bash
netbox-discovery version
```

### Validar instalação/configuração

```bash
netbox-discovery check
```

### Somente Discovery

```bash
netbox-discovery discover
```

### Somente Classify

```bash
netbox-discovery classify
```

### Somente Reconcile

```bash
netbox-discovery reconcile
```

### Somente Plan

```bash
netbox-discovery plan
```

### Classify + Reconcile + Plan

```bash
netbox-discovery inventory
```

### Import

Dry-run/comportamento sem escrita:

```bash
netbox-discovery import
```

Escrita real:

```bash
netbox-discovery import --apply
```

### Audit

```bash
netbox-discovery audit
```

### Pipeline completo sem escrita

```bash
netbox-discovery run
```

### Pipeline completo com escrita

```bash
netbox-discovery run --apply
```

### Status

```bash
netbox-discovery status
```

---

## 10. Entendendo o `status`

Exemplo:

```text
===== NETBOX-DISCOVERY STATUS =====
Versão: 1.8.0
Tenant/Site: CLIENTE/SITE
Último RUN: PASS_WITH_WARNINGS
DISCOVER: 288 hosts
RECONCILE: 283 assets
PLAN: READY=152 REVIEW=129 BLOCKED=2
      CREATE=120 UPDATE_SAFE=2 NOOP=161
IMPORT: mode=APPLY processados=152 blocked=0 erros=0
AUDIT: PASS_WITH_WARNINGS | PASS=15 WARN=137 FAIL=0
       checks FAIL=0
```

Interpretação:

- `Último RUN`: resultado do último pipeline unificado;
- `DISCOVER`: hosts encontrados na última descoberta;
- `RECONCILE`: quantidade de equipamentos/assets após deduplicação;
- `READY`: elegíveis para automação;
- `REVIEW`: pendentes de revisão;
- `BLOCKED`: conflito;
- `CREATE`: seriam criados;
- `UPDATE_SAFE`: atualizações seguras;
- `NOOP`: nenhuma alteração necessária;
- `IMPORT erros=0`: importação concluiu sem erro;
- `AUDIT FAIL=0`: nenhum asset falhou na auditoria;
- `checks FAIL=0`: nenhuma checagem crítica falhou.

---

## 11. Scheduler / execução automática

O produto usa:

```text
systemd service + timer
```

Arquivos:

```text
/etc/systemd/system/netbox-discovery.service
/etc/systemd/system/netbox-discovery.timer
```

O instalador deixa o timer **desabilitado**.

### 10.1 Configurar automação

Execute:

```bash
netbox-discovery configure
```

Responda, por exemplo:

```text
Habilitar execução automática? SIM
Agenda systemd OnCalendar: daily
Permitir IMPORT automático? NÃO
```

### 10.2 Habilitar o scheduler

```bash
netbox-discovery scheduler enable
```

### 10.3 Verificar

```bash
netbox-discovery scheduler status
```

### 10.4 Desabilitar

```bash
netbox-discovery scheduler disable
```

---

## 12. Automação segura x automação com escrita

Existem **dois controles diferentes**:

1. timer systemd habilitado;
2. configuração `automation.enabled/apply`.

O timer sozinho não autoriza escrita.

### Recomendado inicialmente

```yaml
automation:
  enabled: true
  apply: false
  schedule: daily
```

Resultado:

```text
scheduler dispara
→ DISCOVER
→ CLASSIFY
→ RECONCILE
→ PLAN
→ sem IMPORT
```

### Escrita automática

```yaml
automation:
  enabled: true
  apply: true
  schedule: daily
```

Resultado:

```text
scheduler dispara
→ DISCOVER
→ CLASSIFY
→ RECONCILE
→ PLAN
→ IMPORT READY
→ AUDIT
```

A configuração deve preferencialmente ser alterada por:

```bash
netbox-discovery configure
```

---

## 13. Exemplos de agenda

O campo utiliza sintaxe `OnCalendar` do systemd.

Diariamente:

```text
daily
```

Todos os dias às 02:00:

```text
*-*-* 02:00:00
```

Segunda a sexta às 01:30:

```text
Mon..Fri *-*-* 01:30:00
```

Depois de alterar a agenda pelo `configure`, reaplique o scheduler:

```bash
netbox-discovery scheduler enable
```

---

## 14. Execução sem depender da sessão SSH

Uma execução manual:

```bash
netbox-discovery run
```

ou:

```bash
netbox-discovery run --apply
```

é executada em foreground.

Para operação contínua de produto, prefira o **scheduler systemd**, pois ele não depende do tablet, terminal ou sessão SSH permanecer conectada.

O timer possui `Persistent=true`, portanto o systemd pode executar uma ocorrência perdida após o host voltar, conforme o comportamento do timer.

---

## 15. Arquivos e diretórios importantes

Raiz:

```text
/opt/netbox-discovery
```

Configuração principal:

```text
/opt/netbox-discovery/config.yml
```

Configuração por site:

```text
/opt/netbox-discovery/config/sites/<SITE>/
```

Arquivos por site:

```text
networks.conf
exclusions.conf
snmp-communities.conf
```

Relatórios:

```text
/opt/netbox-discovery/reports
```

Logs:

```text
/opt/netbox-discovery/logs
```

Cache:

```text
/opt/netbox-discovery/cache
```

Backups:

```text
/opt/netbox-discovery/backups
```

---

## 16. Relatórios gerados

Para um site chamado `SITE`, são gerados arquivos como:

```text
SITE-discovery-*.json
SITE-discovery-*.csv

SITE-classification-*.json
SITE-classification-*.csv

SITE-reconciliation-*.json
SITE-reconciliation-*.csv

SITE-plan-*.json
SITE-plan-*.csv

SITE-import-*.json
SITE-import-*.csv

SITE-audit-*.json
SITE-audit-*.csv

SITE-run-*.json
```

O JSON contém os dados completos.

O CSV é voltado para leitura/consulta operacional.

O `status` lê os relatórios mais recentes.

---

## 17. Backup e upgrade

A atualização oficial utiliza o mesmo instalador do GitHub público:

```bash
curl -fsSL https://raw.githubusercontent.com/bkpcloud-app/netbox-discovery/main/install-from-github.sh | bash
```

O processo baixa a versão atual do repositório e executa novamente o instalador.

Durante instalação/upgrade, o produto cria automaticamente um backup semelhante a:

```text
/opt/netbox-discovery/backups/pre-product-v1-AAAAmmdd-HHMMSS
```

A configuração operacional existente é preservada. O pacote do produto não contém `config.yml` ativo e não deve sobrescrever credenciais/configuração do cliente.

Também permanecem fora do Git público:

```text
tokens
communities SNMP reais
relatórios
logs
cache
backups de clientes
chaves privadas
```

Para instalar uma release fixa em vez de `main`, use a variável `NETBOX_DISCOVERY_REF`. Exemplo:

```bash
NETBOX_DISCOVERY_REF=v1.8.0 bash -c "$(curl -fsSL https://raw.githubusercontent.com/bkpcloud-app/netbox-discovery/main/install-from-github.sh)"
```

---

## 18. Concorrência

O `run` utiliza lock:

```text
/var/lock/netbox-discovery-run.lock
```

Se outra execução do pipeline já estiver rodando, uma nova execução é recusada.

Isso evita dois pipelines completos concorrentes escrevendo ou coletando ao mesmo tempo.

---

## 19. O que fazer quando der erro

### Primeiro

```bash
netbox-discovery status
```

### Validar produto

```bash
netbox-discovery check
```

### Ver scheduler

```bash
netbox-discovery scheduler status
```

### Regra operacional

Não apague objetos do NetBox manualmente apenas porque uma execução falhou.

O importador foi projetado para:

- replanejar;
- detectar objetos já criados;
- reutilizar o que estiver correto;
- não duplicar IP;
- retomar de forma idempotente.

Quando um `run --apply` falhar, investigue a causa antes de apagar qualquer objeto.

---

## 20. Quando NÃO usar `--apply`

Não use escrita automática quando:

- o site está sendo implantado pela primeira vez e o PLAN ainda não foi revisado;
- existe número inesperadamente alto de `BLOCKED`;
- existem conflitos de IP/identidade;
- o Tenant/Site configurado está incorreto;
- o NetBox apontado não é o ambiente esperado;
- a coleta foi feita em redes incorretas.

Use:

```bash
netbox-discovery run
```

primeiro.

---

## 21. Processo recomendado para novo cliente/site

Fluxo operacional padrão:

```text
1. Instalar PRODUCT V1
2. netbox-discovery init
3. netbox-discovery check
4. netbox-discovery run
5. Conferir PLAN/status
6. netbox-discovery run --apply
7. netbox-discovery status
8. Configurar automação
9. netbox-discovery scheduler enable
```

Depois disso, a operação normal deve ser automática.

---

## 22. Configuração não interativa

A V1 também possui configuração não interativa, útil para automação de implantação.

Exemplo:

```bash
netbox-discovery init \
  --non-interactive \
  --tenant CLIENTE \
  --site SITE \
  --netbox-url https://netbox.exemplo.local \
  --netbox-token TOKEN \
  --network 10.10.1.0/24 \
  --network 10.10.2.0/24 \
  --exclude 10.10.1.1 \
  --community COMMUNITY \
  --automation \
  --no-auto-apply \
  --schedule daily
```

Também existem:

```text
--verify-ssl
--no-verify-ssl
--automation
--no-automation
--auto-apply
--no-auto-apply
--skip-test
```

**Atenção:** passar token diretamente na linha de comando pode deixá-lo exposto no histórico/process list. Para operação manual, prefira o assistente interativo. Para implantação em massa, use um mecanismo seguro de gerenciamento/injeção de secrets.

---

## 23. Configuração ativa por Proxy

A configuração principal possui um único:

```text
tenant
site
```

ativo por vez.

As redes/comunidades ficam organizadas em:

```text
config/sites/<SITE>/
```

Na arquitetura atual, a forma mais simples e segura é tratar cada Proxy/site como uma instalação/configuração operacional própria.

---

## 24. Significado das principais situações

### `READY`

A evidência e o estado do NetBox permitem automação.

### `REVIEW`

Não é erro.

Significa:

> existe informação útil, mas não há segurança suficiente para escrever automaticamente.

### `BLOCKED`

Existe conflito objetivo.

Exemplos:

- identidade apontando para dois devices;
- IP associado a objeto incompatível;
- nome ambíguo em situação de conflito.

O produto não escreve.

### `WARN` no AUDIT

Diferença não crítica ou inventário existente preservado.

### `FAIL` no AUDIT

Falha que impede considerar o resultado homologado.

---

## 25. Política operacional recomendada

### Durante implantação de um site novo

```text
automation.enabled = false
automation.apply = false
```

Faça primeiro:

```bash
netbox-discovery run
```

Depois da validação:

```bash
netbox-discovery run --apply
```

### Depois da homologação

Primeiro automatize sem escrita:

```text
automation.enabled = true
automation.apply = false
```

Depois, quando houver confiança operacional suficiente, pode-se liberar:

```text
automation.apply = true
```

---

## 26. Comandos de bolso

```bash
# ajuda
netbox-discovery help

# versão
netbox-discovery version

# configurar novo site
netbox-discovery init

# alterar configuração
netbox-discovery configure

# validar produto
netbox-discovery check

# simulação completa / sem escrita
netbox-discovery run

# ciclo completo / escrita real
netbox-discovery run --apply

# estado atual
netbox-discovery status

# habilitar automático
netbox-discovery scheduler enable

# ver scheduler
netbox-discovery scheduler status

# desligar automático
netbox-discovery scheduler disable
```

---

## 27. Regra de ouro

Para um cliente/site novo:

```text
NÃO editar inventário na mão para “ajudar” o discovery.
NÃO começar com --apply.
NÃO importar REVIEW.
NÃO forçar BLOCKED.
```

Use o produto:

```text
init
→ check
→ run
→ analisar PLAN
→ run --apply
→ audit/status
→ scheduler
```

---

## 28. Referência da versão 1.5.2

A V1 consolidou as correções homologadas durante o piloto:

- descoberta multi-método;
- classificação por evidência;
- reconciliação de múltiplos IPs;
- proteção contra colisões de asset IDs;
- PLAN conservador;
- preflight global de IP;
- prevenção de POST de IP duplicado;
- retomada idempotente;
- preservação de inventário preexistente;
- auditoria pós-import;
- correção do Primary IPv4 preexistente como `WARN/PRESERVED`;
- execução única `run`;
- execução completa `run --apply`;
- lock contra concorrência;
- status consolidado;
- assistente `init/configure`;
- scheduler systemd.

---

# Resumo final

### Novo site

```text
INSTALAR DO GITHUB
→ INIT
→ CHECK
→ RUN
→ REVISAR PLAN
→ RUN --APPLY
→ STATUS
→ SCHEDULER
```

```bash
netbox-discovery init
netbox-discovery check
netbox-discovery run
# revisar PLAN antes da escrita
netbox-discovery run --apply
netbox-discovery status
```

### Operação recorrente

```bash
netbox-discovery scheduler enable
netbox-discovery scheduler status
```

### Segurança

```text
Sem --apply = sem escrita.
REVIEW = não importa.
BLOCKED = não importa.
AUDIT = somente leitura.
```

---

**Documento referente ao netbox-discovery PRODUCT V1 — versão 1.8.0.**
