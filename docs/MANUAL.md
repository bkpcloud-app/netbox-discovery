# Manual Operacional — netbox-discovery

**Produto:** netbox-discovery  
**Versão:** 1.10.17 — PRODUCT V1  
**Distribuição oficial:** `bkpcloud-app/netbox-discovery`  
**Canal de produção:** `stable`  
**NetBox BKPCLOUD:** `https://inventory.bkpcloud.app.br:8080`

> `CI PASS` não equivale a `LIVE PASS`. Estado real em `docs/HOMOLOGACAO.md`.

## 1. Execução Network

Dry-run:

```bash
netbox-discovery run
```

Escrita explícita:

```bash
netbox-discovery run --apply
```

Fluxo 1.10.17:

```text
DISCOVER
→ CLASSIFY V5
→ RECONCILE V5
→ PLAN V7
→ PREFLIGHT GLOBAL FINALIZE
→ IMPORT normal
→ MAC RECONCILE de Devices
→ REPAIR_SAFE
→ AUDIT FINALIZE V7
```

## 2. Decisões

| Decisão/Ação | Significado | Escrita |
|---|---|---|
| `READY/CREATE` | novo Device físico validado | somente com `--apply` |
| `READY/UPDATE_SAFE` | complemento seguro | somente com `--apply` |
| `READY/REPAIR_SAFE_VM_DUPLICATE` | corrige Device duplicado criado pelo produto | somente após preflight global |
| `READY/NOOP` | inventário já convergente | não altera |
| `DELEGATED` | ownership do Hypervisor | não |
| `REVIEW` | evidência insuficiente | não |
| `BLOCKED` | conflito forte | não |

## 3. Preflight global

Antes da primeira escrita:

```text
recalcula PLAN V7
→ valida READY normais
→ valida ownership dos MACs esperados
→ valida todos os REPAIR_SAFE
→ relê Device, VM, interfaces, IPs, MACs e relacionamentos
→ cria REPAIR_JOURNAL
→ somente então escreve
```

Falha:

```text
PREFLIGHT GLOBAL FINALIZE: BLOQUEADO
NetBox write: NÃO
```

## 4. Reparo quando a VM possui zero interfaces

A 1.10.17 trata o caso validado no DCM em que existe uma VM inequívoca, mas ela não possui nenhuma `virtualization.vminterface` cadastrada no NetBox.

O reparo só é elegível quando:

1. existe uma única VM correspondente pelo nome;
2. a VM possui exatamente zero interfaces live;
3. existe exatamente um MAC VMware forte para o asset;
4. o MAC está ausente ou sem vínculo e pertence ao produto quando já existe;
5. o MAC não está duplicado e não pertence a outro objeto;
6. Device, interfaces físicas e IP mantêm ownership integral do produto;
7. o Device não possui serial, rack, location, cluster, cabo ou objetos relacionados;
8. existe exatamente um IP descoberto e ele ainda está atribuído ao Device duplicado;
9. a VM não possui outro primary IPv4.

A execução faz, nesta ordem:

```text
1. revalida todos os pré-requisitos sem escrita
2. cria virtualization.vminterface MGMT na VM
3. cria/atribui o MAC VMware nessa interface
4. define primary_mac_address da interface
5. move o IP para a nova interface da VM
6. define primary_ip4 da VM se estiver vazio
7. limpa primary/oob do Device duplicado
8. remove somente MACs do Device criados pelo produto
9. remove somente o Device duplicado criado pelo produto
10. executa AUDIT FINALIZE
```

A interface criada recebe:

```text
name: MGMT
enabled: true
description: Descoberto pelo netbox-discovery hypervisor
```

A VM nunca é removida.

## 5. Reparo quando a VM já possui interface

Há dois caminhos anteriores que continuam válidos:

```text
A. MAC VMware corresponde exatamente a uma única interface live
B. VM única + exatamente uma interface sem MAC + MAC VMware forte sem outro owner
```

VM com duas ou mais interfaces sem correspondência inequívoca continua `BLOCKED`.

## 6. Recuperação de falha parcial

Se a criação da interface ou do MAC ocorrer e uma etapa posterior falhar, a próxima execução deve convergir por um dos fluxos existentes:

```text
interface criada sem MAC
→ fallback de interface única

interface + MAC criados, IP ainda no Device
→ REPAIR_SAFE normal

IP já movido, Device ainda existe
→ RECOVERY_AFTER_IP_MOVE
```

Nenhuma remoção automática de VM existe.

Relatório:

```text
/opt/netbox-discovery/reports/<SITE>-repair-journal-*.json
```

## 7. MAC RECONCILE de Devices

Depois do IMPORT normal e antes do reparo destrutivo:

```text
IP único
→ dcim.interface correta
→ Device esperado
→ MAC ausente: cria
→ MAC existente sem vínculo: atribui
→ primary_mac_address: garante
```

Conflito de MAC já atribuído a outra interface ou objeto bloqueia no preflight.

Relatório:

```text
/opt/netbox-discovery/reports/<SITE>-mac-reconcile-*.json
```

## 8. Dell PowerVault MD32xx

Identificação:

```text
sysObjectID = .1.3.6.1.4.1.674.10893.2.31
```

Dois endpoints viram um único asset somente quando existem exatamente dois registros, mesmo OID/nome, `STORAGE/HIGH`, sem serial conflitante e com IPs consecutivos.

Resultado:

```text
Device STORAGE
├─ MGMT
└─ MGMT-2
```

## 9. Audit final

O `auditor_v7` valida:

- READY normais;
- MACs de Devices físicos;
- interface criada na VM correta;
- MAC VMware único e primary nessa interface;
- Device duplicado removido;
- IP atribuído à interface da VM;
- primary IPv4 da VM;
- idempotência como `DELEGATED/NOOP`.

Saída:

```text
AUDIT FINALIZE RESULTADO
Status: PASS | PASS_WITH_WARNINGS | FAIL
```

## 10. REVIEW residual

Um asset sem identidade forte pode permanecer `REVIEW` e ser ignorado pelo importer. Isso não bloqueia os READY seguros.

Nunca force classificação apenas para “zerar a tela”.

## 11. Ownership Hypervisor

```text
IP em virtualization.vminterface → DELEGATED
MAC VMware + VM única por nome   → DELEGATED
Device físico + VM inequívoca    → BLOCKED ou REPAIR_SAFE_VM_DUPLICATE
```

## 12. Hypervisor

```bash
netbox-discovery hypervisor configure
netbox-discovery hypervisor check
netbox-discovery hypervisor run
netbox-discovery hypervisor run --compare
netbox-discovery hypervisor run --apply
```

Estado de referência: `282/282 OK`, sem divergência Tenant/Site.

## 13. Caminhos

```text
Aplicação:              /opt/netbox-discovery
Configuração:           /opt/netbox-discovery/config.yml
Config Hypervisor:      /etc/netbox-discovery/hypervisors.json
Relatórios:             /opt/netbox-discovery/reports
Backups:                /opt/netbox-discovery/backups
Lock global:            /var/lock/netbox-discovery-global.lock
```
