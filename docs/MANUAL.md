# Manual Operacional — netbox-discovery

**Produto:** netbox-discovery  
**Versão:** 1.10.8 — PRODUCT V1  
**Distribuição oficial:** `bkpcloud-app/netbox-discovery`  
**Canal de produção:** `stable`  
**NetBox BKPCLOUD:** `https://inventory.bkpcloud.app.br:8080`

> O estado de homologação real fica em `docs/HOMOLOGACAO.md`. CI verde não equivale a validação ao vivo.

---

## 1. Visão geral

O `netbox-discovery` automatiza descoberta, reconciliação, planejamento, importação segura e auditoria de inventário no NetBox.

### Rede

```text
netbox-discovery run
DISCOVER → CLASSIFY → RECONCILE → PLAN
```

Com escrita:

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

Conectores suportados:

- VMware vCenter/ESXi;
- Proxmox VE;
- Hyper-V via WinRM/NTLM.

Modos:

```text
single_site
multi_site
multi_tenant
```

---

## 2. Decisões e ações

| Decisão | Significado | Escrita |
|---|---|---|
| `READY` | evidência suficiente | somente com `--apply` |
| `REVIEW` | precisa revisão | não |
| `BLOCKED` | conflito forte | não |

| Ação | Significado |
|---|---|
| `CREATE` | objeto novo |
| `UPDATE_SAFE` | ajuste seguro |
| `RECLASSIFY_SAFE` | mesmo objeto em Tenant/Site incorreto, identidade forte |
| `NOOP` | nenhuma mudança necessária |

---

## 3. Dry-run e diagnóstico

```bash
netbox-discovery hypervisor run
```

O próprio produto lista:

```text
HYPERVISOR NOVOS OBJETOS READY
HYPERVISOR AJUSTES/MIGRAÇÕES SEGURAS PENDENTES
HYPERVISOR PENDÊNCIAS DO PLAN
RESUMO DE ESCRITA DO DRY-RUN
```

Resumo esperado:

```text
CREATE READY: N
UPDATE_SAFE/RECLASSIFY_SAFE READY: N
REVIEW/BLOCKED: N
NetBox write: NÃO
```

Não faz parte da operação normal abrir JSON com Python auxiliar para descobrir ações do PLAN.

---

## 4. Preflight global — 1.10.6+

Mesmo depois de receber `--apply`, o produto ainda executa um preflight read-only antes da primeira escrita.

```text
DISCOVER
→ PLAN
→ autorização --apply
→ PREFLIGHT GLOBAL
→ RECLASSIFY PREFLIGHT por contexto
→ escrita READY
→ AUDIT
```

O preflight global:

1. reconstrói o PLAN contra o estado atual do NetBox;
2. aborta se surgir `REVIEW` ou `BLOCKED`;
3. exige que o conjunto `RECLASSIFY_SAFE` não tenha mudado;
4. confirma `existing_id`, Tenant e Site alvo;
5. usa o plano recém-calculado para o APPLY.

Saída:

```text
===== HYPERVISOR PREFLIGHT GLOBAL MULTI-CONTEXT =====
PREFLIGHT GLOBAL: OK
REVIEW/BLOCKED: 0
NetBox write até aqui: NÃO
```

---

## 5. Reclassificação segura

`RECLASSIFY_SAFE` só é permitido com identidade forte:

- serial/UUID único;
- IP inequivocamente vinculado;
- MAC inequivocamente vinculado;
- combinação coerente dessas evidências.

Nome sozinho nunca autoriza migração.

Se serial, IP e MAC apontarem para objetos diferentes ou houver ambiguidade, a decisão vira `REVIEW`.

---

## 6. Migração coordenada de Cluster/Site — 1.10.7

O NetBox exige coerência entre o Site de um Cluster scoped e o Site de seus Devices-host.

A migração segura usa:

```text
RECLASSIFY PREFLIGHT
→ validar todos os Devices-host do Cluster
→ remover temporariamente o scope do Cluster
→ mover Devices-host para o Site alvo
→ reaplicar Tenant/scope do Cluster no Site alvo
→ continuar VMs
```

Travas:

- todo host membro fora do Site alvo precisa ter `HOST / RECLASSIFY_SAFE` no mesmo contexto;
- host com rack/location não muda automaticamente de Site;
- Cluster precisa continuar único;
- mudança inesperada de composição bloqueia o contexto;
- não há DELETE automático.

Essa regra é genérica e vale para qualquer Tenant/Site/Cluster.

