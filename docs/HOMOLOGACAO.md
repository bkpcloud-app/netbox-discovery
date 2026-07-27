# netbox-discovery 1.10.7 — Matriz de Homologação

Este arquivo separa **implementação/CI** de **validação real ao vivo**.

## Estados

```text
LIVE PASS     = validado ao vivo com evidência
LIVE PARTIAL  = parte relevante validada, mas fluxo completo ainda pendente
CI PASS       = regressões automatizadas passaram
NOT LIVE      = ainda não validado ao vivo
```

> Nunca chamar uma função de “homologada” apenas porque o código existe ou o CI passou.

---

## DCM — ambiente de referência

```text
Proxy: SNOC-AGL-DCM
Python: 3.6.8
Tenant Group base: POLIMIX
Tenant base: MIZU
Site base: DCM
NetBox: https://inventory.bkpcloud.app.br:8080
```

## Histórico LIVE PASS relevante

```text
1.9.2  Tenant Group/Tenant/Site genérico
1.9.3  dependências VMware isoladas
1.9.4  configure/connect/save VMware
1.9.6  política de IP autoritativo de VM
1.10.3 rede de gerenciamento autoritativa VMware
1.10.3 source 1 mapping DCM
1.10.3 source 2 mapping multi-Tenant/multi-Site
1.10.3 hypervisor check multi-contexto
1.10.3 discovery/resolver multi-contexto dry-run
1.10.4 RECLASSIFY_SAFE em dry-run
1.10.5 diagnóstico automático completo do PLAN em dry-run
1.10.6 preflight global multi-contexto ao vivo
```

## Mappings LIVE

```text
10.1.1.0/24  -> MIZU/DCM
10.5.1.0/24  -> MIZU/FAB
10.2.1.0/24  -> MIZU/FBA
10.10.1.0/24 -> MIZU/FBE
10.9.1.0/24  -> MIZU/FFT
10.7.1.0/24  -> MIZU/FMN
10.6.1.0/24  -> MIZU/FMO
10.8.1.0/24  -> MIZU/FIB
10.3.1.0/24  -> MIZU/FPA
10.11.1.0/24 -> MIZU/FSO
10.4.1.0/24  -> MIZU/FVI
10.36.1.0/24 -> PXMETAIS/MAC
```

## Dry-run 1.10.3 — evidência real

Último estado antes da 1.10.4:

```text
source 1: hosts 4/4   | VMs 124/124
source 2: hosts 18/18 | VMs 121/121
Contextos resolvidos: 12
NÃO RESOLVIDOS: 0
NetBox write: NÃO
```

Plano:

```text
Objetos planejados: 281
READY: 238
REVIEW: 43
BLOCKED: 0
```

Os 43 REVIEW eram legado do primeiro APPLY single-site:

```text
18 Hosts fora do Site alvo
25 VMs PXMETAIS/MAC ainda no Tenant MIZU
```

## Reclassificação segura — 1.10.4

**Estado:** LIVE PASS para dry-run / LIVE PARTIAL para escrita

Dry-run real:

```text
Versão: 1.10.4
HYPERVISOR CHECK: OK
Contextos resolvidos: 12
NÃO RESOLVIDOS: 0
VMs adicionadas desde a coleta anterior: 0
VMs ausentes desde a coleta anterior: 0
DELETE automático: NÃO
```

Plano combinado:

```text
Objetos planejados: 281
READY: 281
REVIEW: 0
BLOCKED: 0
CREATE: 12
RECLASSIFY_SAFE: 44
NetBox write: NÃO
```

Os 44 `RECLASSIFY_SAFE` observados ao vivo:

```text
18 Hosts antigos
25 VMs PXMETAIS/MAC
1 Cluster FBA
```

## Diagnóstico automático do PLAN — 1.10.5

**Estado:** LIVE PASS para dry-run  
**CI:** PASS

Validação real em 27/07/2026:

```text
Versão instalada: 1.10.5
source 1: 4/4 Hosts | 124/124 VMs
source 2: 18/18 Hosts | 121/121 VMs
Contextos: 12
NÃO RESOLVIDOS: 0
VMs adicionadas: 0
VMs ausentes: 0
DELETE automático: NÃO
```

