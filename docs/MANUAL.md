# Manual Operacional — netbox-discovery

**Produto:** netbox-discovery  
**Versão:** 1.10.5 — PRODUCT V1  
**Distribuição oficial:** `bkpcloud-app/netbox-discovery`  
**Canal de produção:** `stable`  
**NetBox BKPCLOUD:** `https://inventory.bkpcloud.app.br:8080`

> O estado de homologação real fica em `docs/HOMOLOGACAO.md`. CI verde não equivale a validação ao vivo.

---

## 1. Visão geral

O `netbox-discovery` automatiza inventário de infraestrutura no NetBox com dry-run por padrão e escrita somente quando explicitamente solicitada.

### Rede

```text
netbox-discovery run
DISCOVER → CLASSIFY → RECONCILE → PLAN
```

Escrita:

```text
netbox-discovery run --apply
DISCOVER → CLASSIFY → RECONCILE → PLAN → IMPORT → AUDIT
```

### Hypervisor

```text
netbox-discovery hypervisor configure
netbox-discovery hypervisor check
netbox-discovery hypervisor run
netbox-discovery hypervisor run --apply
netbox-discovery hypervisor status
```

---

## 2. Decisões e ações do PLAN

| Decisão | Significado | Escrita |
|---|---|---|
| `READY` | Evidência suficiente | somente com `--apply` |
| `REVIEW` | Requer revisão humana | não |
| `BLOCKED` | Conflito forte | não |

Ações:

| Ação | Significado |
|---|---|
| `CREATE` | objeto novo |
| `UPDATE_SAFE` | ajuste seguro |
| `RECLASSIFY_SAFE` | mesmo objeto em Tenant/Site incorreto, identidade forte inequívoca |
| `NOOP` | nenhuma escrita necessária |

---

## 3. Diagnóstico automático do dry-run — 1.10.5

O operador não deve usar scripts auxiliares para descobrir o conteúdo do PLAN.

O próprio comando:

```bash
netbox-discovery hypervisor run
```

mostra automaticamente:

### Novos objetos

```text
===== HYPERVISOR NOVOS OBJETOS READY =====
[1/N] READY | PREFIX/HOST/VM/CLUSTER | nome | CREATE | alvo=Tenant/Site
NOVOS OBJETOS READY: N
```

### Ajustes e migrações

```text
===== HYPERVISOR AJUSTES/MIGRAÇÕES SEGURAS PENDENTES =====
READY | ... | UPDATE_SAFE
READY | ... | RECLASSIFY_SAFE
```

### Conflitos

```text
===== HYPERVISOR PENDÊNCIAS DO PLAN =====
REVIEW
BLOCKED
```

### Resumo

```text
===== RESUMO DE ESCRITA DO DRY-RUN =====
CREATE READY: N
UPDATE_SAFE/RECLASSIFY_SAFE READY: N
REVIEW/BLOCKED: N
NetBox write: NÃO
```

Portanto:

- a análise é automática;
- o terminal já mostra tudo que precisa ser revisado;
- JSON continua disponível para auditoria, mas não é necessário para operação normal;
- nenhum Python ad-hoc é parte do procedimento operacional.

A única autorização manual obrigatória é a escrita:

```bash
netbox-discovery hypervisor run --apply
```

---

## 4. Endpoint NetBox

O produto aceita somente:

```text
https://inventory.bkpcloud.app.br:8080
```

---

## 5. Hypervisor

Plataformas:

- VMware vCenter;
- VMware ESXi standalone;
- Proxmox VE;
- Microsoft Hyper-V via WinRM/NTLM.

Credenciais:

```text
/etc/netbox-discovery/hypervisors.json
```

Permissão esperada: `0600`.

### Modos de inventário

```text
single_site
multi_site
multi_tenant
```

---

## 6. VMware: rede de gerenciamento autoritativa

Para Tenant/Site, não basta o VMware marcar uma interface como serviço `management`.

Seleção conservadora:

1. IP de vmkernel que corresponde ao FQDN/nome do ESXi;
2. `vmk0` marcada como management;
3. única rede management candidata;
4. múltiplas candidatas sem evidência forte → `REVIEW`.

Interfaces auxiliares continuam no inventário, mas não posicionam o Host.

---

## 7. Resolver Tenant/Site

### Host

```text
rede de gerenciamento autoritativa
→ mapping
→ Tenant/Site
```

### VM

```text
VM
→ Host onde está executando
→ Tenant/Site do Host
```

IP da VM é fallback. Sem evidência confiável, a VM fica `REVIEW`.

A localização no NetBox representa onde a VM está hospedada. Uma VM pode atender outro Site sem mudar seu Site físico de inventário.

---

## 8. Reclassificação segura — 1.10.4+

Problema resolvido:

```text
objeto já existe no NetBox
+ está no Tenant/Site antigo
+ identidade forte confirma que é o mesmo objeto
→ READY / RECLASSIFY_SAFE
```

Evidências fortes:

- serial/UUID único;
- IP vinculado inequivocamente;
- MAC vinculado inequivocamente;
- combinação coerente.

Nunca migrar automaticamente quando:

- serial/UUID é ambíguo;
- IP/MAC possui mais de um dono;
- serial e IP/MAC apontam para objetos diferentes;
- a única evidência é o nome.

Nesses casos:

```text
REVIEW
```

Quando seguro:

- Host: Tenant/Site podem ser corrigidos;
- VM: Tenant pode ser corrigido;
- IPs vinculados podem acompanhar o Tenant;
- Cluster/Prefix somente com correspondência global única e segura;
- o mesmo ID é preservado;
- não existe DELETE automático.

---

## 9. Delta de inventário — 1.10.4+

O discovery compara a coleta atual com o snapshot anterior.

VM ausente:

```text
HYPERVISOR INVENTORY CHANGE
REMOVED/REVIEW
REVIEW / NOOP
DELETE automático: NÃO
```

Uma ausência nunca autoriza exclusão automática.

---

## 10. APPLY

Dry-run:

```bash
netbox-discovery hypervisor run
```

Escrita:

```bash
netbox-discovery hypervisor run --apply
```

Regras:

- somente `READY` escreve;
- `REVIEW` não escreve;
- `BLOCKED` não escreve;
- APPLY mantém journal das escritas;
- AUDIT é executado depois da escrita;
- não existe DELETE automático no Hypervisor.

---

## 11. Atualização

```bash
netbox-discovery update status
netbox-discovery update check
netbox-discovery update run
```

Updater `stable`:

- faz backup;
- valida candidato;
- preserva configuração;
- executa rollback em falha;
- bloqueia downgrade;
- usa quarentena para versão quebrada.

---

## 12. Schedulers

Network e Hypervisor são opt-in.

```bash
netbox-discovery scheduler status
netbox-discovery hypervisor scheduler status
netbox-discovery update scheduler status
```

Durante homologação de uma função de escrita nova, manter Hypervisor scheduler/APPLY automático desabilitado.

---

## 13. Saúde

```bash
netbox-discovery version
netbox-discovery status
netbox-discovery self-test
netbox-discovery health
netbox-discovery health --json
```

---

## 14. Caminhos

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

## 15. Homologação

A matriz oficial é:

```text
docs/HOMOLOGACAO.md
```

`CI PASS` não significa `LIVE PASS`.
