# Manual Operacional — netbox-discovery

**Produto:** netbox-discovery  
**Versão:** 1.10.3 — PRODUCT V1  
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

Ações:

| Ação | Significado |
|---|---|
| `CREATE` | Objeto não existe no contexto alvo |
| `UPDATE_SAFE` | Ajuste considerado seguro |
| `NOOP` | Já está coerente |

Regras principais:

- dry-run é o padrão;
- APPLY replaneja antes da primeira escrita;
- `REVIEW` e `BLOCKED` não escrevem;
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

Instalação:

```bash
curl -fsSL https://raw.githubusercontent.com/bkpcloud-app/netbox-discovery/stable/install-from-github.sh | bash
```

Atualização:

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

Desde a 1.10.1, a documentação obrigatória também é validada no self-test/CI.

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

### `multi_site`

Um mesmo Tenant pode ter vários Sites.

### `multi_tenant`

Uma source pode atender vários Tenants e vários Sites.

```text
Tenant Group
├── Tenant A
│   ├── Site 1
│   └── Site 2
└── Tenant B
    └── Site 3
```

Sources antigas permanecem em `single_site` até edição explícita.

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

Em source existente, ENTER preserva os valores apresentados como default. A senha também pode ser preservada.

---

## 10. VMware: rede de gerenciamento autoritativa — 1.10.3

### Problema encontrado no DCM

Durante homologação real, 4 Hosts ESXi do Datacenter `DCM` apresentaram 11 redes com o serviço VMware `management` habilitado:

```text
10.1.1.0/24
192.168.140.0/24
192.168.141.0/24
192.168.142.0/24
192.168.143.0/24
192.168.160.0/24
192.168.161.0/24
192.168.180.0/24
192.168.181.0/24
192.168.190.0/24
192.168.191.0/24
```

A rede de gestão conhecida dos Hosts é `10.1.1.0/24`. Portanto, usar todas as interfaces `management=True` como mappings Tenant/Site era incorreto.

### Regra 1.10.3

O produto passa a separar:

```text
vmkernel com serviço management
            ≠
rede autoritativa para posicionar o Host no Site
```

Para VMware, a seleção é conservadora:

1. prefere o vmkernel cujo IP corresponde à resolução do FQDN/nome do ESXi;
2. se não houver essa evidência, prefere `vmk0` quando ela está marcada como management;
3. se restar uma única rede management candidata, usa essa rede;
4. se houver múltiplas candidatas sem evidência forte, não adivinha e o Host fica sem contexto resolvido.

As interfaces auxiliares continuam disponíveis no inventário. Elas apenas deixam de decidir Tenant/Site.

### Wizard

O wizard usa apenas redes autoritativas para criar grupos de posicionamento e mappings.

Exemplo esperado para o DCM:

```text
Datacenter: DCM
Hosts: vm-ae01, vm-ae02, vm-ae03, vm-ae04
Rede autoritativa: 10.1.1.0/24
Tenant Group: POLIMIX
Tenant: MIZU
Site: DCM
```

Se a seleção for ambígua, a configuração não deve inventar um mapping.

---

## 11. Resolver Tenant/Site no runtime

### Host

```text
rede de gerenciamento autoritativa
→ mapping mais específico
→ Tenant/Site alvo
```

Sem mapping confiável:

```text
REVIEW
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

A saída mostra contextos, `READY`, `REVIEW`, `BLOCKED`, `UPDATE_SAFE` e alvo Tenant/Site.

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

O produto não cria automaticamente uma segunda cópia para corrigir Site/Tenant.

Reclassificação/migração de objetos já existentes é uma operação distinta e não é automática na 1.10.3.

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

## 17. Homologação

A matriz oficial é:

```text
docs/HOMOLOGACAO.md
```

`CI PASS` não significa `LIVE PASS`.

Não habilitar APPLY automático para funcionalidade ainda marcada como `NOT LIVE`.
