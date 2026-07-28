# Manual Operacional — netbox-discovery

**Produto:** netbox-discovery  
**Versão:** 1.10.13 — PRODUCT V1  
**Distribuição oficial:** `bkpcloud-app/netbox-discovery`  
**Canal de produção:** `stable`  
**NetBox BKPCLOUD:** `https://inventory.bkpcloud.app.br:8080`

> `CI PASS` não equivale a `LIVE PASS`. Estado real em `docs/HOMOLOGACAO.md`.

## 1. Pipeline Network

Dry-run:

```bash
netbox-discovery run
```

```text
DISCOVER → CLASSIFY → RECONCILE → PLAN
```

Escrita explícita:

```bash
netbox-discovery run --apply
```

```text
DISCOVER → CLASSIFY → RECONCILE → PLAN → IMPORT READY → AUDIT
```

## 2. Decisões Network

| Decisão | Significado | Escrita |
|---|---|---|
| `READY` | evidência suficiente | somente com `--apply` |
| `DELEGATED` | ownership de outro pipeline | não |
| `REVIEW` | precisa revisão | não |
| `BLOCKED` | conflito forte | não |

Ações usuais: `CREATE`, `UPDATE_SAFE`, `NOOP`, `CONFLICT`.

## 3. Identidade anti-flap — 1.10.12+

Uma coleta pode perder temporariamente uma evidência que apareceu na coleta anterior. Isso não deve mudar a natureza do asset.

Exemplo real do DCM:

```text
SRV-AE11
coleta anterior: MAC VMware 00:50:56:9F:9E:70
→ VIRTUAL_MACHINE_CANDIDATE

coleta seguinte: MAC não observado
→ NÃO pode virar Device físico automaticamente
```

Outro exemplo:

```text
ME4024 controller
coleta anterior: FA-MIB + serial do array
coleta seguinte: FA-MIB sem resposta
→ identidade STORAGE não deve desaparecer
```

A 1.10.12+ consulta classificações recentes do mesmo Site/IP, por até 48 horas, e retém somente evidência forte:

- `VIRTUAL_MACHINE_CANDIDATE` com OUI VMware;
- storage com serial válido e/ou `connUnitId` válido.

Regras de segurança:

- hardware físico forte atual vence histórico VMware;
- serial atual diferente do histórico gera conflito;
- FA ID atual diferente do histórico gera conflito;
- `connUnitId` todo zero é inválido;
- MAC VMware histórico não é copiado para a interface atual; serve apenas para decisão de ownership;
- ausência transitória não vira evidência negativa.

O terminal informa:

```text
Anti-flap: identidade forte preservada de <arquivo anterior>
VMware MAC histórico: 00:50:56:...
```

## 4. Cross-pipeline Network ↔ Hypervisor — 1.10.12+

O planner consulta as VMs do mesmo Tenant/Site.

Quando o Network encontra um asset com evidência VMware e existe exatamente uma VM com o mesmo nome:

```text
VM candidate
+ nome único no inventário VM
→ DELEGATED
→ NOOP
→ nenhuma criação física
```

Se um `dcim.device` já existir para esse asset:

```text
BLOCKED
PHYSICAL_DEVICE_CONFLICT_WITH_HYPERVISOR_VM:<id>
```

Nenhuma remoção é feita automaticamente. O conflito precisa ser tratado pelo fluxo do produto.

Sem VM por nome e sem Device físico:

```text
REVIEW
VIRTUAL_MACHINE_CANDIDATE_NO_VM_MATCH
```

### 4.1 Precedência de ownership por IP — 1.10.13

Se o planner base já provou que o IP está atribuído a `virtualization.vminterface`, a decisão `DELEGATED/NOOP` é autoritativa e não pode ser rebaixada pela ponte de nome.

```text
IP em virtualization.vminterface
→ DELEGATED/NOOP
→ não executar name bridge para rebaixar a decisão
```

A ponte por nome serve apenas para acrescentar ownership quando o IP ainda não o provou. O conflito físico/VM de `SRV-AE11` continua `BLOCKED`.

## 5. PowerVault / FA-MIB — 1.10.11+

