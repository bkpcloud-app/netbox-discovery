# netbox-discovery 1.10.2 — Matriz de Homologação

Este arquivo separa claramente **implementação/CI** de **validação real ao vivo**.

## Estados

```text
LIVE PASS     = validado ao vivo com evidência de execução
LIVE PARTIAL  = parte relevante validada, mas há pendência no fluxo completo
CI PASS       = código/regressões automatizadas passaram
NOT LIVE      = ainda não homologado ao vivo
```

> Regra: nunca chamar uma função de “homologada” apenas porque o código existe ou o CI passou.

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

---

## Estrutura base Tenant Group / Tenant / Site

**Estado:** LIVE PASS  
**Release de referência:** 1.9.2

Validado:

```text
Tenant Group POLIMIX: CRIADO
Tenant MIZU: CRIADO
Site DCM: CRIADO
ESTRUTURA BASE: OK
```

A relação não é hardcoded. O grupo é explícito na configuração.

---

## Dependências VMware isoladas

**Estado:** LIVE PASS  
**Release de referência:** 1.9.3

Conjunto top-level VMware observado:

```text
six==1.16.0
pyvmomi==7.0.3
```

O caminho VMware não força dependências Hyper-V/Rust.

---

## VMware configure / conexão / save

**Estado:** LIVE PASS  
**Release de referência:** 1.9.4

Source validada:

```text
vmware-10-1-1-20
VMware vCenter Server 7.0.3 build-24322018
```

Resultado:

```text
CONEXÃO: OK
SOURCE SALVA
```

---

## VMware hypervisor check

**Estado:** LIVE PASS

```text
NETBOX: OK
Tenant/Site: MIZU/DCM
vmware-10-1-1-20: OK
HYPERVISOR CHECK: OK
NetBox write: NÃO
```

---

## Política de IP secundário interno

**Estado:** LIVE PASS  
**Release de referência:** 1.9.6

Problema real:

```text
172.18.0.1
```

aparecia repetido em VMs distintas e gerava falso `REVIEW`.

Após correção:

```text
READY: 130
REVIEW: 0
BLOCKED: 0
```

A correção é genérica; não existe exceção hardcoded para `172.18.0.1`.

---

## Dois vCenters no mesmo proxy

**Estado:** LIVE PASS para coleta/conectividade  
**Observação:** isso não significa classificação correta de Tenant/Site.

Sources reais:

```text
10.1.1.20 → VMware vCenter 7.0.3
10.1.1.10 → VMware vCenter 8.0.3
```

Coleta consolidada:

```text
hosts=22
VMs=255
clusters=2
```

---

## APPLY Hypervisor V2

**Estado:** LIVE PARTIAL  
**Release de referência:** 1.9.7

Import real:

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

Portanto o fluxo completo não foi homologado como idempotente/perfeito.

Depois foi identificado que as sources estavam sendo tratadas como `MIZU/DCM`, embora os vCenters enxergassem hosts de vários Sites. A localização Tenant/Site daquele primeiro APPLY não deve ser considerada modelo final.

---

## Diagnóstico de resíduos do PLAN

**Estado:** LIVE PASS  
**Release de referência:** 1.9.8

Casos observados:

```text
AGL-IBE03 → conflito de UUID/host
PROXY-DCM_VEEAM02 → disk
PROXY-DCM_VEEAM04 → disk
SNOC-PXO-DCM → device
SRV-AE02 → device
SNOC-PXARG-DCM → device
```

Esse diagnóstico levou à arquitetura multi-contexto.

---

## Atualização 1.10.1 no DCM

**Estado:** LIVE PASS

Observado:

```text
Versão instalada: 1.10.1
Self-test: PASS
Config existente: preservada
Hypervisor sources: 2
Schedulers Network/Hypervisor: DISABLED
```

---

## Primeira tentativa real do wizard `multi_tenant` — 1.10.1

**Estado:** LIVE PARTIAL

Source:

```text
vmware-10-1-1-20
VMware vCenter Server 7.0.3 build-24322018
```

A source foi editada até:

```text
Como este hypervisor deve ser tratado?
3 - MULTI-TENANT / MULTI-SITE
```

Conexão:

```text
CONEXÃO: OK
```

A descoberta encontrou:

```text
[1/11] Rede de gerenciamento: 10.1.1.0/24
Hosts: vm-ae03.mizu.local, vm-ae01.mizu.local, vm-ae04.mizu.local, vm-ae02.mizu.local
Datacenter(s): DCM
Cluster(s): Cluster
```

