# Manual Operacional — netbox-discovery

**Produto:** netbox-discovery  
**Versão:** 1.10.1 — PRODUCT V1  
**Distribuição oficial:** `bkpcloud-app/netbox-discovery`  
**Canal de produção:** `stable`  
**NetBox BKPCLOUD:** `https://inventory.bkpcloud.app.br:8080`

> Este manual descreve o produto atual. O estado de homologação real fica separado em `docs/HOMOLOGACAO.md` para não confundir “código implementado/CI verde” com “validado ao vivo”.

---

## 1. Objetivo do produto

O `netbox-discovery` automatiza inventário de infraestrutura no NetBox com segurança operacional, dry-run por padrão e escrita somente quando explicitamente solicitada.

Existem dois pipelines independentes.

### 1.1 Rede

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

Comando read-only:

```bash
netbox-discovery run
```

Com escrita:

```bash
netbox-discovery run --apply
```

### 1.2 Hypervisor

```text
COLLECT
   ↓
RESOLVE TENANT/SITE
   ↓
PLAN
   ↓
IMPORT
   ↓
AUDIT
```

Comando read-only:

```bash
netbox-discovery hypervisor run
```

Com escrita:

```bash
netbox-discovery hypervisor run --apply
```

Os pipelines não são combinados em `full-run`.

---

## 2. Política de decisão e escrita

O PLAN classifica cada registro.

| Decisão | Significado | Escrita automática |
|---|---|---|
| `READY` | Evidência suficiente e sem conflito bloqueante | Sim, somente com `--apply` |
| `REVIEW` | Requer decisão/revisão humana | Não |
| `BLOCKED` | Conflito forte | Não |

Ações típicas:

| Ação | Significado |
|---|---|
| `CREATE` | Objeto não existe no contexto alvo |
| `UPDATE_SAFE` | Existe ajuste considerado seguro |
| `NOOP` | Já está coerente |

Regras importantes:

- dry-run é o padrão;
- `REVIEW` e `BLOCKED` nunca entram no lote de escrita;
- APPLY replaneja antes da primeira escrita;
- GETs podem receber retry seguro;
- POST/PATCH não recebem retry cego;
- o Hypervisor não executa DELETE automático;
- falha parcial de APPLY Hypervisor registra as escritas concluídas.

---

## 3. Endpoint NetBox

O produto aceita somente:

```text
https://inventory.bkpcloud.app.br:8080
```

`init` não pergunta a URL. Uma URL diferente no `config.yml` é rejeitada.

---

## 4. Instalação e atualização

### 4.1 Proxy novo

Como `root`:

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
curl -fsSL https://raw.githubusercontent.com/bkpcloud-app/netbox-discovery/stable/install-from-github.sh | bash
'
```

O instalador:

- instala dependências necessárias;
- valida o pacote antes de ativar;
- preserva configuração existente em upgrade;
- não inicia discovery automaticamente;
- não habilita scheduler Network/Hypervisor;
- instala o canal `stable`.

### 4.2 Atualização

```bash
netbox-discovery update status
netbox-discovery update check
netbox-discovery update run
```

O updater:

- usa `stable`;
- bloqueia downgrade;
- faz backup antes da troca;
- executa self-test antes/depois;
- preserva configuração;
- executa rollback em falha;
- coloca versão defeituosa em quarentena;
- compartilha lock global com Network/Hypervisor.

### 4.3 Auto-update

```bash
netbox-discovery update scheduler status
netbox-discovery update scheduler enable
netbox-discovery update scheduler disable
```

O auto-update stable é habilitado por padrão na instalação do produto.

---

## 5. Configuração principal — Tenant/Site base

Execute:

```bash
netbox-discovery init
```

O assistente configura, entre outros:

```text
Tenant Group [opcional]
Tenant
Site
Token NetBox
Redes CIDR
Exclusões
SNMP
Comunidades
Automação Network
```

A estrutura é genérica:

```text
Tenant Group [opcional]
└── Tenant
    └── Site