Plano multi-contexto:

```text
Objetos planejados: 281
READY: 281
REVIEW: 0
BLOCKED: 0
CREATE: 12
UPDATE_SAFE: 51
RECLASSIFY_SAFE: 44
NOOP: 174
NetBox write: NÃO
```

O terminal mostrou automaticamente os 12 `READY/CREATE`:

```text
11 Prefixes dos Sites
1 VM SRV-ISO04 em MIZU/FSO
```

Também mostrou automaticamente os `UPDATE_SAFE`, `RECLASSIFY_SAFE`, resumo de escrita e `REVIEW/BLOCKED: 0`.

**Conclusão 1.10.5:** diagnóstico automático do PLAN = LIVE PASS.

## Gap identificado antes do primeiro APPLY — 1.10.5

Durante a revisão final do código antes de autorizar escrita real, foi identificado que o engine V3 executava `_apply_reclassifications()` antes de chamar o preflight V2 do contexto.

Nenhum APPLY 1.10.5 foi executado no DCM. Nenhuma escrita ocorreu.

## Preflight global multi-contexto — 1.10.6

**Estado:** LIVE PASS para preflight / LIVE PARTIAL para APPLY completo  
**CI:** PASS

Ordem validada:

```text
DISCOVER
→ PLAN
→ autorização --apply
→ PREFLIGHT GLOBAL MULTI-CONTEXT (NetBox write: NÃO)
→ validar REVIEW/BLOCKED = 0
→ validar conjunto RECLASSIFY_SAFE inalterado
→ RECLASSIFY PREFLIGHT por contexto (NetBox write: NÃO)
→ revalidar identidade forte + existing_id + Tenant/Site alvo
→ somente então iniciar escrita
```

### Dry-run 1.10.6 real — 27/07/2026

```text
Versão instalada: 1.10.6
source 1: hosts 4/4 | VMs 124/124
source 2: hosts 18/18 | VMs 121/121
Contextos: 12
NÃO RESOLVIDOS: 0
Objetos planejados: 281
READY: 281
REVIEW: 0
BLOCKED: 0
CREATE: 12
UPDATE_SAFE: 53
RECLASSIFY_SAFE: 44
NOOP: 172
NetBox write: NÃO
```

### Primeiro APPLY multi-contexto real — 27/07/2026

O preflight global passou ao vivo antes da primeira escrita:

```text
PREFLIGHT GLOBAL: OK
READY/CREATE: 12
READY/UPDATE_SAFE: 53
READY/RECLASSIFY_SAFE: 44
REVIEW/BLOCKED: 0
NetBox write até aqui: NÃO
```

#### MIZU/DCM

```text
PREFLIGHT: OK
Hosts processados: 4
VMs processadas: 124
Erros: 0
NetBox write: SIM
```

#### MIZU/FAB

```text
RECLASSIFY PREFLIGHT MIZU/FAB: OK
objetos=1
NetBox write antes da migração: NÃO
Hosts processados: 1
VMs processadas: 4
Erros: 0
NetBox write: SIM
```

Evidência visual pós-APPLY parcial mostrou o Device `10.5.1.21` no Site `FAB`, enquanto Devices dos contextos seguintes ainda permaneciam em `DCM`, coerente com a interrupção subsequente do pipeline.

#### MIZU/FBA — falha controlada

```text
RECLASSIFY PREFLIGHT MIZU/FBA: OK | objetos=5 | NetBox write: NÃO
HTTP 400 /api/virtualization/clusters/4/
{"scope":["2 devices are assigned as hosts for this cluster but are not in site FBA"]}
```

O APPLY foi interrompido pelo NetBox. Contextos posteriores a FBA não foram executados.

Relatórios:

```text
MULTI-hypervisor-import-failed-20260727-163932.json
MULTI-hypervisor-run-20260727-163932.json
```

### Causa raiz confirmada

A 1.10.6 ordenava reclassificações como:

```text
PREFIX
→ CLUSTER
→ HOST
→ VM
```

Para um Cluster já scoped em `DCM`, isso é inválido: o NetBox não permite mover o Cluster para `FBA` enquanto Devices-host continuam em `DCM`; também não permite mover um Device para outro Site enquanto seu Cluster continua scoped no Site antigo.

