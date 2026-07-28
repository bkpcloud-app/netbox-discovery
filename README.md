# netbox-discovery

Produto BKPCLOUD para descoberta, reconciliação e inventário seguro de infraestrutura no NetBox.

**Versão atual:** 1.10.15 — PRODUCT V1  
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
DISCOVER → CLASSIFY V5 → RECONCILE V5 → PLAN V5
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
→ PLAN V5
→ PREFLIGHT GLOBAL FINALIZE
→ IMPORT READY normal
→ MAC RECONCILE
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

## 1.10.15 — correção final do fluxo Network

A release corrige, no mesmo `run --apply`, os dois problemas encontrados no APPLY real da 1.10.14:

```text
SRV-AE11 não entrou no REPAIR_SAFE porque o planner ignorou historical_vmware_mac
ME5024 possuía MAC esperado no PLAN, mas a interface existente foi preservada sem criar o objeto MAC
```

### Identidade histórica VMware no reparo seguro

O `historical_vmware_mac` do anti-flap pode participar da seleção da interface da VM somente quando:

- o asset continua `VIRTUAL_MACHINE_CANDIDATE`;
- o MAC pertence a um OUI VMware conhecido;
- existe uma única VM correspondente por nome;
- o MAC corresponde exatamente a uma interface live dessa VM;
- todas as proteções de ownership do Device, interface e IP continuam válidas.

O histórico não autoriza reparo sozinho. Ele apenas recupera a evidência forte que precisa confirmar uma interface real da VM no NetBox.

### MAC RECONCILE

Após o IMPORT normal, o produto garante o objeto MAC mesmo quando o IP já estava vinculado à interface correta e o importer apenas preservou essa interface.

```text
IP único
→ dcim.interface correta
→ Device esperado
→ MAC ausente: cria
→ MAC existente sem vínculo: atribui
→ primary_mac_address: garante
```

Antes da primeira escrita, o preflight global verifica se algum MAC esperado já pertence a outra interface ou outro tipo de objeto. Conflito bloqueia toda a execução.

## Dell PowerVault MD32xx

A classificação exige o `sysObjectID` exato:

```text
.1.3.6.1.4.1.674.10893.2.31
```

A reconciliação automática só ocorre quando existem exatamente dois endpoints com o mesmo sysName/OID, `STORAGE/HIGH`, sem serial conflitante e com IPs consecutivos.

Resultado:

```text
1 Device STORAGE
├─ MGMT   → primeiro IP
└─ MGMT-2 → segundo IP
```

## REPAIR_SAFE de Device duplicado de VM

A correção automática exige ownership completo do produto, ausência de vínculos manuais, VM e interface inequívocas, IP único e ausência de outro primary IPv4 na VM.

Ação:

```text
IP do Device duplicado
→ interface da VM correta
→ primary IPv4 da VM, somente se vazio
→ remove MACs do Device criados pelo produto
→ remove somente o Device duplicado criado pelo produto
```

A VM nunca é removida. Falha depois da movimentação do IP pode ser retomada por `RECOVERY_AFTER_IP_MOVE`.

## Decisões Network

```text
READY / CREATE                    → escrita somente com --apply
READY / UPDATE_SAFE               → escrita somente com --apply
READY / REPAIR_SAFE_VM_DUPLICATE  → escrita após preflight global e revalidação live
DELEGATED                         → ownership Hypervisor; não escreve no Network
REVIEW                            → não escreve
BLOCKED                           → não escreve
```

Um asset sem identidade forte pode permanecer `REVIEW` sem bloquear os READY seguros.

## Ownership Network ↔ Hypervisor

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
→ BLOCKED ou REPAIR_SAFE_VM_DUPLICATE
```

## Segurança operacional

```text
run                 → dry-run
run --apply         → escrita explícita
PREFLIGHT GLOBAL    → antes da primeira escrita
POST/PATCH/DELETE   → sem retry cego
DELETE genérico     → não existe
DELETE seguro       → somente Device duplicado com ownership completo do produto
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

Relatórios adicionais:

```text
<SITE>-repair-journal-*.json
<SITE>-mac-reconcile-*.json
<SITE>-import-finalize-*.json
<SITE>-audit-finalize-*.json
```

## Homologação

**CI PASS não equivale a LIVE PASS.** A matriz oficial fica em `docs/HOMOLOGACAO.md`.
