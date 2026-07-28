# Manual Operacional — netbox-discovery

**Produto:** netbox-discovery  
**Versão:** 1.10.11 — PRODUCT V1  
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

| Decisão | Significado | Escrita Network |
|---|---|---|
| `READY` | elegível | somente com `--apply` |
| `DELEGATED` | ownership pertence a outro pipeline | não |
| `REVIEW` | precisa revisão | não |
| `BLOCKED` | conflito forte | não |

Ações usuais: `CREATE`, `UPDATE_SAFE`, `NOOP`, `CONFLICT`.

## 3. Storage FibreAlliance / PowerVault — 1.10.11

O produto não considera dois IPs com o mesmo nome suficientes para representar um único storage.

O discovery 1.10.11 consulta a árvore FCMGMT/FibreAlliance:

```text
.1.3.6.1.3.94.1.6.1
```

Campos usados:

```text
connUnitId       → identidade persistente da connectivity unit
connUnitType     → precisa identificar storage-subsystem(11)
connUnitProduct  → modelo do array
connUnitSn       → serial
connUnitName     → nome complementar
```

Fluxo:

```text
Controller/IP A ─┐
                 ├─ mesmo connUnitId → 1 asset STORAGE
Controller/IP B ─┘
```

Se os IDs forem diferentes, o reconciliador não funde os registros pela semelhança de nome.

Quando `connUnitSn` é válido, o serial continua sendo identidade preferencial. Sem serial, um `connUnitId` válido e único pode formar a identidade `FA:<id>`.

O SNMP EngineID não é usado como identidade do array, porque pode ser específico da controladora.

O terminal mostra:

```text
Storage FA-MIB: id=<id> product=<modelo> serial=<serial> type=storage-subsystem(11)
```

Falha ou ausência de FA-MIB não libera criação automática: o item continua sujeito às regras conservadoras de REVIEW/BLOCKED.

## 4. DELEGATED / ownership Hypervisor — 1.10.10

Quando um IP descoberto pela rede já existe no NetBox vinculado a `virtualization.vminterface`:

```text
Network discovery
→ DELEGATED
→ NOOP
→ nenhuma criação de dcim.device
```

`DELEGATED` nunca é consumido pelo IMPORT Network.

## 5. VM candidata sem correspondência

Um MAC/asset claramente virtual, mas ainda sem vínculo a uma VM do NetBox, não é criado como Device físico:

```text
REVIEW
VIRTUAL_MACHINE_CANDIDATE_NO_VM_MATCH
```

## 6. Dell switches — 1.10.10

Hardware model/ENTITY-MIB tem prioridade sobre SSH/Linux/Web genérico.

Validados ao vivo:

```text
N2024      → NETWORK_SWITCH/HIGH
PCT7024    → NETWORK_SWITCH/HIGH
S4128F-ON  → NETWORK_SWITCH/HIGH
```

## 7. Diagnóstico Network

`netbox-discovery run` mostra:

```text
NETWORK PLAN DIAGNÓSTICO
NETWORK DELEGADOS AO HYPERVISOR
NETWORK NOVOS OBJETOS READY
NETWORK AJUSTES READY
NETWORK PENDÊNCIAS POR MOTIVO
NETWORK PENDÊNCIAS DETALHADAS
```

READY e pendências exibem evidência CLASSIFY, SNMP, asset class e, quando disponível, identidade FA-MIB.

Não faz parte da operação normal abrir PLAN com Python ad-hoc.

## 8. Identidade Network

Evidências fortes incluem:

- serial válido;
- MAC de gerenciamento autoritativo;
- LLDP chassis ID válido;
- IP associado de forma inequívoca;
- `connUnitId` válido para storage FibreAlliance.

Regras:

- MAC secundário não funde assets sozinho;
- nome sozinho não é identidade forte;
- dois controllers de storage só são unidos automaticamente com identidade de array compatível;
- IP de VM já pertencente a `virtualization.vminterface` não vira Device físico;
- ausência em coleta não autoriza DELETE.

## 9. Interfaces/IPs físicos

O Network cria intenção apenas para interfaces de gerenciamento/OOB observadas.

```text
Device físico
→ interface MGMT/OOB
→ IP
→ primary IPv4 quando aplicável
```

Não expande automaticamente todas as portas IF-MIB de um switch.

## 10. Segurança do APPLY Network

Antes de autorizar `--apply`, revisar o PLAN.

- somente `READY` escreve;
- `DELEGATED`, `REVIEW` e `BLOCKED` não escrevem;
- IMPORT recalcula PLAN antes da execução;
- falha em APPLY para no primeiro erro inesperado;
- não fazer correção em massa manual no NetBox para facilitar o discovery.

## 11. Hypervisor

```bash
netbox-discovery hypervisor configure
netbox-discovery hypervisor check
netbox-discovery hypervisor run
netbox-discovery hypervisor run --compare
netbox-discovery hypervisor run --apply
netbox-discovery hypervisor status
```

O fluxo multi-contexto está LIVE PASS para placement Tenant/Site, Cluster/Site, VM Parent/Site, APPLY/AUDIT e compare final.

Validação de referência:

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
1. confirmar processo/lock
2. não repetir --apply cegamente
3. usar compare/dry-run apropriado
4. revisar estado real
5. somente então retomar
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
