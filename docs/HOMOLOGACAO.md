# netbox-discovery 1.10.4 — Matriz de Homologação

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

## Estrutura base Tenant Group / Tenant / Site

**Estado:** LIVE PASS  
**Release:** 1.9.2

```text
POLIMIX
└── MIZU
    └── DCM
```

A relação não é hardcoded no produto.

## Dependências VMware e conexão

**Estado:** LIVE PASS  
**Releases:** 1.9.3 / 1.9.4

```text
six==1.16.0
pyvmomi==7.0.3
vmware-10-1-1-20: CONEXÃO OK
vmware-10-1-1-10: CONEXÃO OK
```

## Política de IP secundário de VM

**Estado:** LIVE PASS  
**Release:** 1.9.6

O IP repetido `172.18.0.1` deixou de gerar falso REVIEW. Dry-run observado:

```text
READY: 130
REVIEW: 0
BLOCKED: 0
```

## Dois vCenters no mesmo proxy

**Estado:** LIVE PASS para coleta/conectividade

```text
10.1.1.20 → VMware vCenter 7.0.3 build-24322018
10.1.1.10 → VMware vCenter 8.0.3 build-24022515
Hosts observados: 22
```

A quantidade de VMs é dinâmica e variou durante a homologação porque VMs antigas/lixo foram removidas do vCenter. O último dry-run 1.10.3 registrado em 27/07/2026 coletou 124 + 121 = 245 VMs.

## APPLY Hypervisor V2

**Estado:** LIVE PARTIAL  
**Release:** 1.9.7

Primeiro APPLY real anterior ao desenho multi-contexto:

```text
Hosts processados: 22
VMs processadas: 255
Erros: 0
NetBox write: SIM
```

Pós-AUDIT:

```text
PASS: 278
WARN: 1
FAIL: 1
```

Depois foi identificado que os dois vCenters eram tratados como `MIZU/DCM`, embora enxergassem Hosts de vários Sites. Portanto aquela localização não representa o desenho final multi-contexto e gerou objetos que precisam de reclassificação.

## Agrupamento por Datacenter — 1.10.2

**Estado:** LIVE PARTIAL

Ao vivo, a source `vmware-10-1-1-20` mostrou inicialmente:

```text
Grupos de posicionamento: 1
Redes management detectadas: 11
Datacenter: DCM
Hosts: vm-ae01.mizu.local, vm-ae02.mizu.local, vm-ae03.mizu.local, vm-ae04.mizu.local
Cluster(s): Cluster
```

As redes incluíam `10.1.1.0/24` e dez redes auxiliares `192.168.x`. Conclusão: agrupar por Datacenter funcionou, mas `management=True` em vmkernel não pode significar automaticamente “rede autoritativa para Tenant/Site”.

## Rede de gerenciamento autoritativa VMware — 1.10.3

**Estado:** LIVE PASS

Regra:

```text
1. IP que corresponde ao FQDN/nome do ESXi
2. vmk0 marcada como management
3. única candidata management
4. múltiplas candidatas sem evidência forte → sem resolução / REVIEW
```

### Evidência source 1 — 27/07/2026

```text
netbox-discovery 1.10.3
source: vmware-10-1-1-20
vCenter: 7.0.3 build-24322018
Grupos de posicionamento: 1 | Redes management detectadas: 1
Datacenter: DCM
Hosts: vm-ae01.mizu.local, vm-ae02.mizu.local, vm-ae03.mizu.local, vm-ae04.mizu.local
Rede de gerenciamento: 10.1.1.0/24
MAPEAMENTOS SALVOS: 1
mode=multi_tenant
10.1.1.0/24 -> POLIMIX / MIZU / DCM
```

As redes auxiliares `192.168.x` deixaram de participar dos mappings Tenant/Site.

## Source 2 multi-Tenant / multi-Site — 1.10.3

**Estado:** LIVE PASS para descoberta/mapping

Source:

```text
vmware-10-1-1-10
VMware vCenter Server 8.0.3 build-24022515
```

Resultado real:

```text
Grupos de posicionamento: 11 | Redes management detectadas: 11
```

Mappings confirmados:

