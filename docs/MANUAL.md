# Manual Operacional — netbox-discovery

**Produto:** netbox-discovery  
**Versão:** 1.10.18 — PRODUCT V1  
**Distribuição oficial:** `bkpcloud-app/netbox-discovery`  
**Canal de produção:** `stable`  
**NetBox BKPCLOUD:** `https://inventory.bkpcloud.app.br:8080`

> `CI PASS` não equivale a `LIVE PASS`. Estado real em `docs/HOMOLOGACAO.md`.

## 1. Execução Network

```bash
netbox-discovery run
netbox-discovery run --apply
```

Fluxo 1.10.18:

```text
DISCOVER
→ CLASSIFY V5
→ RECONCILE V5
→ PLAN V7
→ PREFLIGHT GLOBAL FINALIZE
→ IMPORT normal
→ MAC RECONCILE
→ REPAIR_SAFE com liberação do primary IP do Device
→ AUDIT FINALIZE V7
```

## 2. Decisões

| Decisão/Ação | Significado | Escrita |
|---|---|---|
| `READY/CREATE` | novo Device físico validado | somente com `--apply` |
| `READY/UPDATE_SAFE` | complemento seguro | somente com `--apply` |
| `READY/REPAIR_SAFE_VM_DUPLICATE` | corrige Device duplicado criado pelo produto | após preflight global |
| `READY/NOOP` | inventário já convergente | não altera |
| `DELEGATED` | ownership do Hypervisor | não |
| `REVIEW` | evidência insuficiente | não |
| `BLOCKED` | conflito forte | não |

## 3. Falha live tratada pela 1.10.18

Na 1.10.17, o produto criou:

```text
VM ID 359
virtualization.vminterface MGMT
MAC 00:50:56:9F:9E:70
primary_mac_address da interface
```

A transferência de `10.1.1.111/24` falhou porque o IP ainda era o primary IPv4 do Device duplicado:

```text
Cannot reassign IP address while it is designated as the primary IP for the parent object
```

A VM, a interface e o MAC foram preservados. O IP e o Device também permaneceram no estado anterior. Portanto, o estado é recuperável.

## 4. Ordem correta do reparo

Para qualquer `REPAIR_SAFE_VM_DUPLICATE` em modo `FULL`:

```text
1. revalidar todo o reparo
2. verificar primary_ip4, primary_ip6 e oob_ip do Device
3. bloquear se qualquer campo apontar para outro IP
4. limpar somente referências que apontem para o IP alvo
5. mover o IP para virtualization.vminterface
6. definir primary_ip4 da VM se vazio
7. limpar MACs duplicados do Device criados pelo produto
8. remover somente o Device duplicado criado pelo produto
9. executar audit e preview de idempotência
```

Evento esperado:

```text
PRIMARY_IP_CLEARED_BEFORE_MOVE
```

A liberação do primary IP acontece antes do PATCH de reassignment do IP.

## 5. Recuperação do estado parcial da 1.10.17

A próxima execução não deve criar outra interface. O PLAN deve encontrar a interface `MGMT` existente pelo MAC VMware e produzir novamente:

```text
READY/REPAIR_SAFE_VM_DUPLICATE
Device ID 324 → VM ID 359
IP 10.1.1.111/24 → interface MGMT existente
```

Depois:

```text
Device primary_ip4 = null
→ IP reassigned para virtualization.vminterface
→ VM primary_ip4 = IP 801
→ Device 324 removido
```

## 6. Preflight global

Antes da primeira escrita:

```text
recalcula PLAN V7
→ valida READY normais
→ valida ownership de MACs
→ valida REPAIR_SAFE
→ relê Device, VM, interfaces, IPs e relacionamentos
→ cria REPAIR_JOURNAL
→ somente então escreve
```

Qualquer drift bloqueia.

## 7. Caminhos aceitos de interface VM

```text
A. MAC VMware corresponde a uma interface live
B. VM única + uma interface vazia + MAC VMware forte
C. VM única + zero interfaces + MAC VMware forte → criar MGMT
```

VM com múltiplas interfaces sem correspondência inequívoca permanece `BLOCKED`.

## 8. Proteções obrigatórias

- Device, interfaces e IP criados pelo produto;
- Device sem serial, rack, location, cluster, virtual chassis ou device bay;
- nenhum cabo ou objeto relacionado;
- exatamente um IP observado;
- VM única por nome;
- VM sem outro primary IPv4;
- MAC VMware único e sem owner conflitante;
- primary/oob do Device vazio ou apontando para o próprio IP alvo.

A VM nunca é removida.

## 9. Recuperação de falha parcial

```text
interface criada sem MAC
→ fallback de interface única

interface + MAC criados, IP ainda no Device
→ REPAIR_SAFE com liberação do primary IP

IP já movido, Device ainda existe
→ RECOVERY_AFTER_IP_MOVE
```

## 10. Audit final

O audit confirma:

```text
Device duplicado ausente
IP na virtualization.vminterface correta
VM primary IPv4 correto
MAC único e primary na interface da VM
novo PLAN em DELEGATED/NOOP
Assets FAIL: 0
Checks FAIL: 0
```

## 11. Dell PowerVault MD32xx

```text
sysObjectID = .1.3.6.1.4.1.674.10893.2.31
2 endpoints válidos → 1 STORAGE com MGMT + MGMT-2
```

## 12. Hypervisor

```bash
netbox-discovery hypervisor configure
netbox-discovery hypervisor check
netbox-discovery hypervisor run
netbox-discovery hypervisor run --compare
netbox-discovery hypervisor run --apply
```

Estado de referência: `282/282 OK`.

## 13. Caminhos

```text
Aplicação:              /opt/netbox-discovery
Configuração:           /opt/netbox-discovery/config.yml
Config Hypervisor:      /etc/netbox-discovery/hypervisors.json
Relatórios:             /opt/netbox-discovery/reports
Backups:                /opt/netbox-discovery/backups
Lock global:            /var/lock/netbox-discovery-global.lock
```
