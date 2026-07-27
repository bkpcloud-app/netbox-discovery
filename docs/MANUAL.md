# Manual Operacional — netbox-discovery

**Produto:** netbox-discovery  
**Versão:** 1.10.7 — PRODUCT V1  
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
netbox-discovery hypervisor run --compare
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

## 3. Diagnóstico automático do dry-run — 1.10.5+

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

## 4. Preflight global multi-contexto — 1.10.6+

O `--apply` possui uma trava adicional antes da primeira escrita.

Depois de receber a autorização do operador, o produto ainda não escreve. Primeiro ele executa:

```text
===== HYPERVISOR PREFLIGHT GLOBAL MULTI-CONTEXT =====
```

O preflight:

1. reconstrói o PLAN usando o estado atual do NetBox;
2. aborta se surgir qualquer `REVIEW` ou `BLOCKED`;
3. exige que o conjunto de `RECLASSIFY_SAFE` seja o mesmo apresentado no dry-run;
4. confirma o mesmo `existing_id`, Tenant alvo e Site alvo;
5. usa o plano recém-recalculado como plano efetivo do APPLY.

Antes de uma reclassificação, o contexto recebe uma segunda validação:

```text
RECLASSIFY PREFLIGHT Tenant/Site: OK
```

Ela revalida imediatamente:

- serial/UUID;
- vínculo inequívoco de IP/MAC;
- `existing_id` esperado;
- Cluster/Prefix único quando aplicável;
- existência e unicidade do Tenant/Site alvo.

Se qualquer evidência mudar:

```text
PREFLIGHT ... nenhuma escrita iniciada
```

A ordem operacional é:

```text
DISCOVER
→ PLAN
→ autorização --apply
→ PREFLIGHT GLOBAL (sem escrita)
→ RECLASSIFY PREFLIGHT por contexto (sem escrita)
→ RECLASSIFY_SAFE / CREATE / UPDATE_SAFE
→ AUDIT
```

---

## 5. Migração coordenada de Cluster/Site — 1.10.7

### Problema

No NetBox, um Device que é host de Cluster só pode permanecer associado ao Cluster quando ambos estão coerentes com o mesmo Site, caso o Cluster possua `scope` de Site.

Durante o primeiro APPLY multi-contexto real em 27/07/2026, o contexto `MIZU/FBA` chegou com:

```text
Cluster FBA → scope DCM
Hosts FBA   → Site DCM
Alvo        → MIZU/FBA
```

A 1.10.6 tentava reclassificar o Cluster antes dos Hosts e o NetBox bloqueou corretamente:

```text
HTTP 400
2 devices are assigned as hosts for this cluster but are not in site FBA
```

Nenhum contexto posterior a FBA foi escrito naquela execução.

### Sequência segura 1.10.7

Como o `scope` do Cluster é opcional, a migração coordenada passa a usar:

```text
1. RECLASSIFY PREFLIGHT
2. validar todos os Devices-host do Cluster
3. remover temporariamente o scope do Cluster
4. mover os Devices-host para o Site alvo
5. reaplicar Tenant + scope do Cluster no Site alvo
6. continuar com VMs e reconciliação normal
```

Saída esperada:

```text
RECLASSIFY PREFLIGHT MIZU/FBA: OK
CLUSTER SCOPE RELEASE FBA: OK | NetBox write: SIM
...
```

### Travas

Antes de soltar o scope do Cluster:

- o Cluster precisa continuar sendo correspondência global única;
- cada Device-host fora do Site alvo precisa possuir `HOST / RECLASSIFY_SAFE` no mesmo contexto;
- Device-host com rack/location não é migrado automaticamente;
- identidade forte dos Hosts continua sendo revalidada;
- se a composição do Cluster mudar, o processo aborta antes da migração daquele contexto.

### Recuperação após falha parcial

O produto mantém journal das escritas. Não existe rollback cego de objetos já gravados.

Depois de uma falha:

1. não repetir `--apply` cegamente;
2. executar comparação read-only;
3. rodar novo dry-run;
4. somente continuar depois de revisar o estado real do NetBox.

---

## 6. Comparação NetBox × Hypervisor — 1.10.7

Comando oficial:

```bash
netbox-discovery hypervisor run --compare
```

Esse modo é somente leitura.

Ele:

1. coleta novamente as sources Hypervisor;
2. resolve Tenant/Site pelos mappings atuais;
3. lê Devices, VMs, Clusters e Prefixes do NetBox;
4. compara o contexto atual contra o contexto esperado;
5. lista apenas as divergências e entrega resumo completo.

Estados:

```text
OK
MISMATCH
MISSING
AMBIGUOUS
```

Exemplo:

```text
MISMATCH | HOST | 10.2.1.21 | atual=MIZU/DCM | esperado=MIZU/FBA
```

Para VMs:

- se a VM estiver em Cluster, o Site efetivo vem do `scope` do Cluster;
- se estiver ligada diretamente a Device, o Site efetivo vem do Device;
- Tenant da VM é comparado diretamente.

Proteções:

- não usa POST/PATCH;
- usa lock global e não roda durante APPLY/Update;
- gera `MULTI-hypervisor-compare-*.json`;
- termina com `NetBox write: NÃO`.

---

## 7. Endpoint NetBox

O produto aceita somente:

```text
https://inventory.bkpcloud.app.br:8080
```

---

## 8. Hypervisor

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

## 9. VMware: rede de gerenciamento autoritativa

Para Tenant/Site, não basta o VMware marcar uma interface como serviço `management`.

Seleção conservadora:

1. IP de vmkernel que corresponde ao FQDN/nome do ESXi;
2. `vmk0` marcada como management;
3. única rede management candidata;
4. múltiplas candidatas sem evidência forte → `REVIEW`.

Interfaces auxiliares continuam no inventário, mas não posicionam o Host.

---

## 10. Resolver Tenant/Site

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

## 11. Reclassificação segura — 1.10.4+

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

## 12. Delta de inventário — 1.10.4+

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

## 13. APPLY

Dry-run:

```bash
netbox-discovery hypervisor run
```

Comparação read-only:

```bash
netbox-discovery hypervisor run --compare
```

Escrita:

```bash
netbox-discovery hypervisor run --apply
```

Regras:

- somente `READY` escreve;
- antes da primeira escrita, o PLAN é reconstruído no preflight global;
- `REVIEW` não escreve;
- `BLOCKED` não escreve;
- `RECLASSIFY_SAFE` exige revalidação de identidade imediatamente antes do PATCH;
- migração de Cluster/Site usa bridge coordenada quando necessário;
- APPLY mantém journal das escritas;
- AUDIT é executado depois da escrita;
- não existe DELETE automático no Hypervisor.

---

## 14. Atualização

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

## 15. Schedulers

Network e Hypervisor são opt-in.

```bash
netbox-discovery scheduler status
netbox-discovery hypervisor scheduler status
netbox-discovery update scheduler status
```

Durante homologação de uma função de escrita nova, manter Hypervisor scheduler/APPLY automático desabilitado.

---

## 16. Saúde

```bash
netbox-discovery version
netbox-discovery status
netbox-discovery self-test
netbox-discovery health
netbox-discovery health --json
```

---

## 17. Caminhos

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

## 18. Homologação

A matriz oficial é:

```text
docs/HOMOLOGACAO.md
```

`CI PASS` não significa `LIVE PASS`.
