# netbox-discovery 1.10.5 — Matriz de Homologação

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

CI 1.10.4: PASS.

Dry-run real em 27/07/2026:

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
UPDATE_SAFE: 50
RECLASSIFY_SAFE: 44
NOOP: 175
NetBox write: NÃO
```

Os 44 `RECLASSIFY_SAFE` observados ao vivo:

```text
18 Hosts antigos
25 VMs PXMETAIS/MAC
1 Cluster FBA
```

A ação preserva identidade global e não cria duplicata.

**Ainda falta para LIVE PASS completo da reclassificação:**

```text
1. APPLY controlado
2. AUDIT
3. novo dry-run
4. confirmar idempotência/resíduos
```

## Diagnóstico automático do PLAN — 1.10.5

**Estado:** NOT LIVE  
**CI:** PENDENTE até o PR da 1.10.5 concluir

Objetivo: eliminar qualquer procedimento operacional com Python auxiliar para abrir o JSON do PLAN.

O próprio:

```bash
netbox-discovery hypervisor run
```

deve mostrar:

```text
HYPERVISOR NOVOS OBJETOS READY
READY / CREATE

HYPERVISOR AJUSTES/MIGRAÇÕES SEGURAS PENDENTES
READY / UPDATE_SAFE
READY / RECLASSIFY_SAFE

HYPERVISOR PENDÊNCIAS DO PLAN
REVIEW
BLOCKED

RESUMO DE ESCRITA DO DRY-RUN
CREATE READY: N
UPDATE_SAFE/RECLASSIFY_SAFE READY: N
REVIEW/BLOCKED: N
NetBox write: NÃO
```

Regressão obrigatória:

- `READY/CREATE` precisa aparecer no terminal;
- `UPDATE_SAFE` continua aparecendo;
- `RECLASSIFY_SAFE` continua aparecendo;
- `REVIEW/BLOCKED` continuam aparecendo;
- dry-run continua sem escrita.

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
- reclassificação planejada automaticamente no dry-run 1.10.4.

Ainda falta:

- publicar/validar terminal automático 1.10.5;
- APPLY multi-contexto real;
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
1. publicar 1.10.5 somente após CI PASS
2. netbox-discovery update run
3. confirmar version = 1.10.5
4. hypervisor check
5. hypervisor run SEM --apply
6. confirmar que CREATE aparece automaticamente no terminal
7. revisar CREATE/UPDATE_SAFE/RECLASSIFY_SAFE/REVIEW/BLOCKED
8. somente depois considerar --apply
9. AUDIT
10. segundo dry-run
```
