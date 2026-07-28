# netbox-discovery

Produto BKPCLOUD para descoberta, reconciliação e inventário seguro de infraestrutura no NetBox.

**Versão atual:** 1.10.16 — PRODUCT V1  
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
DISCOVER → CLASSIFY V5 → RECONCILE V5 → PLAN V6
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
→ PLAN V6
→ PREFLIGHT GLOBAL FINALIZE
→ IMPORT READY normal
→ MAC RECONCILE
→ VM MAC ENSURE, quando necessário
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

## 1.10.16 — reparo seguro de VM com interface única sem MAC no NetBox

A execução live da 1.10.15 confirmou que o `SRV-AE11` possui:

```text
VM única por nome: ID 359
MAC VMware forte: 00:50:56:9F:9E:70
Device duplicado integralmente criado pelo produto
```

Porém, a interface da VM não possuía objeto MAC no NetBox. Por isso o PLAN retornou:

```text
REPAIR_SAFE_NOT_ELIGIBLE: Interface da VM por MAC não é única: 0
```

O PLAN V6 adiciona um único fallback conservador. O reparo só é promovido para `READY/REPAIR_SAFE_VM_DUPLICATE` quando todas as condições forem verdadeiras:

- uma única VM já foi selecionada pelo nome;
- essa VM possui exatamente uma interface live;
- a interface não possui outro MAC;
- existe exatamente um MAC VMware forte para o asset;
- esse MAC está ausente, sem vínculo ou já pertence à mesma interface da VM;
- o MAC não está duplicado e não pertence a outro objeto;
- todas as proteções de ownership do Device, interfaces e IP da 1.10.14 continuam válidas.

Antes de mover o IP ou remover o Device duplicado, o importer:

```text
cria/atribui o MAC à única interface da VM
→ define primary_mac_address da interface
→ move o IP para virtualization.vminterface
→ define primary IPv4 da VM se vazio
→ remove somente o Device duplicado criado pelo produto
```

VM com duas ou mais interfaces continua `BLOCKED`; o produto não escolhe interface por tentativa.

## MAC RECONCILE de Devices físicos

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

A correção automática exige ownership completo do produto, ausência de vínculos manuais, VM inequívoca, IP único e ausência de outro primary IPv4 na VM.

A interface alvo deve ser comprovada por um destes caminhos:

```text
MAC VMware corresponde exatamente a uma interface live
```

ou:

```text
VM única + exatamente uma interface sem MAC + MAC VMware forte e sem outro owner
```

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
