## V1.10.7 — Migração coordenada de Cluster/Site e compare read-only

Hotfix criado a partir da evidência do primeiro APPLY multi-contexto real em 27/07/2026.

### Evidência do APPLY parcial 1.10.6

O preflight global passou corretamente antes da primeira escrita:

```text
PREFLIGHT GLOBAL: OK
READY/CREATE: 12
READY/UPDATE_SAFE: 53
READY/RECLASSIFY_SAFE: 44
REVIEW/BLOCKED: 0
NetBox write até aqui: NÃO
```

`MIZU/DCM` concluiu com 4 Hosts, 124 VMs e 0 erros. `MIZU/FAB` reclassificou o Host `10.5.1.21` e concluiu com 1 Host, 4 VMs e 0 erros.

Ao iniciar `MIZU/FBA`, o NetBox bloqueou a alteração do Cluster `FBA`:

```text
HTTP 400 /api/virtualization/clusters/4/
{"scope":["2 devices are assigned as hosts for this cluster but are not in site FBA"]}
```

O pipeline parou e os contextos posteriores não foram escritos.

### Causa raiz

A 1.10.6 ordenava reclassificações como:

```text
PREFIX → CLUSTER → HOST → VM
```

Isso não funciona quando o Cluster possui scope no Site antigo e seus Devices-host também precisam mudar de Site: o NetBox exige coerência entre o Site do Cluster e o Site dos hosts.

### Bridge segura de Cluster/Site

A 1.10.7 usa a natureza opcional do scope do Cluster para uma transição coordenada:

```text
RECLASSIFY PREFLIGHT
→ validar todos os Devices-host do Cluster
→ remover temporariamente o scope do Cluster
→ mover os Devices-host para o Site alvo
→ reaplicar Tenant/scope do Cluster no Site alvo
→ continuar VMs
```

Proteções adicionais:

- todos os hosts membros fora do Site alvo precisam estar cobertos por `HOST / RECLASSIFY_SAFE` no mesmo contexto;
- Device-host com rack/location bloqueia migração automática de Site;
- Cluster e identidades fortes são revalidados imediatamente antes da escrita;
- composição inesperada do Cluster aborta a migração do contexto;
- nenhuma rotina executa DELETE automático.

### Compare oficial NetBox × Hypervisor

Novo modo read-only:

```bash
netbox-discovery hypervisor run --compare
```

Ele reutiliza o mesmo planner/identity guard de produção para comparar o estado atual do NetBox contra Tenant/Site esperado pelas sources e mappings.

Estados apresentados:

```text
OK
MISMATCH
MISSING
AMBIGUOUS
```

Abrange Hosts, VMs, Clusters e Prefixes, mostra `atual=Tenant/Site` versus `esperado=Tenant/Site`, gera `MULTI-hypervisor-compare-*.json` e nunca executa POST/PATCH.

Esse modo foi adicionado para auditoria após APPLY parcial e também pode ser usado antes/depois de uma escrita real.

### Estado de homologação

Na publicação inicial da 1.10.7, a bridge de Cluster/Site e o compare permanecem `CI PASS / NOT LIVE` até validação real no estado parcial do DCM. O APPLY multi-contexto completo continua `LIVE PARTIAL`.

---

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

O CI exige que registros `READY/CREATE` apareçam na saída operacional do runner.