---

## 7. VM acompanha o Site autoritativo do Host/Cluster — 1.10.8

Uma VM herda o Tenant/Site do Host onde está executando. Quando uma VM existente precisa ser reclassificada, `tenant` e `site` precisam mudar juntos.

Fluxo seguro:

```text
revalida identidade forte da VM
→ relê Device/Cluster atual no NetBox
→ confirma que o parent já está no Site alvo
→ VM PARENT PREFLIGHT: OK
→ PATCH tenant + site no mesmo request
→ ajusta Tenant dos IPs vinculados
```

Motivo: depois que o Host muda de Site, o NetBox rejeita uma VM que ainda mantém `site` antigo enquanto continua ligada ao novo Device.

Proteções:

- VM ligada a Device: o Device precisa estar no Site alvo;
- VM ligada a Cluster: o Cluster não pode estar scoped em outro Site;
- identidade da VM é revalidada depois das migrações de Host/Cluster e imediatamente antes do PATCH;
- o mesmo ID da VM é preservado;
- IPs vinculados acompanham o Tenant;
- sem DELETE automático.

Essa lógica é genérica e não contém hardcode de PXMETAIS, MAC, MIZU, DCM, FBA ou qualquer IP.

---

## 8. Resolver Tenant/Site

### Host

```text
rede de gerenciamento autoritativa
→ mapping mais específico
→ Tenant/Site
```

### VM

```text
VM
→ Host onde está executando
→ Tenant/Site do Host
```

IP da VM é fallback. Sem evidência confiável, fica `REVIEW`.

A localização no NetBox representa onde a VM está hospedada, não necessariamente o local que ela atende.

---

## 9. Comparação NetBox × Hypervisor

```bash
netbox-discovery hypervisor run --compare
```

Somente leitura.

Compara Hosts, VMs, Clusters e Prefixes e classifica:

```text
OK
MISMATCH
MISSING
AMBIGUOUS
```

Mostra:

```text
atual=Tenant/Site
esperado=Tenant/Site
```

Regras:

- não executa POST/PATCH;
- usa o mesmo planner/identity guard de produção;
- usa lock global;
- gera `MULTI-hypervisor-compare-*.json`;
- termina com `NetBox write: NÃO`.

---

## 10. Falha parcial e retomada

O produto é idempotente por plano: objetos já concluídos devem voltar como `NOOP` na execução seguinte.

Depois de uma falha ou queda de SSH:

```text
1. confirmar que não há processo/lock ativo
2. NÃO repetir --apply cegamente
3. executar --compare
4. executar dry-run se necessário
5. revisar REVIEW/BLOCKED/MISMATCH/MISSING
6. somente depois autorizar novo --apply
```

Não existe rollback cego de escrita parcial. O journal e os relatórios preservam o que já aconteceu.

---

## 11. Delta de inventário

VM presente no snapshot anterior e ausente agora:

```text
REMOVED/REVIEW
REVIEW / NOOP
DELETE automático: NÃO
```

Ausência nunca autoriza exclusão automática.

---

## 12. APPLY

```bash
netbox-discovery hypervisor run --apply
```

Regras:

- somente `READY` escreve;
- `REVIEW` e `BLOCKED` nunca escrevem;
- preflight global ocorre antes da primeira escrita;
- reclassificações recebem preflight imediato;
- Cluster/Site usa bridge coordenada;
- VM/parent usa validação pós-migração;
- APPLY mantém journal;
- AUDIT é read-only;
- não existe DELETE automático.

---

## 13. Atualização

```bash
netbox-discovery update status
netbox-discovery update check
netbox-discovery update run
```

O updater `stable`:

- cria backup;
- valida candidato;
- preserva configuração;
- executa rollback se a validação pós-instalação falhar;
- bloqueia downgrade;
- usa quarentena para versão quebrada.

---

## 14. Schedulers

Network e Hypervisor são opt-in.

```bash
netbox-discovery scheduler status
netbox-discovery hypervisor scheduler status
netbox-discovery update scheduler status
```

Durante homologação de escrita nova, Hypervisor scheduler/APPLY automático deve permanecer desabilitado.

---

## 15. Saúde

```bash
netbox-discovery version
netbox-discovery status
netbox-discovery self-test
netbox-discovery health
netbox-discovery health --json
```

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

A matriz oficial fica em:

```text
docs/HOMOLOGACAO.md
```

`CI PASS` não significa `LIVE PASS`.
