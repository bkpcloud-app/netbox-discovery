# netbox-discovery 1.10.6 — Matriz de Homologação

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

**Estado:** LIVE PASS para dry-run / NOT LIVE para APPLY completo

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

Também mostrou automaticamente os 51 `UPDATE_SAFE`, 44 `RECLASSIFY_SAFE`, resumo de escrita e `REVIEW/BLOCKED: 0`.

**Conclusão 1.10.5:** diagnóstico automático do PLAN = LIVE PASS.

## Gap identificado antes do primeiro APPLY — 1.10.5

Durante a revisão final do código antes de autorizar escrita real, foi identificado que o engine V3 executava `_apply_reclassifications()` antes de chamar o preflight V2 do contexto.

Portanto:

```text
PLAN 1.10.5 está limpo
mas
RECLASSIFY_SAFE podia iniciar PATCH antes do preflight V2 do contexto
```

Nenhum APPLY 1.10.5 foi executado no DCM. Nenhuma escrita ocorreu.

O fluxo foi bloqueado propositalmente antes de produção.

## Preflight global multi-contexto — 1.10.6

**Estado:** CI PASS / NOT LIVE  
**CI:** run `30283140532` — todos os passos PASS

Objetivo: garantir que **nenhum POST/PATCH**, inclusive `RECLASSIFY_SAFE`, ocorra antes de validação atualizada do estado real.

Ordem 1.10.6:

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
→ APPLY V3/V2
→ AUDIT
```

O preflight global aborta antes da primeira escrita se:

- surgir `REVIEW` ou `BLOCKED`;
- o conjunto `RECLASSIFY_SAFE` mudar;
- `existing_id`, Tenant ou Site alvo divergirem.

O preflight de reclassificação aborta antes do PATCH se:

- serial/UUID não reencontrar o mesmo ID;
- IP/MAC não confirmar o mesmo objeto;
- identidade ficar ambígua;
- Cluster/Prefix deixar de ser único;
- Tenant/Site alvo deixar de ser único/existente.

Regressões CI 1.10.6 confirmadas:

- preflight aceita conjunto de reclassificação idêntico;
- mudança de `existing_id` aborta;
- `REVIEW` novo aborta antes de escrita;
- identidade forte é revalidada imediatamente antes de reclassificar;
- identity drift aborta;
- regressões legadas e Hypervisor 1.10 anteriores continuam PASS.

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
- diagnóstico completo do PLAN no terminal.

Ainda falta:

- update real para 1.10.6;
- dry-run 1.10.6;
- primeiro APPLY multi-contexto real;
- AUDIT;
- segundo dry-run de idempotência.

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
1. publicar 1.10.6 na stable
2. netbox-discovery update run
3. confirmar version = 1.10.6
4. hypervisor run SEM --apply
5. confirmar REVIEW/BLOCKED = 0
6. executar hypervisor run --apply
7. confirmar PREFLIGHT GLOBAL: OK antes de qualquer write
8. confirmar RECLASSIFY PREFLIGHT: OK nos contextos de migração
9. acompanhar IMPORT
10. confirmar AUDIT
11. segundo dry-run
12. confirmar idempotência/resíduos
```
