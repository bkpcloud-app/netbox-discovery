# Manual Operacional — netbox-discovery

**Produto:** netbox-discovery  
**Versão:** 1.10.2 — PRODUCT V1  
**Distribuição oficial:** `bkpcloud-app/netbox-discovery`  
**Canal de produção:** `stable`  
**NetBox BKPCLOUD:** `https://inventory.bkpcloud.app.br:8080`

> Este manual descreve o produto atual. O estado de homologação real fica separado em `docs/HOMOLOGACAO.md` para não confundir “implementado/CI verde” com “validado ao vivo”.

---

## 1. Visão geral

O `netbox-discovery` automatiza inventário de infraestrutura no NetBox com dry-run por padrão e escrita somente quando explicitamente solicitada.

Existem dois pipelines independentes.

### Rede

```text
DISCOVER → CLASSIFY → RECONCILE → PLAN → IMPORT → AUDIT
```

Dry-run:

```bash
netbox-discovery run
```

Escrita:

```bash
netbox-discovery run --apply
```

### Hypervisor

```text
COLLECT → RESOLVE TENANT/SITE → PLAN → IMPORT → AUDIT
```

Dry-run:

```bash
netbox-discovery hypervisor run
```

Escrita:

```bash
netbox-discovery hypervisor run --apply
```

Não existe `full-run`.

---

## 2. Decisões do PLAN

| Decisão | Significado | Escrita |
|---|---|---|
| `READY` | Evidência suficiente e sem conflito bloqueante | somente com `--apply` |
| `REVIEW` | Requer revisão humana | não |
| `BLOCKED` | Conflito forte | não |

Ações típicas:

| Ação | Significado |
|---|---|
| `CREATE` | Objeto não existe no contexto alvo |
| `UPDATE_SAFE` | Ajuste considerado seguro |
| `NOOP` | Já está coerente |

Regras:

- dry-run é o padrão;
- APPLY replaneja antes da primeira escrita;
- `REVIEW` e `BLOCKED` não entram no lote de escrita;
- GETs podem receber retry seguro;
- POST/PATCH não recebem retry cego;
- Hypervisor não executa DELETE automático;
- falha parcial de APPLY Hypervisor mantém journal das escritas realizadas.

---

## 3. Endpoint NetBox

O produto aceita somente:

```text
https://inventory.bkpcloud.app.br:8080
```

Uma URL diferente no `config.yml` é rejeitada.

---

## 4. Instalação e atualização

### Proxy novo

```bash
curl -fsSL https://raw.githubusercontent.com/bkpcloud-app/netbox-discovery/stable/install-from-github.sh | bash
```

O instalador:

- valida o pacote antes de ativar;
- preserva configuração existente;
- não inicia discovery automaticamente;
- não habilita schedulers Network/Hypervisor;
- instala o canal `stable`.

### Atualização

```bash
netbox-discovery update status
netbox-discovery update check
netbox-discovery update run
```

O updater:

- usa `stable`;
- bloqueia downgrade;
- faz backup;
- executa self-test antes/depois;
- preserva configuração;
- executa rollback em falha;
- usa quarentena para versão quebrada;
- compartilha lock global com Network/Hypervisor.

Desde a 1.10.1, documentação obrigatória também é validada no self-test/CI.

---

## 5. Configuração base

```bash
netbox-discovery init
netbox-discovery check
```

Estrutura:

```text
Tenant Group [opcional]
└── Tenant
    └── Site
```

O produto é genérico. **Não existe hardcode `MIZU → POLIMIX` ou equivalente.**

O `init` cria/reutiliza a estrutura base de forma idempotente e bloqueia vínculos conflitantes.

---

## 6. Pipeline de Rede

O discovery pode usar Nmap, TCP/UDP, HTTP/TLS, SSH, SMB/RDP, SNMP, ENTITY-MIB, interfaces/MAC/IP, LLDP e probes específicos.

A identidade pode considerar serial, MAC de gerenciamento, IP, hostname, SNMP e LLDP.

Desde a linha 1.9, `management_mac` pode ser derivado preferencialmente por:

```text
IP → SNMP ifIndex → MAC
```

MAC secundário é evidência, não identidade forte isolada.

Execução:

```bash
netbox-discovery run
# revisar PLAN
netbox-discovery run --apply
```

O estado de homologação da persistência MAC está em `docs/HOMOLOGACAO.md`.

---

## 7. Pipeline Hypervisor

Plataformas:

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

Credenciais/sources:

```text
/etc/netbox-discovery/hypervisors.json
```

O arquivo deve permanecer `0600` e root-only quando executado como root.

---

## 8. Modos de inventário Hypervisor

Cada source possui `inventory_mode`.

### `single_site`

Todos os Hosts/VMs pertencem ao Tenant/Site principal desta instalação.

Sources antigas permanecem nesse modo até edição explícita.

### `multi_site`

Um mesmo Tenant pode ter vários Sites.

### `multi_tenant`

Uma source pode atender vários Tenants e vários Sites.

Exemplo:

```text
Tenant Group
├── Tenant A
│   ├── Site 1
│   └── Site 2
└── Tenant B
    └── Site 3
```

---

## 9. Configurando uma source Hypervisor

```bash
netbox-discovery hypervisor configure
```

O assistente pergunta:

```text
1 - SITE ÚNICO
2 - MULTI-SITE
3 - MULTI-TENANT / MULTI-SITE
```

Em source existente, ENTER preserva plataforma/endpoint/ID/usuário quando exibidos como default; a senha também pode ser preservada.

---

## 10. Wizard multi-contexto VMware — 1.10.2