```

**Não existe regra hardcoded `MIZU → POLIMIX` ou equivalente.** O Tenant Group é explícito na configuração.

Após salvar, o produto garante de forma idempotente a estrutura base no NetBox:

- cria objetos ausentes;
- reutiliza os existentes;
- preenche vínculo vazio quando seguro;
- bloqueia vínculo conflitante em vez de sobrescrever silenciosamente.

Depois:

```bash
netbox-discovery check
```

---

## 6. Pipeline de Rede

### 6.1 Discovery

O discovery coleta evidências sem escrever inventário no NetBox.

Fontes podem incluir:

- Nmap/TCP/UDP;
- HTTP/TLS;
- SSH host key;
- SMB/RDP;
- SNMP System;
- ENTITY-MIB;
- interfaces/MAC/IP;
- LLDP/Bridge;
- probes específicos de equipamentos.

### 6.2 Classificação

O classificador tenta inferir:

- role;
- fabricante;
- modelo;
- plataforma;
- tipo de ativo;
- confiança.

A regra é conservadora: ausência de evidência suficiente não deve virar dado inventado.

### 6.3 Identidade

O produto pode correlacionar:

- serial;
- MAC de gerenciamento;
- IP;
- hostname;
- identidade SNMP;
- LLDP e outras evidências fortes.

Desde a linha 1.9, o `management_mac` pode ser derivado preferencialmente por:

```text
IP → SNMP ifIndex → MAC
```

MAC secundário/interface é evidência e não deve fundir Devices sozinho.

### 6.4 Execução

Dry-run:

```bash
netbox-discovery run
```

Após revisar o PLAN:

```bash
netbox-discovery run --apply
```

Para o estado de homologação de persistência de MAC em NetBox, consulte `docs/HOMOLOGACAO.md`.

---

## 7. Pipeline Hypervisor

Plataformas suportadas:

- VMware vCenter;
- VMware ESXi standalone;
- Proxmox VE;
- Microsoft Hyper-V via WinRM/NTLM.

Comandos:

```bash
netbox-discovery hypervisor configure
netbox-discovery hypervisor check
netbox-discovery hypervisor run
netbox-discovery hypervisor run --apply
netbox-discovery hypervisor status
```

Credenciais/sources ficam em:

```text
/etc/netbox-discovery/hypervisors.json
```

O arquivo deve permanecer `0600` e root-only quando executado como root.

---

## 8. Modos de inventário Hypervisor — 1.10+

Cada source possui `inventory_mode`.

### 8.1 `single_site`

```text
Todos os Hosts/VMs da source
→ Tenant/Site principal do config.yml
```

É o modo de compatibilidade das sources antigas.

### 8.2 `multi_site`

```text
Mesmo Tenant
├── Site A
├── Site B
└── Site C
```

O Tenant é o Tenant principal; cada rede de gerenciamento é mapeada para um Site.

### 8.3 `multi_tenant`

```text
Tenant Group
├── Tenant A
│   ├── Site 1
│   └── Site 2
└── Tenant B
    └── Site 3
```

Cada rede de gerenciamento pode apontar para Tenant Group, Tenant e Site diferentes.

---

## 9. Configurando uma source Hypervisor

Execute:

```bash
netbox-discovery hypervisor configure
```

O assistente pergunta a plataforma, endpoint, usuário, credencial e o modo:

```text
1 - SITE ÚNICO
2 - MULTI-SITE
3 - MULTI-TENANT / MULTI-SITE
```

### 9.1 Sources antigas

Sources criadas antes da 1.10 recebem em memória/configuração compatível:

```text
inventory_mode=single_site
mappings=[]
```

Elas **não mudam automaticamente para multi-contexto durante o update**.

Para ativar o novo comportamento, edite a source no `configure`.

### 9.2 Wizard multi-contexto

Nos modos `multi_site` ou `multi_tenant`, o wizard:

1. conecta no hypervisor;
2. coleta inventário de hosts;
3. identifica interfaces de gerenciamento quando disponíveis;
4. agrupa os hosts pelas redes CIDR observadas;
5. exibe hosts, Datacenters e Clusters como evidência;
6. solicita o mapeamento da rede;
7. opcionalmente cria/reutiliza a estrutura no NetBox;
8. salva os mappings na source.

Exemplo:

```text
Rede: 10.1.1.0/24
Hosts: ESX-DCM01, ESX-DCM02
Tenant Group: POLIMIX
Tenant: MIZU
Site: DCM

