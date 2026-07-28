# netbox-discovery

Produto BKPCLOUD para descoberta, reconciliação e inventário seguro de infraestrutura no NetBox.

**Versão atual:** 1.10.17 — PRODUCT V1  
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
DISCOVER → CLASSIFY V5 → RECONCILE V5 → PLAN V7
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
→ PLAN V7
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

## 1.10.17 — reparo seguro quando a VM não possui interface no NetBox

A validação live da 1.10.16 comprovou o último cenário pendente do `SRV-AE11`:

```text
VM única por nome: ID 359
MAC VMware forte: 00:50:56:9F:9E:70
Device duplicado integralmente criado pelo produto
Interfaces cadastradas na VM: 0
```

O PLAN V7 promove o conflito para `READY/REPAIR_SAFE_VM_DUPLICATE` somente quando todas as proteções forem verdadeiras:

- existe exatamente uma VM correspondente pelo nome;
- a VM não possui nenhuma `virtualization.vminterface`;
- existe exatamente um MAC VMware forte para o asset;
- o MAC não está duplicado nem pertence a outro objeto;
- o Device, suas interfaces e o IP foram criados pelo `netbox-discovery`;
- o Device não possui serial, rack, location, cluster, cabo ou objetos relacionados;
- existe exatamente um IP descoberto e esse IP ainda pertence ao Device duplicado;
- a VM não possui outro primary IPv4.

A execução protegida ocorre nesta ordem:

```text
1. revalidar todos os pré-requisitos sem escrita
2. criar virtualization.vminterface MGMT na VM
3. criar/atribuir o MAC VMware nessa interface
4. definir primary_mac_address da interface
5. mover o IP para a interface da VM
6. definir primary IPv4 da VM, se vazio
7. remover MACs do Device criados pelo produto
8. remover somente o Device duplicado criado pelo produto
9. auditar interface, MAC, IP, VM e idempotência
```

Se houver qualquer drift antes da criação da interface, o preflight bloqueia sem escrita. A VM nunca é removida.

## 1.10.16 — VM com uma interface sem MAC

Quando a VM já possui exatamente uma interface, mas essa interface não possui objeto MAC, o produto pode garantir o MAC VMware e então executar o mesmo reparo seguro.

VM com duas ou mais interfaces sem correspondência inequívoca continua `BLOCKED`.

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

Conflito de ownership bloqueia antes da primeira escrita.

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

A interface alvo pode ser comprovada por três caminhos:

```text
1. MAC VMware corresponde exatamente a uma interface live
2. VM única + exatamente uma interface sem MAC + MAC VMware forte
3. VM única + zero interfaces + MAC VMware forte → criar MGMT protegida
```

Em todos os caminhos, o produto exige ownership completo do Device/IP/interfaces e ausência de vínculos manuais.

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

Device físico criado pelo produto + VM inequívoca pode entrar no fluxo `REPAIR_SAFE`; qualquer Device sem ownership integral do produto permanece `BLOCKED`.

## Segurança operacional

```text
netbox-discovery run          = dry-run
netbox-discovery run --apply  = escrita somente de READY
DELEGATED / REVIEW / BLOCKED  = não escrevem
DELETE de VM                  = proibido
DELETE de Device              = somente REPAIR_SAFE com ownership integral do produto
```

Network, Hypervisor, Compare e Update compartilham lock global. POST/PATCH não recebem retry cego.

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

## Homologação

**CI PASS não equivale a LIVE PASS.**

A matriz oficial fica em `docs/HOMOLOGACAO.md`.

## Documentação obrigatória

- `README.md`
- `docs/MANUAL.md`
- `docs/COMANDOS-RAPIDOS.md`
- `docs/HOMOLOGACAO.md`
- `RELEASE-NOTES.md`
- `SECURITY.md`