Ponto crítico observado:

```text
4 Hosts
11 redes VMware marcadas com serviço management
```

Conclusão: perguntar Tenant/Site uma vez por CIDR seria repetitivo e poderia induzir mapeamentos inconsistentes. A execução foi interrompida **antes de preencher Tenant/Site e antes de salvar a source alterada**.

Nenhum novo mapping multi-contexto foi persistido nessa tentativa.

---

## Wizard com agrupamento por Datacenter — 1.10.2

**Estado:** CI PASS / NOT LIVE

Objetivo:

- agrupar redes VMware `management` quando todas pertencem inequivocamente ao mesmo Datacenter;
- perguntar Tenant/Site uma vez por grupo;
- manter um mapping CIDR por baixo para o resolver atual;
- permitir abrir revisão por rede quando um Datacenter não representa um único Site;
- não agrupar rede compartilhada por vários Datacenters;
- não consolidar mappings existentes divergentes silenciosamente.

Regressões automatizadas cobrem:

- três redes management em dois Hosts do mesmo Datacenter → um grupo;
- Datacenters DCM e FBA → grupos separados;
- rede compartilhada entre dois Datacenters → grupo individual/ambíguo;
- VM herdando contexto do Host;
- host sem mapping não sendo adivinhado;
- `multi_site` usando Tenant padrão;
- mapping `multi_tenant` válido;
- guarda global impedindo CREATE duplicado por serial/UUID;
- regressões antigas da linha 1.9.

**Ainda não validado ao vivo:** repetir o wizard 1.10.2 no DCM e confirmar que as 11 redes do primeiro vCenter aparecem agrupadas no Datacenter `DCM`.

---

## Hypervisor multi-Tenant / multi-Site — estado geral

**Estado:** LIVE PARTIAL / fluxo completo ainda NOT LIVE

Já validado ao vivo:

- conexão VMware;
- duas sources;
- coleta de 22 Hosts / 255 VMs;
- seleção do modo `multi_tenant` até a etapa de descoberta;
- descoberta real de múltiplas redes `management` no primeiro vCenter.

Ainda falta:

- concluir mappings da primeira source;
- mapear a segunda source;
- provisionar/reutilizar todos os Tenants/Sites necessários;
- `hypervisor check` após mappings;
- dry-run multi-contexto real;
- avaliar os 280 objetos já criados anteriormente em `MIZU/DCM`;
- projetar/revisar reclassificação segura;
- APPLY multi-contexto real;
- AUDIT e segundo dry-run de idempotência.

Até isso ocorrer, não chamar o multi-contexto completo de `LIVE PASS`.

---

## Network — persistência de MAC V2

**Estado:** CI PASS / NOT LIVE

O código possui correlação/persistência de `management_mac`, vínculo com interface e validação no audit. Ainda falta homologação real completa do endpoint `dcim/mac-addresses` no NetBox de produção.

---

## Schedulers

### Auto-update stable

**Estado:** LIVE PASS

Atualizações reais 1.9.x → 1.10.1 foram executadas preservando configuração e com self-test PASS.

### Network scheduler

**Estado no DCM:** DESABILITADO durante homologação.

### Hypervisor scheduler

**Estado no DCM:** DESABILITADO durante homologação.

Não habilitar APPLY automático enquanto o multi-contexto não estiver `LIVE PASS`.

---

## Próxima homologação obrigatória — DCM

```text
1. atualizar para 1.10.2
2. editar a primeira source vmware-10-1-1-20
3. escolher multi_tenant
4. confirmar o novo grupo de posicionamento do Datacenter DCM
5. conferir Hosts e todos os CIDRs exibidos
6. confirmar se DCM é um único Tenant/Site para esse grupo
7. preencher/confirmar Tenant Group / Tenant / Site
8. salvar a primeira source
9. repetir na segunda source
10. hypervisor check
11. hypervisor run SEM --apply
12. conferir contextos e REVIEWs
13. avaliar reclassificação dos objetos já existentes em MIZU/DCM
14. somente após plano seguro considerar APPLY
15. AUDIT + segundo dry-run para idempotência
```

---

## Regra de evidência

Para promover algo para `LIVE PASS`, registrar:

- versão executada;
- comando;
- resultado relevante;
- quantidade de objetos quando aplicável;
- escrita SIM/NÃO;
- resultado do AUDIT quando houver escrita.
