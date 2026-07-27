## V1.10.6 — Preflight global antes de qualquer escrita Hypervisor

Hotfix de segurança identificado durante a revisão final imediatamente antes do primeiro APPLY multi-contexto real.

### Gap encontrado

Na 1.10.5 o PLAN estava limpo (`REVIEW=0`, `BLOCKED=0`), porém o engine V3 executava `RECLASSIFY_SAFE` antes de chamar o preflight V2 do contexto.

Nenhum APPLY 1.10.5 foi executado no ambiente real. A produção foi bloqueada antes de qualquer escrita.

### Correção

A 1.10.6 adiciona um wrapper V4 de preflight na frente do engine V3 já validado.

Antes do primeiro POST/PATCH:

```text
DISCOVER
→ PLAN
→ autorização --apply
→ PREFLIGHT GLOBAL MULTI-CONTEXT
→ REVIEW/BLOCKED = 0
→ conjunto RECLASSIFY_SAFE inalterado
→ RECLASSIFY PREFLIGHT por contexto
→ identidade forte / existing_id / Tenant / Site revalidados
→ somente então escrita
```

O preflight global reconstrói o PLAN contra o estado atual do NetBox e aborta sem escrita se:

- surgir `REVIEW` ou `BLOCKED`;
- o conjunto de `RECLASSIFY_SAFE` mudar;
- `existing_id`, Tenant alvo ou Site alvo mudarem.

Antes de cada lote de reclassificação, o produto revalida novamente:

- serial/UUID;
- IP/MAC vinculados;
- unicidade da identidade;
- mesmo `existing_id`;
- Cluster/Prefix único quando aplicável;
- Tenant/Site alvo existente e único.

### Saída operacional

Antes da primeira escrita:

```text
===== HYPERVISOR PREFLIGHT GLOBAL MULTI-CONTEXT =====
PREFLIGHT GLOBAL: OK
NetBox write até aqui: NÃO
```

Nos contextos com migração:

```text
RECLASSIFY PREFLIGHT Tenant/Site: OK
NetBox write: NÃO
```

### Regressões

- conjunto idêntico de `RECLASSIFY_SAFE` passa;
- mudança de `existing_id` aborta;
- novo `REVIEW/BLOCKED` aborta antes de qualquer write;
- identidade forte é revalidada imediatamente antes de reclassificar;
- identity drift aborta.

---

## V1.10.5 — Diagnóstico completo do PLAN no terminal

Correção de UX/operabilidade identificada durante a homologação real da 1.10.4.

O dry-run já mostrava `UPDATE_SAFE`, `RECLASSIFY_SAFE`, `REVIEW` e `BLOCKED`, mas os objetos `READY/CREATE` ainda exigiam leitura manual do JSON ou um script auxiliar para listar exatamente o que seria criado.

Isso não faz parte do desenho de produto.

### Mudança

O próprio comando:

```bash
netbox-discovery hypervisor run
```

passa a listar automaticamente:

```text
===== HYPERVISOR NOVOS OBJETOS READY =====
READY | ... | CREATE | alvo=Tenant/Site
NOVOS OBJETOS READY: N

===== HYPERVISOR AJUSTES/MIGRAÇÕES SEGURAS PENDENTES =====
READY | ... | UPDATE_SAFE
READY | ... | RECLASSIFY_SAFE

===== HYPERVISOR PENDÊNCIAS DO PLAN =====
REVIEW
BLOCKED

===== RESUMO DE ESCRITA DO DRY-RUN =====
CREATE READY: N
UPDATE_SAFE/RECLASSIFY_SAFE READY: N
REVIEW/BLOCKED: N
NetBox write: NÃO
```

### Política operacional

- nenhuma etapa normal exige Python ad-hoc para abrir/filtrar o PLAN;
- o JSON continua disponível para auditoria detalhada;
- dry-run continua sem escrita;
- a única autorização manual obrigatória continua sendo `--apply`;
- Hypervisor continua sem DELETE automático.

### Regressão

O CI passa a exigir que um registro `READY/CREATE` apareça na saída operacional do runner.

---

