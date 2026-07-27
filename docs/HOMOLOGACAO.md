# netbox-discovery 1.10.3 — Matriz de Homologação

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
**Release:** 1.9.2

```text
Tenant Group POLIMIX: CRIADO
Tenant MIZU: CRIADO
Site DCM: CRIADO
ESTRUTURA BASE: OK
```

A relação não é hardcoded.

---

## Dependências VMware isoladas

**Estado:** LIVE PASS  
**Release:** 1.9.3

```text
six==1.16.0
pyvmomi==7.0.3
```

O caminho VMware não força dependências Hyper-V/Rust.

---

## VMware configure / conexão / save

**Estado:** LIVE PASS  
**Release:** 1.9.4

Source validada:

```text
vmware-10-1-1-20
VMware vCenter Server 7.0.3 build-24322018
CONEXÃO: OK
```

---

## Política de IP secundário interno de VM

**Estado:** LIVE PASS  
**Release:** 1.9.6

O IP repetido `172.18.0.1` deixou de causar falso REVIEW. Dry-run observado:

```text
READY: 130
REVIEW: 0
BLOCKED: 0
```

---

## Dois vCenters no mesmo proxy

**Estado:** LIVE PASS para coleta/conectividade

```text
10.1.1.20 → VMware vCenter 7.0.3
10.1.1.10 → VMware vCenter 8.0.3
hosts=22
VMs=255
clusters=2
```

Isso não comprova classificação Tenant/Site.

---

## APPLY Hypervisor V2

**Estado:** LIVE PARTIAL  
**Release:** 1.9.7

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

Depois foi identificado que os dois vCenters estavam sendo tratados como `MIZU/DCM`, embora enxergassem hosts de vários Sites. Portanto a localização daquele primeiro APPLY não representa o desenho final.

---

## Diagnóstico de resíduos do PLAN

**Estado:** LIVE PASS  
**Release:** 1.9.8

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

## Atualização 1.10.1 / 1.10.2 no DCM

**Estado:** LIVE PASS para updater

Observado:

```text
1.10.0 -> 1.10.1: PASS
1.10.1 -> 1.10.2: PASS
Self-test: PASS
Config existente: preservada
Hypervisor sources: 2
Schedulers Network/Hypervisor: DISABLED
```

---

## Primeira tentativa real `multi_tenant` — 1.10.1

**Estado:** LIVE PARTIAL

Source `vmware-10-1-1-20` conectou corretamente e encontrou:

```text
4 Hosts
Datacenter: DCM
Cluster: Cluster
11 redes VMware marcadas com serviço management
```

A execução foi interrompida antes de preencher Tenant/Site e antes de salvar a source.

---

## Agrupamento por Datacenter — 1.10.2

**Estado:** LIVE PARTIAL

A 1.10.2 foi executada ao vivo e confirmou o agrupamento:

```text
Grupos de posicionamento: 1
Redes management detectadas: 11

Datacenter: DCM
Hosts: vm-ae01.mizu.local, vm-ae02.mizu.local, vm-ae03.mizu.local, vm-ae04.mizu.local
Cluster(s): Cluster
```

Redes exibidas:

```text
10.1.1.0/24
192.168.140.0/24
192.168.141.0/24
192.168.142.0/24
192.168.143.0/24
192.168.160.0/24
192.168.161.0/24
192.168.180.0/24
192.168.181.0/24
192.168.190.0/24
192.168.191.0/24
```

O usuário identificou imediatamente que essas redes `192.168.x` **não representam as redes corretas para posicionamento do Site**; no ambiente existem, por exemplo, redes como `10.160.1.0/24` e `10.180.1.0/24`, e a rede de gestão conhecida dos quatro ESXi é `10.1.1.0/24`.

Conclusão:

- o agrupamento por Datacenter funcionou ao vivo;
- a semântica anterior estava errada: `management=True` em vmkernel não pode equivaler automaticamente a “rede de gestão autoritativa do Host”;
- a execução foi interrompida antes de confirmar Tenant/Site e antes de salvar mappings novos.

Portanto 1.10.2 **não é LIVE PASS para seleção de rede**.

---

## Rede de gerenciamento autoritativa VMware — 1.10.3

**Estado:** CI PASS / NOT LIVE

Correção implementada:

```text
vmkernel com serviço management
            ≠
rede autoritativa para Tenant/Site
```

Prioridade de seleção:

```text
1. IP que corresponde à resolução do FQDN/nome do ESXi
2. vmk0 marcada como management
3. única rede management candidata
4. múltiplas candidatas sem evidência forte → sem resolução / REVIEW
```

Regressões automatizadas cobrem:

- caso real DCM: `vmk0=10.1.1.x` + múltiplas `192.168.x` marcadas management → somente `10.1.1.0/24` autoritativa;
- FQDN apontando para vmkernel diferente de vmk0;
- múltiplas candidatas sem DNS/vmk0 → sem resolução;
- Datacenters diferentes permanecem separados;
- VM herda contexto do Host;
- guarda global impede CREATE duplicado por serial/UUID.

**Ainda não validado ao vivo:** repetir o wizard 1.10.3 no DCM e confirmar que o posicionamento apresenta somente a rede autoritativa correta, sem as redes auxiliares `192.168.x`.

---

## Hypervisor multi-Tenant / multi-Site — estado geral

**Estado:** LIVE PARTIAL / fluxo completo ainda NOT LIVE

Já validado ao vivo:

- conexão VMware;
- duas sources;
- coleta de 22 Hosts / 255 VMs;
- escolha do modo `multi_tenant`;
- descoberta real das interfaces VMware;
- agrupamento por Datacenter da 1.10.2.

Ainda falta:

- validar seleção autoritativa 1.10.3;
- concluir mappings da primeira source;
- mapear a segunda source;
- provisionar/reutilizar os Tenants/Sites necessários;
- executar `hypervisor check` após mappings;
- dry-run multi-contexto real;
- avaliar os 280 objetos criados anteriormente em `MIZU/DCM`;
- reclassificação segura;
- APPLY multi-contexto real;
- AUDIT e segundo dry-run de idempotência.

---

## Network — persistência de MAC V2

**Estado:** CI PASS / NOT LIVE

O código possui correlação/persistência de `management_mac`, vínculo com interface e validação no audit. Ainda falta homologação real completa do endpoint `dcim/mac-addresses` no NetBox de produção.

---

## Schedulers

### Auto-update stable

**Estado:** LIVE PASS

### Network scheduler

**Estado no DCM:** DESABILITADO durante homologação.

### Hypervisor scheduler

**Estado no DCM:** DESABILITADO durante homologação.

Não habilitar APPLY automático enquanto o multi-contexto não estiver `LIVE PASS`.

---

## Próxima homologação obrigatória — DCM

```text
1. atualizar para 1.10.3
2. editar a primeira source vmware-10-1-1-20
3. escolher multi_tenant
4. confirmar que o wizard mostra a rede autoritativa correta dos Hosts
5. NÃO aceitar se aparecerem novamente as redes auxiliares 192.168.x como mappings
6. confirmar Tenant Group / Tenant / Site somente após a rede correta
7. salvar a primeira source
8. repetir na segunda source
9. hypervisor check
10. hypervisor run SEM --apply
11. revisar contextos e REVIEWs
12. avaliar reclassificação dos objetos existentes
13. somente após plano seguro considerar APPLY
14. AUDIT + segundo dry-run
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
