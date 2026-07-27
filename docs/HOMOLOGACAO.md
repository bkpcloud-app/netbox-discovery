# netbox-discovery 1.10.9 — Matriz de Homologação

Este arquivo separa **implementação/CI** de **validação real ao vivo**.

## Estados

```text
LIVE PASS     = validado ao vivo com evidência
LIVE PARTIAL  = parte relevante validada, fluxo completo ainda pendente
CI PASS       = regressões automatizadas passaram
NOT LIVE      = ainda não validado ao vivo
```

> Nunca chamar uma função de homologada apenas porque o código existe ou o CI passou.

---

## Ambiente de referência

```text
Proxy: SNOC-AGL-DCM
Python: 3.6.8
Tenant Group base: POLIMIX
Tenant base: MIZU
Site base: DCM
NetBox: https://inventory.bkpcloud.app.br:8080
```

## Mappings Hypervisor LIVE

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

---

## Histórico relevante

```text
1.9.2   Tenant Group/Tenant/Site genérico                      LIVE PASS
1.9.3   dependências VMware isoladas                           LIVE PASS
1.9.4   configure/connect/save VMware                          LIVE PASS
1.9.6   política de IP autoritativo de VM                      LIVE PASS
1.10.3  management network autoritativa VMware                 LIVE PASS
1.10.3  resolver multi-contexto                                LIVE PASS
1.10.4  RECLASSIFY_SAFE em dry-run                             LIVE PASS
1.10.5  diagnóstico automático do PLAN Hypervisor              LIVE PASS
1.10.6  preflight global antes da primeira escrita             LIVE PASS
1.10.7  bridge Cluster/Site                                    LIVE PASS
1.10.7  compare read-only                                      LIVE PASS
1.10.8  VM parent/site bridge                                  LIVE PASS
1.10.9  diagnóstico automático do PLAN Network                 NOT LIVE
```

---

## Hypervisor multi-contexto — estado final 1.10.8

O APPLY real 1.10.8 concluiu os 12 contextos.

PXMETAIS/MAC validou especificamente:

```text
RECLASSIFY PREFLIGHT PXMETAIS/MAC: OK | objetos=25
VM PARENT PREFLIGHT PXMETAIS/MAC: OK | VMs=25
Hosts processados: 1
VMs processadas: 25
Erros: 0
```

AUDIT final:

```text
HYPERVISOR AUDIT MULTI-CONTEXT
Status: PASS
Contextos auditados: 12
```

Compare independente pós-APPLY:

```text
Objetos comparados: 282
OK: 282
MISMATCH: 0
MISSING: 0
AMBIGUOUS: 0
CLUSTER: OK=2
HOST: OK=22
PREFIX: OK=12
VM: OK=246
COMPARE STATUS: OK
NetBox write: NÃO
```

**Conclusão:** Hypervisor multi-contexto 1.10.8 = **LIVE PASS** para placement Tenant/Site, migração coordenada, VM Parent/Site, APPLY/AUDIT e compare final.

---

## Network DCM — primeiro dry-run real antes da 1.10.9

Execução em 27/07/2026:

```text
Rede: 10.1.1.0/24
Hosts ativos: 64
Evidence HIGH: 59
MEDIUM: 4
LOW: 1
NONE: 0
```

CLASSIFY:

```text
Registros: 64
Confiança: HIGH=47 MEDIUM=1 LOW=11 NONE=5
```

RECONCILE:

```text
Registros de IP: 64
Assets reconciliados: 60
Assets com múltiplos registros/IPs: 4
Candidatos para revisão: 3
```

PLAN:

```text
NetBox: 4 devices atuais no site
Assets planejados: 60
READY: 7
REVIEW: 47
BLOCKED: 6
CREATE: 56
NOOP: 4
READY/CREATE: 3
READY/NOOP: 4
NetBox write: NÃO
```

A descoberta encontrou equipamentos de rede reais, incluindo:

```text
10.1.1.31  SW-DCM-SERVERS  NETWORK  HIGH
10.1.1.38  SW_LINKS        NETWORK  HIGH
```

Também mostrou classificações que precisam ser investigadas, por exemplo SAN switches/appliances e dispositivos UNKNOWN.

**Nenhum APPLY Network foi autorizado nesse estado.**

---

## 1.10.9 — diagnóstico automático do PLAN Network

**Estado:** NOT LIVE  
**CI:** pendente até conclusão da branch/PR

Objetivo: eliminar leitura manual de JSON/Python para descobrir os 47 REVIEW e 6 BLOCKED do DCM.

Nova saída do próprio `netbox-discovery run`:

```text
NETWORK PLAN DIAGNÓSTICO
NETWORK NOVOS OBJETOS READY
NETWORK AJUSTES READY
NETWORK PENDÊNCIAS POR MOTIVO
NETWORK PENDÊNCIAS DETALHADAS
```

Para cada pendência:

```text
Decision
IP
nome desejado
role
confidence/score
reasons
match_state/match_reason
fabricante/modelo/serial
SNMP name/object-id/management MAC
evidência CLASSIFY
```

A 1.10.9 não altera elegibilidade de escrita. `REVIEW`/`BLOCKED` continuam sem escrita.

Regressão adicionada valida:

- READY/CREATE visível;
- REVIEW visível;
- BLOCKED visível;
- contagem por motivo;
- evidência CLASSIFY visível;
- `NetBox write: NÃO`.

Próxima homologação live esperada:

```text
1. publicar 1.10.9 stable
2. update no SNOC-AGL-DCM
3. netbox-discovery run
4. capturar diagnóstico completo dos 47 REVIEW / 6 BLOCKED
5. agrupar causas reais
6. corrigir classificador/reconciliador/planner por classe de causa
7. repetir dry-run
8. somente autorizar Network APPLY quando o PLAN representar corretamente equipamentos físicos
```

---

## Regras Network que permanecem obrigatórias

- não editar inventário em massa manualmente para “ajudar” o discovery;
- não começar Site novo diretamente com `--apply`;
- apenas `READY` escreve;
- `REVIEW`/`BLOCKED` não escrevem;
- MAC de gerenciamento autoritativo é identidade forte;
- MAC secundário não funde asset sozinho;
- múltiplos IPs do mesmo firewall não devem criar múltiplos firewalls quando identidade forte confirma o mesmo equipamento;
- redes OT/Industrial permanecem separadas conforme configuração do Site;
- ausência não vira DELETE automático.

---

## Schedulers

```text
Auto-update stable: LIVE PASS
Network scheduler: DISABLED durante homologação
Hypervisor scheduler: DISABLED durante homologação
```

Não habilitar APPLY automático de Network enquanto o fluxo Network não estiver `LIVE PASS`.