### Por que mudou

Durante a primeira homologação real do modo `multi_tenant` no DCM, um vCenter com apenas 4 Hosts retornou **11 redes VMware com serviço `management`**.

Isso é possível porque um ESXi pode possuir vários vmkernel com o serviço VMware `management` habilitado. Portanto:

> uma rede vmkernel marcada como management não deve ser tratada automaticamente como um Site distinto.

A 1.10.1 perguntaria Tenant/Site para cada CIDR. A configuração foi interrompida antes de salvar o novo mapping.

### Comportamento 1.10.2

O wizard agora:

1. conecta no hypervisor;
2. coleta Hosts, Datacenter, Cluster e interfaces vmkernel;
3. identifica as redes com serviço VMware `management`;
4. verifica a relação de cada rede com VMware Datacenter;
5. quando várias redes pertencem inequivocamente ao mesmo Datacenter, cria um **grupo de posicionamento**;
6. mostra Hosts, Clusters e todos os CIDRs do grupo;
7. pergunta se um único Tenant/Site atende aquele Datacenter;
8. se sim, solicita Tenant/Site uma vez e grava mappings equivalentes para todos os CIDRs;
9. se não, abre o grupo para revisão por rede;
10. rede sem Datacenter único ou compartilhada entre Datacenters permanece individual;
11. mappings existentes divergentes não são consolidados silenciosamente.

Exemplo:

```text
Datacenter: DCM
Hosts: vm-ae01.mizu.local, vm-ae02.mizu.local, vm-ae03.mizu.local, vm-ae04.mizu.local
Cluster(s): Cluster
Redes VMware com serviço management (11): 10.1.1.0/24, ...

Usar um único Tenant/Site para todas estas redes deste Datacenter? [S/n]: S
Tenant Group (opcional) [POLIMIX]:
Tenant [MIZU]:
Site [DCM]:
```

Os defaults `MIZU/DCM` nesse exemplo não são hardcode. Eles podem ser sugeridos apenas quando o nome do Datacenter coincide com o Site base atual configurado nessa instalação.

### Escrita estrutural durante o wizard

Quando o usuário aceita:

```text
Criar/reutilizar automaticamente Tenant/Site no NetBox para os mapeamentos? [S/n]
```

o wizard pode criar/reutilizar Tenant Group/Tenant/Site. Isso é **escrita estrutural**, não IMPORT de Hosts/VMs.

Nenhum Host/VM é importado pelo `configure`.

---

## 11. Resolver Tenant/Site no runtime

### Host

```text
IPs do Host
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
→ contexto já resolvido do Host
→ Tenant/Site
```

Fallback:

```text
IP da VM
→ mapping de rede
```

A VM normalmente herda o Site do Host onde está executando.

---

## 12. Pipeline multi-contexto

Uma source central pode produzir:

```text
vCenter
  ↓
MIZU/DCM
MIZU/FBA
PXMETAIS/MAC
...
```

O engine V3 divide o inventário por Tenant/Site e reaproveita PLAN/APPLY/AUDIT V2 em cada contexto.

Dry-run:

```bash
netbox-discovery hypervisor run
```

A saída mostra contextos, `READY`, `REVIEW`, `BLOCKED`, `UPDATE_SAFE` e o alvo Tenant/Site.

---

## 13. Proteção contra duplicação entre contextos

Antes de CREATE de Host/VM, existe guarda global de identidade forte.

Se serial/UUID já existe fora do contexto alvo:

```text
CREATE
→ cancelado
→ REVIEW
→ requer reclassificação/migração
```

O produto não cria automaticamente uma segunda cópia para “corrigir” Site/Tenant.

Reclassificação/migração de objetos já existentes é operação distinta e não é automática na 1.10.2.

---

## 14. Schedulers

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

Update:

```bash
netbox-discovery update scheduler status
netbox-discovery update scheduler enable
netbox-discovery update scheduler disable
```

Network/Hypervisor são opt-in. Auto-update stable é habilitado por padrão.

---

## 15. Operação e saúde

```bash
netbox-discovery version
netbox-discovery status
netbox-discovery self-test
netbox-discovery health
netbox-discovery health --json
```

`health --json` é adequado para integração com Zabbix e outras ferramentas.

---

## 16. Caminhos

```text
Aplicação:              /opt/netbox-discovery
Configuração principal: /opt/netbox-discovery/config.yml
Config Hypervisor:      /etc/netbox-discovery/hypervisors.json
Dependências isoladas:  /opt/netbox-discovery/vendor
Config por Site:        /opt/netbox-discovery/config/sites/
Relatórios:             /opt/netbox-discovery/reports
Backups:                /opt/netbox-discovery/backups
Lock global:            /var/lock/netbox-discovery-global.lock
```

---

## 17. Regra de homologação

`CI PASS` não significa `LIVE PASS`.

Consulte:

```text
docs/HOMOLOGACAO.md
```

Uma funcionalidade só deve ser chamada de homologada ao vivo depois de execução real registrada.

---

## 18. Procedimento atual no DCM

```text
1. atualizar para 1.10.2
2. editar a primeira source VMware
3. escolher multi_tenant
4. revisar o grupo de Datacenter detectado
5. confirmar se o grupo realmente representa um Site
6. confirmar Tenant Group / Tenant / Site
7. salvar a source
8. repetir na segunda source
9. hypervisor check
10. hypervisor run SEM --apply
11. revisar redistribuição dos objetos já existentes
12. somente após plano seguro considerar APPLY
```

Não habilitar scheduler Hypervisor com APPLY enquanto o multi-contexto ainda não estiver LIVE PASS.