## V1.10.4 — Reclassificação segura e delta de inventário Hypervisor

Evolução do runtime multi-contexto após o dry-run real no DCM mostrar que o resolver posicionava corretamente Hosts/VMs em 12 contextos, porém objetos legados ainda existiam no Tenant/Site incorreto devido ao primeiro APPLY single-site.

### Reclassificação segura

O PLAN passa a suportar:

```text
READY / RECLASSIFY_SAFE
```

quando o mesmo objeto já existe no NetBox fora do contexto autoritativo e a identidade global é inequívoca.

Evidências fortes:

- serial/UUID único;
- IP vinculado ao mesmo objeto;
- MAC vinculado ao mesmo objeto;
- combinação coerente dessas evidências.

Proteções:

- nome sozinho nunca autoriza migração;
- identidade global ambígua permanece `REVIEW`;
- serial e IP/MAC apontando para objetos diferentes permanece `REVIEW`;
- o mesmo ID é preservado;
- nenhuma migração executa DELETE.

### Delta de inventário

VM presente anteriormente e ausente agora:

```text
REMOVED/REVIEW
REVIEW / NOOP
DELETE automático: NÃO
```

### Evidência real 1.10.4

Dry-run no DCM em 27/07/2026:

```text
22/22 Hosts resolvidos
245/245 VMs resolvidas
12 contextos
NÃO RESOLVIDOS: 0
Objetos planejados: 281
READY: 281
REVIEW: 0
BLOCKED: 0
CREATE: 12
UPDATE_SAFE: 50
RECLASSIFY_SAFE: 44
NOOP: 175
NetBox write: NÃO
```

---

## V1.10.3 — Rede de gerenciamento autoritativa VMware

Para VMware, Tenant/Site passa a usar uma rede de gerenciamento autoritativa por Host:

1. IP de vmkernel correspondente ao FQDN/nome do ESXi;
2. `vmk0` marcada como management;
3. única candidata management;
4. múltiplas candidatas sem evidência forte → `REVIEW`.

Interfaces auxiliares continuam no inventário, mas não decidem Site/Tenant.

Validação real no DCM confirmou `10.1.1.0/24` como rede autoritativa dos quatro Hosts do Datacenter DCM, ignorando os vmkernel auxiliares `192.168.x` para placement.

---

## V1.10.2 — Agrupamento de redes VMware por Datacenter

- agrupa evidências de placement por VMware Datacenter;
- pergunta Tenant/Site uma vez por grupo quando seguro;
- mantém rede ambígua separada;
- não altera política de escrita/DELETE.

---

## V1.10.1 — Documentação obrigatória da release

- README, Manual, Comandos Rápidos, Security, Release Notes e Matriz de Homologação passam a acompanhar `VERSION`;
- self-test/CI bloqueiam release documentalmente inconsistente;
- `CI PASS` e `LIVE PASS` passam a ser estados explicitamente separados.

---

## V1.10.0 — Hypervisor multi-Tenant / multi-Site

Modos:

```text
single_site
multi_site
multi_tenant
```

- Host resolvido por rede de gerenciamento;
- VM herda contexto do Host;
- IP da VM é fallback;
- sem resolução confiável → `REVIEW`;
- proteção global impede CREATE duplicado fora do contexto alvo.

---

## V1.9.x — Consolidação anterior

Principais marcos:

- 1.9.8: diagnóstico visível de resíduos;
- 1.9.7: consistência V2 entre dry-run, preflight e audit;
- 1.9.6: política de IP autoritativo de VM;
- 1.9.4: carregamento VMware no mesmo processo;
- 1.9.3: dependências VMware isoladas;
- 1.9.2: Tenant Group genérico;
- 1.9.0: identidade física, auto-update e hardening operacional.

---

## V1.8.0

Hypervisor integrado e endpoint BKPCLOUD fixo.

## V1.7.0

Estabilização de classificação e inventário.

## V1.6.0

Reconciliação segura e descoberta CFTV.

## V1.5.x

Consolidação inicial do PRODUCT V1, instalador, preservação de configuração e correções de DNS/versão.