```text
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

```text
MAPEAMENTOS SALVOS: 11
SOURCE ATUALIZADA: vmware-10-1-1-10
```

## Hypervisor check multi-contexto — 1.10.3

**Estado:** LIVE PASS

```text
NETBOX: OK
vmware-10-1-1-20: OK | VMware vCenter Server 7.0.3 build-24322018 | 7.0.3
vmware-10-1-1-10: OK | VMware vCenter Server 8.0.3 build-24022515 | 8.0.3
HYPERVISOR CHECK: OK
NetBox write: NÃO
```

## Dry-run multi-contexto real — 1.10.3

**Estado:** LIVE PASS para DISCOVER/RESOLVE/PLAN  
**APPLY multi-contexto:** ainda não executado

Última evidência registrada em 27/07/2026:

```text
source 1: hosts mapeados 4/4  | VMs mapeadas 124/124
source 2: hosts mapeados 18/18 | VMs mapeadas 121/121
HYPERVISOR CONTEXTOS RESOLVIDOS: 12
NÃO RESOLVIDOS: 0
NetBox write: NÃO
```

Contextos:

```text
MIZU/DCM       hosts=4 VMs=124
MIZU/FAB       hosts=1 VMs=4
MIZU/FBA       hosts=4 VMs=45
MIZU/FBE       hosts=2 VMs=10
MIZU/FFT       hosts=2 VMs=5
MIZU/FIB       hosts=1 VMs=4
MIZU/FMN       hosts=2 VMs=9
MIZU/FMO       hosts=1 VMs=3
MIZU/FPA       hosts=1 VMs=4
MIZU/FSO       hosts=1 VMs=6
MIZU/FVI       hosts=2 VMs=6
PXMETAIS/MAC   hosts=1 VMs=25
```

Plano combinado:

```text
Objetos planejados: 281
READY: 238
REVIEW: 43
BLOCKED: 0
CREATE: 56
UPDATE_SAFE: 51
NOOP: 174
```

Os 43 REVIEW restantes foram analisados e correspondem ao legado do primeiro APPLY single-site:

```text
18 Hosts existentes fora do Site alvo
25 VMs PXMETAIS/MAC existentes sob o Tenant anterior MIZU
```

O conflito anterior de `AGL-IBE03` em FMN era uma VM lixo/duplicada removida pelo operador. A VM legítima permanece em FBA e no último dry-run aparece somente como `READY/UPDATE_SAFE` em `MIZU/FBA`.

## Reclassificação segura — 1.10.4

**Estado:** NOT LIVE  
**CI:** PENDENTE nesta branch até a execução do GitHub Actions

Objetivo: transformar casos de identidade forte já existente fora do contexto alvo em:

```text
READY / RECLASSIFY_SAFE
```

em vez de CREATE duplicado ou migração manual.

Regras implementadas:

- identidade forte única por serial/UUID e/ou vínculo inequívoco de IP/MAC;
- serial e IP/MAC precisam apontar para o mesmo objeto;
- qualquer ambiguidade termina em `REVIEW`;
- preserva o mesmo ID do Host/VM;
- Host pode ter Tenant/Site corrigidos;
- VM pode ter Tenant corrigido;
- IPs vinculados ao objeto acompanham o Tenant;
- Cluster/Prefix somente quando a correspondência global é única;
- depois da reclassificação o pipeline V2 normal executa a reconciliação;
- DELETE automático continua proibido.

Esta função **não pode ser chamada LIVE PASS** até:

```text
1. CI PASS
2. update real para 1.10.4
3. hypervisor check
4. hypervisor run SEM --apply
5. revisar todos os RECLASSIFY_SAFE/REVIEW
6. APPLY controlado
7. AUDIT
8. segundo dry-run idempotente
```

## Delta de inventário Hypervisor — 1.10.4

**Estado:** NOT LIVE  
**CI:** PENDENTE

A coleta atual é comparada ao snapshot multi-contexto anterior. VMs ausentes são apresentadas como:

```text
REMOVED/REVIEW
REVIEW / NOOP
DELETE automático: NÃO
```

Isso foi criado porque a quantidade real de VMs variou durante a homologação (`132 → 123 → 121` na segunda source) enquanto VMs antigas eram removidas do vCenter.

## Hypervisor multi-Tenant / multi-Site — estado geral

**Estado:** LIVE PARTIAL

Já validado ao vivo:

- duas sources VMware;
- seleção autoritativa de management;
- 12 mappings/contextos;
- `hypervisor check`;
- dry-run multi-contexto real;
- 22/22 Hosts resolvidos;
- todas as VMs retornadas pelas duas sources resolvidas;
- `NÃO RESOLVIDOS: 0`;
- guarda contra duplicação do legado single-site.

Ainda falta para o fluxo completo:

- CI da 1.10.4;
- dry-run ao vivo da reclassificação 1.10.4;
- APPLY multi-contexto real com reclassificação;
- AUDIT;
- segundo dry-run de idempotência.

## Network — persistência de MAC V2

**Estado:** CI PASS / NOT LIVE

Ainda falta homologação completa da persistência em `dcim/mac-addresses` no NetBox de produção.

## Schedulers

```text
Auto-update stable: LIVE PASS
Network scheduler: DISABLED durante homologação
Hypervisor scheduler: DISABLED durante homologação
```

Não habilitar APPLY automático enquanto o fluxo multi-contexto completo não estiver LIVE PASS.

## Próxima homologação obrigatória — DCM

```text
1. publicar 1.10.4 somente após CI PASS
2. atualizar pela stable
3. confirmar netbox-discovery version = 1.10.4
4. hypervisor check
5. hypervisor run SEM --apply
6. revisar INVENTORY CHANGE
7. revisar RECLASSIFY_SAFE, REVIEW e BLOCKED
8. não executar APPLY se houver identidade ambígua
9. somente após plano seguro executar --apply
10. AUDIT
11. segundo dry-run
```

## Regra de evidência

Para promover algo para LIVE PASS, registrar:

- versão executada;
- comando/etapa;
- resultado relevante;
- quantidade de objetos quando aplicável;
- escrita SIM/NÃO;
- resultado do AUDIT quando houver escrita.
