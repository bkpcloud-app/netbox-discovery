# netbox-discovery

Produto BKPCLOUD para descoberta, reconciliação e inventário seguro de infraestrutura no NetBox.

**Versão atual:** 1.10.14 — PRODUCT V1  
**Distribuição:** repositório público oficial `bkpcloud-app/netbox-discovery`  
**Canal padrão:** `stable`  
**NetBox BKPCLOUD:** `https://inventory.bkpcloud.app.br:8080`

> A documentação faz parte da release. O self-test e o CI bloqueiam publicação quando os documentos obrigatórios divergem do `VERSION`.

## Pipelines

### Network

```bash
netbox-discovery run
```

```text
DISCOVER → CLASSIFY V5 → RECONCILE V5 → PLAN V4
NetBox write: NÃO
```

Com escrita explícita:

```bash
netbox-discovery run --apply
```

```text
DISCOVER
→ CLASSIFY V5
→ RECONCILE V5
→ PLAN V4
→ PREFLIGHT GLOBAL FINALIZE
→ IMPORT READY normal
→ REPAIR_SAFE
→ AUDIT FINALIZE
```

### Hypervisor

```bash
netbox-discovery hypervisor configure
netbox-discovery hypervisor check
netbox-discovery hypervisor run
netbox-discovery hypervisor run --compare
netbox-discovery hypervisor run --apply
netbox-discovery hypervisor status
```

## 1.10.14 — finalização Network em uma única execução

A release fecha duas pendências reais do DCM no mesmo `run --apply`:

```text
Dell PowerVault MD32xx com dois IPs/controladoras
+ Device físico duplicado de uma VM criado anteriormente pelo próprio produto
```

O pipeline recalcula tudo e executa **um preflight global antes da primeira escrita**. Se qualquer proteção falhar, nenhuma escrita da etapa final é iniciada.

### Dell PowerVault MD32xx

A classificação exige o `sysObjectID` exato:

```text
.1.3.6.1.4.1.674.10893.2.31
```

A reconciliação automática só ocorre quando existem exatamente dois endpoints que atendem simultaneamente a todas as regras:

```text
mesmo sysObjectID exato
mesmo sysName não genérico
ambos STORAGE/HIGH
sem serial conflitante
IPs consecutivos
exatamente dois registros
```

Resultado esperado:

```text
1 Device STORAGE
├─ MGMT   → primeiro IP
└─ MGMT-2 → segundo IP
```

Nome igual sozinho nunca autoriza a união.

### REPAIR_SAFE de Device físico duplicado de VM

A correção automática só é elegível quando:

- existe uma única VM correspondente por nome;
- o MAC VMware resolve exatamente uma interface da VM;
- o Device foi criado pelo `netbox-discovery`;
- Device, interface e IP mantêm as descrições de ownership do produto;
- não existe serial, rack, location, cluster, virtual chassis ou device bay;
- não existem inventário, console, energia, front/rear ports ou bays relacionados;
- não existe cabo ou conexão manual;
- o IP é único e pertence somente ao Device duplicado ou já está na interface correta da VM;
- a VM não possui outro primary IPv4.

Ação:

```text
IP do Device duplicado
→ interface da VM correta
→ primary IPv4 da VM, somente se vazio
→ remove MACs criados pelo produto no Device duplicado
→ remove somente o Device duplicado criado pelo produto
```

A VM nunca é removida. Um Device sem ownership inequívoco do produto permanece `BLOCKED`.

### Recuperação de execução parcial

Antes da escrita é criado um `REPAIR_JOURNAL` read-only. Se uma falha ocorrer depois que o IP já foi movido para a VM, a execução seguinte reconhece:

```text
RECOVERY_AFTER_IP_MOVE
```

E pode concluir apenas a limpeza segura restante, com novo preflight.

## Decisões Network

```text
READY / CREATE                    → escrita somente com --apply
READY / UPDATE_SAFE               → escrita somente com --apply
READY / REPAIR_SAFE_VM_DUPLICATE  → escrita após preflight global e revalidação live
DELEGATED                         → ownership Hypervisor; não escreve no Network
REVIEW                            → não escreve
BLOCKED                           → não escreve
```

Um asset de baixa confiança, como um Web Appliance ainda sem identidade forte, pode permanecer `REVIEW` sem bloquear os READY seguros.

## Ownership Network ↔ Hypervisor

Precedência:

```text
IP em virtualization.vminterface
→ DELEGATED/NOOP
```

Quando o IP ainda não prova ownership:

```text
identidade VMware + uma única VM com mesmo nome
→ DELEGATED/NOOP
```

Quando já existe Device físico:

```text
Device físico + identidade VMware + VM única
→ BLOCKED
```

Somente a ação específica `REPAIR_SAFE_VM_DUPLICATE` pode resolver esse conflito automaticamente, e apenas sob as proteções da 1.10.14.

## Storage FibreAlliance

PowerVault ME4/ME5 continuam usando:

```text
connUnitType = storage-subsystem(11)
connUnitId   = identidade quando válido
connUnitSn   = serial forte
```

`connUnitId` composto somente por zeros é ignorado. A leitura FA-MIB tem até três tentativas read-only e identidade forte recente pode ser preservada pelo anti-flap.

## Diagnóstico no terminal

```text
NETWORK PLAN DIAGNÓSTICO
READY/CREATE
READY/UPDATE_SAFE
READY/REPAIR_SAFE
DELEGATED/HYPERVISOR
NETWORK NOVOS OBJETOS READY
NETWORK REPAROS SEGUROS READY
NETWORK PENDÊNCIAS POR MOTIVO
NETWORK PENDÊNCIAS DETALHADAS
```

## Segurança operacional

```text
run                 → dry-run
run --apply         → escrita explícita
PREFLIGHT GLOBAL    → antes da primeira escrita final
POST/PATCH/DELETE   → sem retry cego
DELETE genérico     → não existe
DELETE 1.10.14      → somente Device duplicado com ownership completo do produto
Schedulers Network → opt-in
```

Network, Hypervisor, Compare e Update compartilham o lock global.

## Caminhos

```text
Aplicação:              /opt/netbox-discovery
Configuração principal: /opt/netbox-discovery/config.yml
Config Hypervisor:      /etc/netbox-discovery/hypervisors.json
Config por Site:        /opt/netbox-discovery/config/sites/
Relatórios:             /opt/netbox-discovery/reports
Backups:                /opt/netbox-discovery/backups
Lock global:            /var/lock/netbox-discovery-global.lock
```

Relatórios novos:

```text
<SITE>-repair-journal-*.json
<SITE>-import-finalize-*.json
<SITE>-audit-finalize-*.json
```

## Homologação

**CI PASS não equivale a LIVE PASS.**

A matriz oficial fica em `docs/HOMOLOGACAO.md`.