Árvore consultada:

```text
.1.3.6.1.3.94.1.6.1
```

Campos:

```text
connUnitId
connUnitType
connUnitProduct
connUnitSn
```

Somente `connUnitType=storage-subsystem(11)` entra como identidade de array.

A 1.10.12+ executa até três tentativas read-only da leitura FA-MIB.

Identidade:

```text
serial válido             → forte
connUnitId válido         → forte
connUnitId 000...000      → ignorado
```

Quando duas controladoras apresentam o mesmo serial/ID forte, o reconciliador pode gerar um único asset com múltiplos IPs de gerenciamento.

## 6. Dell Networking

Modelos físicos Dell reconhecidos por hardware/ENTITY-MIB têm prioridade sobre Linux/SSH/Web genérico.

```text
N2024      → NETWORK_SWITCH/HIGH
PCT7024    → NETWORK_SWITCH/HIGH
S4128F-ON  → NETWORK_SWITCH/HIGH
```

## 7. Diagnóstico Network

O `run` mostra:

```text
NETWORK PLAN DIAGNÓSTICO
NETWORK DELEGADOS AO HYPERVISOR
NETWORK NOVOS OBJETOS READY
NETWORK AJUSTES READY
NETWORK PENDÊNCIAS POR MOTIVO
NETWORK PENDÊNCIAS DETALHADAS
```

Não é necessário usar Python/JSON ad-hoc para descobrir os motivos do PLAN.

## 8. IMPORT Network

O importer recalcula o PLAN com `planner_v3.py` imediatamente antes da escrita.

```text
PLAN atual
→ PRE-FLIGHT
→ somente READY
→ primeiro erro inesperado interrompe APPLY
```

`DELEGATED`, `REVIEW` e `BLOCKED` nunca entram no IMPORT.

## 9. AUDIT

O auditor usa o mesmo planner V3 para o preview de idempotência.

A partir da 1.10.12, WARN/FAIL aparecem no terminal:

```text
===== AUDIT PENDÊNCIAS DETALHADAS =====
WARN | ...
FAIL | ...
```

`PASS_WITH_WARNINGS` não é tratado como falha de escrita, mas as divergências ficam visíveis.

## 10. Interfaces e IPs físicos

O Network cria somente interfaces de gerenciamento/OOB respaldadas por IP observado.

```text
Device
→ MGMT / MGMT-2 / ...
→ IP observado
→ primary IPv4 quando aplicável
```

O produto não cria todas as portas de um switch apenas porque IF-MIB as expôs.

## 11. Hypervisor

```bash
netbox-discovery hypervisor configure
netbox-discovery hypervisor check
netbox-discovery hypervisor run
netbox-discovery hypervisor run --compare
netbox-discovery hypervisor run --apply
netbox-discovery hypervisor status
```

Referência LIVE PASS:

```text
Objetos comparados: 282
OK: 282
MISMATCH: 0
MISSING: 0
AMBIGUOUS: 0
COMPARE STATUS: OK
```

## 12. Falha parcial

```text
1. preservar estado/relatórios
2. confirmar processo e lock
3. não repetir --apply cegamente
4. rodar dry-run/compare apropriado
5. corrigir o produto, não o inventário em massa
6. somente depois retomar
```

## 13. Update

```bash
netbox-discovery update status
netbox-discovery update check
netbox-discovery update run
```

`stable` usa backup, validação, preservação de configuração e rollback de candidato inválido.

## 14. Schedulers

```bash
netbox-discovery scheduler status
netbox-discovery hypervisor scheduler status
netbox-discovery update scheduler status
```

Network e Hypervisor são opt-in.

## 15. Caminhos

```text
Aplicação:              /opt/netbox-discovery
Configuração principal: /opt/netbox-discovery/config.yml
Config Hypervisor:      /etc/netbox-discovery/hypervisors.json
Config por Site:        /opt/netbox-discovery/config/sites/
Relatórios:             /opt/netbox-discovery/reports
Backups:                /opt/netbox-discovery/backups
Lock global:            /var/lock/netbox-discovery-global.lock
```