Rede: 10.2.1.0/24
Hosts: ESX-FBA01, ESX-FBA02
Tenant Group: POLIMIX
Tenant: MIZU
Site: FBA
```

O produto não deve adivinhar Tenant/Site pelo nome da VM.

---

## 10. Resolver Tenant/Site no runtime

No `hypervisor run` da linha 1.10:

### Host

```text
IP de gerenciamento do Host
→ mapping de rede mais específico
→ Tenant/Site alvo
```

Sem mapping confiável:

```text
REVIEW
Motivo: rede de gerenciamento do host sem mapeamento Tenant/Site
```

### VM

Primeira escolha:

```text
VM
→ host_name
→ contexto já resolvido do ESXi/Hypervisor Host
→ Tenant/Site
```

Fallback:

```text
IP da VM
→ mapping de rede
```

Sem resolução:

```text
REVIEW
```

A VM normalmente herda o Site do Host onde está executando. Isso permite que o IP do guest pertença a outra rede sem deslocar indevidamente a VM para outro Site.

---

## 11. Pipeline multi-contexto

Uma source central pode produzir vários contextos:

```text
vCenter
  ↓
MIZU/DCM
MIZU/FBA
PXMETAIS/MAC
...
```

O engine V3 divide o inventário por `Tenant/Site` e reaproveita o motor V2 de PLAN/APPLY/AUDIT em cada contexto.

Dry-run:

```bash
netbox-discovery hypervisor run
```

A saída mostra os contextos resolvidos e os objetos `REVIEW/BLOCKED/UPDATE_SAFE` com o alvo.

Exemplo conceitual:

```text
REVIEW | VM | VM01 | NOOP | alvo=PXMETAIS/MAC
Motivo: identidade já existe no NetBox fora do contexto alvo; requer reclassificação/migração
```

---

## 12. Proteção contra duplicação entre Sites/Tenants

Antes de permitir `CREATE` de Host/VM, a linha 1.10 possui uma guarda global de identidade forte.

Quando serial/UUID já existe em outro contexto:

```text
CREATE
→ cancelado
→ REVIEW
```

O produto não cria automaticamente uma segunda cópia para “corrigir” classificação de Site/Tenant.

Reclassificação/migração de objeto existente é uma operação distinta e **não é feita automaticamente na 1.10.1**.

Isso é particularmente importante quando uma versão anterior importou objetos no Site errado.

---

## 13. Provisionamento Tenant/Site pelo Hypervisor

No wizard multi-contexto existe a opção de criar/reutilizar automaticamente a estrutura correspondente ao mapping.

Ela pode executar escrita estrutural no NetBox durante o `configure`:

```text
Tenant Group
Tenant
Site
```

Isso **não importa Hosts/VMs**. A escrita de inventário continua exigindo:

```bash
netbox-discovery hypervisor run --apply
```

Conflitos de vínculo estrutural são bloqueados.

---

## 14. IPs de VM e redes internas

Discovery pode observar vários IPs do guest, inclusive bridges/container networks repetidas.

A política V2/V3 para IP autoritativo evita usar como identidade um IP secundário fora das redes relevantes do contexto. IP primário informado pela API pode permanecer elegível.

Isso evita falsos conflitos comuns como o mesmo IP de bridge Docker aparecendo em várias VMs.

---

## 15. Clusters, Hosts e VMs

O Hypervisor pode planejar/gerenciar:

- Cluster Types;
- Clusters;
- Devices físicos com role Hypervisor;
- Virtual Machines/containers;
- interfaces;
- MACs;
- IPs;
- Primary IP quando há evidência segura;
- associação VM ↔ Host;
- associação Host ↔ Cluster.

Nomes existentes no NetBox são preservados quando o motor encontra identidade forte suficiente para o objeto já existente.

Nenhuma ausência temporária em coleta gera DELETE automático.

---

## 16. Dependências VMware/Hyper-V

Dependências ficam isoladas em:

```text
/opt/netbox-discovery/vendor
```

Para VMware em ambientes Python 3.6, o conjunto homologado na linha 1.9 foi separado do Hyper-V para evitar dependência Rust/cryptography desnecessária.

O configurador instala dependências antes de carregar o collector da mesma execução.

Consulte `docs/HOMOLOGACAO.md` para o que já foi testado ao vivo.

---

## 17. Hypervisor check

```bash
netbox-discovery hypervisor check
```

Valida:

- NetBox;
- configuração Tenant/Site base;
- sources habilitadas;
- conexão/autenticação com o manager;
- versão/produto reportados quando disponível.

O check não escreve inventário.

---

## 18. Dry-run antes de APPLY

Regra operacional:

```text
configure
→ check
→ run
→ revisar
→ somente então --apply
```

Nunca tratar “CI passou” como autorização automática para APPLY em ambiente ainda não homologado.

Para a linha 1.10 multi-contexto, valide primeiro:

- número de contextos;
- Tenant/Site de cada contexto;
- redes mapeadas;
- quantidade de Hosts/VMs por contexto;
- `REVIEW`;
- `BLOCKED`;
- objetos que já existem fora do contexto alvo.

---

## 19. AUDIT e idempotência

Após APPLY, o audit verifica o estado no NetBox e replaneja.

Objetivo ideal:

```text
CREATE=0
UPDATE_SAFE=0
REVIEW=0
BLOCKED=0
NOOP=<todos os objetos coerentes>
```

Resultados residuais devem ser investigados. Não se deve repetir `--apply` cegamente esperando que “uma hora estabilize”.

---

## 20. Schedulers

Network:

```bash
netbox-discovery scheduler status
netbox-discovery scheduler enable
netbox-discovery scheduler disable
```

Hypervisor:

```bash
netbox-discovery hypervisor scheduler status
netbox-discovery hypervisor scheduler enable
netbox-discovery hypervisor scheduler disable
```

Os schedulers de inventário são opt-in.

Durante homologação, mantenha o Hypervisor scheduler desabilitado.

---

## 21. Saúde e monitoramento

```bash
netbox-discovery status
netbox-discovery self-test
netbox-discovery health
netbox-discovery health --json
```

`health --json` existe para integração com ferramentas como Zabbix.

---

## 22. Caminhos importantes

```text
/opt/netbox-discovery
/opt/netbox-discovery/config.yml
/opt/netbox-discovery/config/sites/
/opt/netbox-discovery/reports/
/opt/netbox-discovery/backups/
/opt/netbox-discovery/vendor/
/etc/netbox-discovery/hypervisors.json
/var/lock/netbox-discovery-global.lock
```

---

## 23. Credenciais e segurança de repositório

Nunca versionar:

- token NetBox;
- community SNMP real;
- senha VMware/Proxmox/Hyper-V;
- `hypervisors.json` real;
- `.env` de clientes;
- relatórios de cliente;
- backups de configuração;
- chaves privadas.

Consulte `SECURITY.md`.

---

## 24. Estado de homologação

A fonte oficial é:

```text
docs/HOMOLOGACAO.md
```

Categorias usadas:

```text
LIVE PASS     = testado ao vivo com resultado comprovado
LIVE PARTIAL  = parte do fluxo validada, ainda há pendência
CI PASS       = implementado e regressões automatizadas passaram
NOT LIVE      = ainda não foi homologado ao vivo
```

**1.10 multi-Tenant/multi-Site não deve ser chamado de homologado ao vivo até passar o teste real no DCM.**

---

## 25. Regra de documentação da release — 1.10.1+

Documentos obrigatórios:

```text
README.md
docs/MANUAL.md
docs/COMANDOS-RAPIDOS.md
docs/HOMOLOGACAO.md
RELEASE-NOTES.md
SECURITY.md
```

O `self-test` e o CI comparam a versão desses documentos com `VERSION`.

Uma release com documentação antiga deve falhar antes de entrar em `stable`.

---

## 26. Fluxo recomendado para o DCM após 1.10.1

Como já houve um import Hypervisor anterior em `MIZU/DCM`, não faça limpeza manual nem novo APPLY multi-contexto sem PLAN.

Sequência recomendada:

```text
1. atualizar para stable atual
2. confirmar self-test
3. editar uma source Hypervisor
4. escolher modo multi_tenant quando aplicável
5. revisar/provisionar mappings de rede → Tenant/Site
6. editar a segunda source
7. executar hypervisor check
8. executar hypervisor run SEM --apply
9. revisar toda a redistribuição proposta
10. somente então desenhar a migração dos objetos já existentes
```

A versão 1.10.1 **não move nem apaga automaticamente** os objetos importados anteriormente no Site errado.
