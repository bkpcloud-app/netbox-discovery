# netbox-discovery 1.10.3 — Matriz de Homologação

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
10.1.1.20 → VMware vCenter 7.0.3
10.1.1.10 → VMware vCenter 8.0.3
hosts=22
VMs=255
clusters=2
```

Isso não comprova por si só a classificação correta de Tenant/Site.

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

Depois foi identificado que os dois vCenters eram tratados como `MIZU/DCM`, embora enxergassem Hosts de vários Sites. Portanto aquela localização não representa o desenho final multi-contexto.

## Agrupamento por Datacenter — 1.10.2

**Estado:** LIVE PARTIAL

Ao vivo, a source `vmware-10-1-1-20` mostrou:

```text
Grupos de posicionamento: 1
Redes management detectadas: 11
Datacenter: DCM
Hosts: vm-ae01.mizu.local, vm-ae02.mizu.local, vm-ae03.mizu.local, vm-ae04.mizu.local
Cluster(s): Cluster
```

As redes exibidas incluíam:

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

Conclusão: agrupar por Datacenter funcionou, mas `management=True` em vmkernel não pode significar automaticamente “rede autoritativa para Tenant/Site”. A execução foi interrompida antes de salvar mappings.

## Rede de gerenciamento autoritativa VMware — 1.10.3

**Estado:** LIVE PASS para seleção da rede autoritativa

Regra implementada:

```text
vmkernel com serviço management
            ≠
rede autoritativa para Tenant/Site
```

Prioridade:

```text
1. IP que corresponde ao FQDN/nome do ESXi
2. vmk0 marcada como management
3. única candidata management
4. múltiplas candidatas sem evidência forte → sem resolução / REVIEW
```

### Evidência real DCM — 27/07/2026

Versão:

```text
netbox-discovery 1.10.3
```

Source:

```text
vmware-10-1-1-20
VMware vCenter Server 7.0.3 build-24322018
```

Resultado observado ao vivo:

```text
Grupos de posicionamento: 1 | Redes management detectadas: 1

[1] Datacenter: DCM
  Hosts: vm-ae01.mizu.local, vm-ae02.mizu.local, vm-ae03.mizu.local, vm-ae04.mizu.local
  Cluster(s): Cluster
  Rede de gerenciamento: 10.1.1.0/24
```

As redes auxiliares `192.168.x` deixaram de participar dos mappings Tenant/Site.

**NetBox write de inventário:** NÃO.  
A opção de criação/reuso estrutural foi respondida com `n` durante esta validação.

Portanto, a **seleção da rede de gerenciamento autoritativa VMware da 1.10.3 está LIVE PASS** no primeiro vCenter DCM.

## Hypervisor multi-Tenant / multi-Site — estado geral

**Estado:** LIVE PARTIAL / fluxo completo ainda NOT LIVE

Já validado ao vivo:

- conexão das duas sources VMware;
- coleta consolidada de 22 Hosts / 255 VMs;
- escolha do modo `multi_tenant`;
- agrupamento por Datacenter;
- seleção autoritativa correta `10.1.1.0/24` na source `vmware-10-1-1-20`.

Ainda falta:

- concluir e salvar o mapping da primeira source;
- mapear a segunda source;
- `hypervisor check` após mappings;
- `hypervisor run` sem `--apply` em multi-contexto real;
- avaliar os 280 objetos existentes em `MIZU/DCM`;
- projetar/revisar reclassificação segura;
- APPLY multi-contexto real;
- AUDIT e segundo dry-run de idempotência.

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
1. concluir POLIMIX / MIZU / DCM para 10.1.1.0/24 na primeira source
2. salvar a primeira source
3. confirmar mode=multi_tenant e maps=1
4. repetir na segunda source
5. hypervisor check
6. hypervisor run SEM --apply
7. revisar contextos, REVIEW/BLOCKED e objetos já existentes
8. somente após plano seguro considerar APPLY
9. AUDIT + segundo dry-run
```

## Regra de evidência

Para promover algo para LIVE PASS, registrar:

- versão executada;
- comando/etapa;
- resultado relevante;
- quantidade de objetos quando aplicável;
- escrita SIM/NÃO;
- resultado do AUDIT quando houver escrita.