**Conclusão:** o resolver/mapping não foi a causa. O erro é de ordem de migração coordenada Cluster ↔ Devices-host.

## Migração coordenada de Cluster/Site — 1.10.7

**Estado:** NOT LIVE  
**CI:** PENDENTE até publicação da branch

Correção implementada:

```text
RECLASSIFY PREFLIGHT
→ validar todos os Devices-host do Cluster
→ remover temporariamente o scope opcional do Cluster
→ mover Devices-host para o Site alvo
→ reaplicar Tenant/scope do Cluster no Site alvo
→ continuar VMs
```

Travas adicionadas:

- cada Device-host fora do Site alvo precisa estar coberto por `HOST / RECLASSIFY_SAFE` no mesmo contexto;
- Cluster precisa continuar único por identidade prevista;
- host com rack/location bloqueia migração automática de Site;
- identidade forte continua sendo revalidada imediatamente antes da escrita;
- se a composição do Cluster divergir, o contexto aborta.

Regressões adicionadas:

- reproduz a validação NetBox que falha se Cluster for movido antes dos hosts;
- confirma `scope=None → hosts → scope alvo`;
- bloqueia Cluster com membro fora do Site alvo sem HOST migration correspondente.

## Compare NetBox × Hypervisor — 1.10.7

**Estado:** NOT LIVE  
**CI:** PENDENTE

Novo modo oficial read-only:

```bash
netbox-discovery hypervisor run --compare
```

Objetivo: auditar estado parcial ou final do NetBox contra as sources/mappings sem qualquer PATCH/POST.

Compara:

```text
HOST
VM
CLUSTER
PREFIX
```

Estados:

```text
OK
MISMATCH
MISSING
AMBIGUOUS
```

Para VMs, o Site efetivo é derivado do Cluster ou Device quando aplicável.

Saída obrigatória:

```text
NetBox write: NÃO
MULTI-hypervisor-compare-*.json
```

## Hypervisor multi-contexto — estado geral

**Estado:** LIVE PARTIAL

Já validado:

- duas sources VMware;
- 12 mappings/contextos;
- seleção autoritativa de management;
- 22/22 Hosts resolvidos;
- todas as VMs retornadas pelas sources resolvidas;
- `NÃO RESOLVIDOS: 0`;
- guarda contra duplicação;
- reclassificação planejada automaticamente;
- diagnóstico completo do PLAN no terminal;
- preflight global real antes da primeira escrita;
- DCM APPLY real sem erros;
- FAB reclassificação/APPLY real sem erros;
- journal de falha parcial real.

Ainda falta:

- CI da 1.10.7;
- update real para 1.10.7;
- compare read-only do estado parcial;
- dry-run pós-falha;
- novo APPLY retomando FBA e contextos posteriores;
- AUDIT final;
- segundo dry-run de idempotência;
- compare final sem divergências.

## Network — persistência MAC V2

**Estado:** CI PASS / NOT LIVE

Ainda falta homologação completa ao vivo da persistência em `dcim/mac-addresses`.

## Schedulers

```text
Auto-update stable: LIVE PASS
Network scheduler: DISABLED durante homologação
Hypervisor scheduler: DISABLED durante homologação
```

Não habilitar APPLY automático enquanto o fluxo multi-contexto completo não estiver LIVE PASS.

## Próxima homologação

```text
1. CI PASS da 1.10.7
2. publicar 1.10.7 na stable
3. netbox-discovery update run
4. confirmar version = 1.10.7
5. netbox-discovery hypervisor run --compare
6. registrar estado parcial atual → esperado
7. netbox-discovery hypervisor run SEM --apply
8. confirmar REVIEW/BLOCKED = 0 ou analisar qualquer divergência
9. somente depois executar --apply
10. confirmar bridge de Cluster FBA: SCOPE RELEASE → HOSTS → SCOPE FBA
11. acompanhar contextos restantes
12. confirmar AUDIT
13. segundo dry-run
14. compare final
15. promover fluxo completo para LIVE PASS somente se idempotente e sem divergência
```
