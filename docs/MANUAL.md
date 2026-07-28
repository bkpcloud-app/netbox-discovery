# Manual Operacional — netbox-discovery

**Produto:** netbox-discovery  
**Versão:** 1.10.16 — PRODUCT V1  
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

Fluxo 1.10.16:

```text
DISCOVER
→ CLASSIFY V5
→ RECONCILE V5
→ PLAN V6
→ PREFLIGHT GLOBAL FINALIZE
→ IMPORT normal
→ MAC RECONCILE de Devices
→ VM MAC ENSURE, quando elegível
→ REPAIR_SAFE
→ AUDIT FINALIZE
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
recalcula PLAN V6
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

## 4. Reparo de VM com interface única sem MAC

A 1.10.16 trata o caso em que existe uma VM inequívoca, mas sua única interface ainda não possui objeto MAC no NetBox.

O fallback só é elegível quando:

1. existe uma única VM correspondente pelo nome;
2. a VM possui exatamente uma interface live;
3. a interface não possui nenhum outro MAC;
4. existe exatamente um MAC VMware forte para o asset;
5. o MAC está ausente, sem vínculo ou já pertence à mesma interface;
6. o MAC não pertence a outro objeto e não está duplicado;
7. Device, interface física e IP mantêm ownership integral do produto;
8. o Device não possui serial, rack, location, cluster, cabo ou objetos relacionados;
9. a VM não possui outro primary IPv4.

A execução faz, nesta ordem:

```text
1. cria/atribui o MAC à única virtualization.vminterface
2. define primary_mac_address dessa interface
3. move o IP para a interface da VM
4. define primary_ip4 da VM se estiver vazio
5. limpa primary/oob do Device duplicado
6. remove somente MACs do Device criados pelo produto
7. remove somente o Device duplicado criado pelo produto
```

VM com mais de uma interface permanece `BLOCKED`. O produto não escolhe interface sem evidência.

## 5. Caminho normal por MAC

Quando o MAC VMware já existe no NetBox, a ação `REPAIR_SAFE_VM_DUPLICATE` continua exigindo correspondência exata com uma única interface da VM inequívoca.

O anti-flap pode fornecer `historical_vmware_mac`, mas ele precisa ser OUI VMware e passar por uma das duas validações:

```text
correspondência exata com uma interface live
```

ou:

```text
VM única + exatamente uma interface vazia + MAC forte sem outro owner
```

A VM nunca é removida.

## 6. MAC RECONCILE de Devices

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

## 7. Recuperação de falha parcial

Se o IP já tiver sido movido, mas o Device duplicado ainda existir:

```text
RECOVERY_AFTER_IP_MOVE
```

A próxima execução faz novo preflight e conclui somente a limpeza segura restante.

Relatório:

```text
/opt/netbox-discovery/reports/<SITE>-repair-journal-*.json
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

O `auditor_v6` valida:

- READY normais;
- MACs de Devices físicos;
- MAC criado/atribuído à interface da VM no fallback;
- Device duplicado removido;
- IP na interface correta da VM;
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
