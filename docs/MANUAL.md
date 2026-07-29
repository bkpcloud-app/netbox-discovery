# Manual Operacional — netbox-discovery

**Produto:** netbox-discovery  
**Versão:** 1.10.19 — PRODUCT V1  
**Distribuição oficial:** `bkpcloud-app/netbox-discovery`  
**Canal de produção:** `stable`  
**NetBox BKPCLOUD:** `https://inventory.bkpcloud.app.br:8080`

> `CI PASS` não equivale a `LIVE PASS`. Estado real em `docs/HOMOLOGACAO.md`.

## 1. Execução Network

```bash
netbox-discovery run
netbox-discovery run --apply
```

Fluxo 1.10.19:

```text
DISCOVER V4
→ CLASSIFY V6
→ RECONCILE V5
→ PLAN V8
→ PREFLIGHT GLOBAL FINALIZE
→ IMPORT normal V9
→ MAC RECONCILE
→ REPAIR_SAFE
→ AUDIT FINALIZE V8
```

## 2. Decisões

| Decisão/Ação | Significado | Escrita |
|---|---|---|
| `READY/CREATE` | novo Device físico validado | somente com `--apply` |
| `READY/UPDATE_SAFE` | complemento ou enriquecimento seguro | somente com `--apply` |
| `READY/REPAIR_SAFE_VM_DUPLICATE` | corrige Device duplicado criado pelo produto | após preflight global |
| `READY/NOOP` | inventário já convergente ou identidade live preservada | não altera |
| `DELEGATED` | ownership do Hypervisor | não |
| `REVIEW` | evidência insuficiente | não |
| `BLOCKED` | conflito forte | não |

## 3. Printer-MIB

A 1.10.19 consulta de forma read-only:

```text
prtGeneralPrinterName
prtGeneralSerialNumber
hrDeviceDescr
```

A resposta é incorporada ao inventário como evidência `printer-mib`. O CLASSIFY utiliza apenas fabricante/modelo/serial explicitamente encontrados.

Quando não existe modelo exato, o objeto continua genérico e não recebe alteração automática.

## 4. Upgrade seguro de Device Type genérico

Um Device Type pode mudar de genérico para exato somente quando todos os requisitos abaixo forem verdadeiros:

```text
Device description = Criado pelo netbox-discovery
match forte = SERIAL, MAC ou IP
confidence = HIGH
tipo atual = placeholder genérico
fabricante/modelo destino = explícitos e não genéricos
nenhum conflito adicional no PLAN
```

Exemplo:

```text
Unidentified / Generic Printer
→ Kyocera / ECOSYS M2040dn
```

No momento do `--apply`, o importer relê o Device e bloqueia se o tipo deixou de ser genérico ou se o objeto não pertence ao produto.

## 5. Preservação de identidade live

Uma coleta pode perder temporariamente SNMP, banner ou fingerprint. Quando SERIAL/MAC/IP ainda apontam para um Device existente com identidade específica, o PLAN não degrada o objeto para `Unknown Server` ou outro placeholder.

```text
LIVE_IDENTITY_PRESERVED_OVER_WEAK_OBSERVATION
```

Esse caminho é `READY/NOOP`: não altera o NetBox.

## 6. Alias de fabricante

Aliases reconhecidos evitam drift falso quando modelo e identidade são equivalentes:

```text
Dell Inc. = Dell
Ubiquiti Networks = Ubiquiti
Kyocera Document Solutions = Kyocera
Hewlett-Packard = HP
```

A nomenclatura já existente no Device é preservada. Não há renomeação em massa de fabricante.

## 7. Colisão segura de nomes SNMP

Equipamentos físicos diferentes podem publicar o mesmo `sysName`. O PLAN somente resolve automaticamente quando todos possuem:

- confiança HIGH;
- asset class física;
- serial ou MAC único;
- nenhum Device existente;
- nenhum conflito de IP;
- apenas os motivos `DUPLICATE_DESIRED_NAME` e `RECONCILE_REVIEW_CANDIDATE`.

O nome recebe sufixo determinístico:

```text
SW-BA17-LB43JZ
SW-BA17-KPC2C1
```

Sem identidade forte, permanece `REVIEW/BLOCKED`.

## 8. Moxa NPort 5210

```text
sysObjectID: .1.3.6.1.4.1.8691.2.7
Role: INDUSTRIAL_COMMUNICATION
Manufacturer: Moxa
Model: NPort 5210
Confidence: HIGH
```

## 9. Preflight global

Antes da primeira escrita:

```text
recalcula PLAN V8
→ valida READY normais
→ valida ownership global de IP/MAC
→ valida REPAIR_SAFE
→ relê Device, VM, interfaces, IPs e relacionamentos
→ cria REPAIR_JOURNAL
→ somente então escreve
```

Qualquer drift bloqueia.

## 10. REPAIR_SAFE de VM duplicada

Ordem protegida:

```text
1. revalidar Device, VM, interface, IP e MAC
2. bloquear primary/oob divergente
3. limpar referência primary/oob que aponta para o IP alvo
4. mover IP para virtualization.vminterface
5. definir primary IPv4 da VM se vazio
6. remover somente MACs e Device criados pelo produto
7. auditar convergência e idempotência
```

A VM nunca é removida.

## 11. Proteções obrigatórias do reparo

- Device, interfaces e IP criados pelo produto;
- Device sem serial, rack, location, cluster, virtual chassis ou device bay;
- nenhum cabo ou objeto relacionado;
- exatamente um IP observado;
- VM única por nome;
- VM sem outro primary IPv4;
- MAC VMware único e sem owner conflitante;
- primary/oob do Device vazio ou apontando para o próprio IP alvo.

## 12. Audit final

O audit confirma:

```text
Assets FAIL: 0
Checks FAIL: 0
novo PLAN sem CREATE/UPDATE_SAFE/REPAIR_SAFE elegível
```

`PASS_WITH_WARNINGS` é aceito apenas quando os contadores de FAIL são zero e os WARNs estão detalhados.

## 13. Dell PowerVault MD32xx

```text
sysObjectID = .1.3.6.1.4.1.674.10893.2.31
2 endpoints válidos → 1 STORAGE com MGMT + MGMT-2
```

## 14. Hypervisor

```bash
netbox-discovery hypervisor configure
netbox-discovery hypervisor check
netbox-discovery hypervisor run
netbox-discovery hypervisor run --compare
netbox-discovery hypervisor run --apply
```

Estado de referência homologado: `282/282 OK`.

## 15. Caminhos

```text
Aplicação:              /opt/netbox-discovery
Configuração:           /opt/netbox-discovery/config.yml
Config Hypervisor:      /etc/netbox-discovery/hypervisors.json
Relatórios:             /opt/netbox-discovery/reports
Backups:                /opt/netbox-discovery/backups
Lock global:            /var/lock/netbox-discovery-global.lock
```
