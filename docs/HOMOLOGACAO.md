# netbox-discovery 1.10.1 — Matriz de Homologação

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

## DCM — histórico real

### Estrutura base Tenant Group / Tenant / Site

**Estado:** LIVE PASS  
**Release de referência:** 1.9.2

Validado em DCM com:

```text
Tenant Group: POLIMIX
Tenant: MIZU
Site: DCM
```

Resultado observado:

```text
Tenant Group POLIMIX: CRIADO
Tenant MIZU: CRIADO
Site DCM: CRIADO
ESTRUTURA BASE: OK
```

Importante: a relação não é hardcoded no produto. O grupo é explícito na configuração.

---

### Dependências VMware isoladas

**Estado:** LIVE PASS  
**Release de referência:** 1.9.3

Ambiente:

```text
Proxy: SNOC-AGL-DCM
Python: 3.6.8
```

Validado que o caminho VMware instala somente o conjunto necessário para VMware e não força dependências do Hyper-V/Rust.

Conjunto top-level observado:

```text
six==1.16.0
pyvmomi==7.0.3
```

---

### VMware configure / conexão / save

**Estado:** LIVE PASS  
**Release de referência:** 1.9.4

Source validada:

```text
vmware-10-1-1-20
VMware vCenter Server 7.0.3 build-24322018
```

Resultado observado:

```text
CONEXÃO: OK
SOURCE SALVA
```

O bug de import do `vendor` na mesma execução foi corrigido e validado ao vivo.

---

### VMware hypervisor check

**Estado:** LIVE PASS

Resultado observado:

```text
NETBOX: OK
Tenant/Site: MIZU/DCM
vmware-10-1-1-20: OK
HYPERVISOR CHECK: OK
NetBox write: NÃO
```

---

### Política de IP secundário interno

**Estado:** LIVE PASS  
**Release de referência:** 1.9.6

Problema real observado:

```text
172.18.0.1
```

aparecia como IP interno repetido em VMs diferentes e gerava falso `REVIEW`.

Após correção, dry-run observado:

```text
READY: 130
REVIEW: 0
BLOCKED: 0
```

A correção foi feita por política genérica de IP autoritativo, não por exceção específica para `172.18.0.1`.

---

### Dois vCenters no mesmo proxy

**Estado:** LIVE PASS para coleta/conectividade  
**Escopo:** não significa classificação correta de Tenant/Site

Sources reais:

```text
10.1.1.20 → VMware vCenter 7.0.3
10.1.1.10 → VMware vCenter 8.0.3
```

Coleta consolidada observada:

```text
hosts=22
VMs=255
clusters=2
```

---

### APPLY Hypervisor V2

**Estado:** LIVE PARTIAL  
**Release de referência:** 1.9.7

Import real executado:

```text
Hosts processados: 22
VMs processadas: 255
Erros: 0
NetBox write: SIM
```

Isso comprova que o caminho de escrita processou os objetos sem erro de import.

Porém o pós-AUDIT retornou:

```text
PASS: 278
WARN: 1
FAIL: 1
```

Portanto **o fluxo completo não foi homologado como idempotente/perfeito**.

Além disso, depois foi identificado que as sources estavam em escopo único `MIZU/DCM`, embora os vCenters enxergassem hosts de vários Sites. Assim, a localização Tenant/Site dos objetos daquele primeiro APPLY não deve ser considerada correta como modelo final.

---

### Diagnóstico de resíduos do PLAN

**Estado:** LIVE PASS  
**Release de referência:** 1.9.8

A saída passou a mostrar automaticamente `REVIEW` e `UPDATE_SAFE` sem exigir leitura manual de JSON.

Casos observados:

```text
AGL-IBE03 → conflito de UUID/host
PROXY-DCM_VEEAM02 → disk
PROXY-DCM_VEEAM04 → disk
SNOC-PXO-DCM → device
SRV-AE02 → device
SNOC-PXARG-DCM → device
```

Esse diagnóstico levou à mudança arquitetural de 1.10.

---

## Hypervisor multi-Tenant / multi-Site — 1.10

**Estado:** CI PASS / NOT LIVE

Implementado:

```text
single_site
multi_site
multi_tenant
```

Regressões automatizadas cobrem:

- agrupamento de hosts por rede de gerenciamento;
- VM herdando contexto do Host;
- host sem mapping não sendo adivinhado;
- `multi_site` usando Tenant padrão;
- validação de mapping `multi_tenant`;
- guarda global impedindo CREATE duplicado por serial/UUID fora do contexto alvo;
- regressões antigas da linha 1.9.

**Ainda não validado ao vivo:**

- edição real das duas sources DCM para `multi_tenant`;
- descoberta real de todas as redes de gerenciamento dos 22 hosts;
- provisionamento real de todos os Tenants/Sites encontrados;
- dry-run multi-contexto real com os dois vCenters;
- comportamento do PLAN diante dos 280 objetos que já foram criados anteriormente em `MIZU/DCM`;
- migração/reclassificação segura desses objetos existentes;
- APPLY multi-contexto real;
- AUDIT/idempotência multi-contexto real.

Até esses testes ocorrerem, **não chamar 1.10 multi-contexto de homologado ao vivo**.

---

## Network — persistência de MAC V2

**Estado:** CI PASS / NOT LIVE

O código possui:

- `management_mac`;
- correlação por MAC;
- persistência em `dcim/mac-addresses`;
- vínculo com interface;
- validação no audit.

Ainda falta homologação real completa da persistência MAC no endpoint NetBox de produção, incluindo idempotência e comportamento exato de `dcim/mac-addresses`.

---

## Schedulers

### Auto-update stable

**Estado:** LIVE PASS

Atualizações reais 1.9.x → 1.10.0 foram executadas preservando configuração e com self-test PASS.

### Network scheduler

**Estado no DCM:** DESABILITADO durante homologação.

### Hypervisor scheduler

**Estado no DCM:** DESABILITADO durante homologação.

Não habilitar APPLY automático enquanto o multi-contexto não estiver homologado ao vivo.

---

## Próxima homologação obrigatória — DCM

Sequência:

```text
1. atualizar para 1.10.1+
2. editar a primeira source
3. escolher o modo correto, provavelmente multi_tenant
4. revisar cada rede de gerenciamento detectada
5. mapear Tenant Group / Tenant / Site
6. repetir na segunda source
7. hypervisor check
8. hypervisor run SEM --apply
9. conferir contextos e REVIEWs
10. avaliar reclassificação dos objetos já existentes em MIZU/DCM
11. somente após plano seguro considerar APPLY
12. executar AUDIT e segundo dry-run para idempotência
```

---

## Regra de evidência

Para promover um item deste arquivo de `CI PASS/NOT LIVE` para `LIVE PASS`, registrar pelo menos:

- versão executada;
- comando;
- resultado relevante;
- quantidade de objetos quando aplicável;
- escrita SIM/NÃO;
- resultado do AUDIT quando houver escrita.
