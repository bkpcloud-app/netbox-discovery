# netbox-discovery

Produto BKPCLOUD para descoberta, reconciliação e inventário seguro de infraestrutura no NetBox.

**Versão atual:** 1.10.13 — PRODUCT V1  
**Distribuição:** repositório público oficial `bkpcloud-app/netbox-discovery`  
**Canal padrão:** `stable`  
**NetBox BKPCLOUD:** `https://inventory.bkpcloud.app.br:8080`

> A documentação faz parte da release. O self-test e o CI bloqueiam publicação quando os documentos obrigatórios divergem do `VERSION`.

## Pipelines

### Rede

```text
netbox-discovery run
DISCOVER → CLASSIFY → RECONCILE → PLAN
```

Com escrita explícita:

```text
netbox-discovery run --apply
DISCOVER → CLASSIFY → RECONCILE → PLAN → IMPORT → AUDIT
```

### Hypervisor

```text
netbox-discovery hypervisor configure
netbox-discovery hypervisor check
netbox-discovery hypervisor run
netbox-discovery hypervisor run --compare
netbox-discovery hypervisor run --apply
netbox-discovery hypervisor status
```

Conectores: VMware, Proxmox VE e Microsoft Hyper-V.

## Precedência de ownership por IP — 1.10.13

O dry-run live da 1.10.12 comprovou o anti-flap do `SRV-AE11`, mas revelou uma regressão: assets que o planner base já havia marcado como `DELEGATED` porque o IP pertence a `virtualization.vminterface` podiam ser rebaixados para `REVIEW` pela nova correlação por nome.

A 1.10.13 define a precedência correta:

```text
IP já pertence a virtualization.vminterface
→ DELEGATED/NOOP
→ ownership Hypervisor já provado
→ correlação por nome não pode rebaixar para REVIEW
```

A correlação por nome continua sendo usada quando o ownership por IP ainda não está provado.

O conflito físico/VM continua protegido:

```text
Device físico existente + identidade VMware + VM única por nome
→ BLOCKED/CONFLICT
→ PHYSICAL_DEVICE_CONFLICT_WITH_HYPERVISOR_VM:<id>
```

## Identidade anti-flap — 1.10.12+

O primeiro APPLY Network real mostrou que uma evidência forte pode desaparecer em uma coleta posterior sem que o equipamento tenha mudado. Exemplos reais:

```text
SRV-AE11
coleta A → MAC VMware 00:50:56:... → VIRTUAL_MACHINE_CANDIDATE
coleta B → MAC não observado         → não pode virar Device físico

ME4024
coleta A → FA-MIB/serial do array
coleta B → FA-MIB transitório ausente → identidade do array não pode sumir
```

A 1.10.12 mantém por até 48 horas apenas evidências fortes já observadas no mesmo Site/IP:

```text
VMware OUI / VIRTUAL_MACHINE_CANDIDATE
FA-MIB storage-subsystem + serial/connUnitId
```

A memória é conservadora:

- identidade física forte atual vence evidência VMware antiga;
- serial/FA atual diferente gera conflito, não sobrescrita silenciosa;
- `connUnitId` composto só de zeros é tratado como ausente;
- serial válido de storage continua sendo identidade forte;
- o histórico não copia MAC antigo para criar interface/MAC no NetBox.

## Ownership Network ↔ Hypervisor por nome único — 1.10.12+

Quando há evidência VMware e um nome único corresponde a uma VM existente:

```text
VM candidate + VM única com mesmo nome
→ DELEGATED
→ NOOP
→ ownership Hypervisor
```

Se já existir um `dcim.device` físico para esse mesmo asset:

```text
→ BLOCKED
→ PHYSICAL_DEVICE_CONFLICT_WITH_HYPERVISOR_VM
→ nenhuma escrita automática
```

## PowerVault / storage FibreAlliance — 1.10.11+

Storages com duas controladoras não são fundidos apenas por `sysName`.

O discovery consulta:

```text
.1.3.6.1.3.94.1.6.1
```

E usa:

```text
connUnitId       → identidade persistente quando válido
connUnitType     → storage-subsystem(11)
connUnitProduct  → modelo
connUnitSn       → serial
```

A 1.10.12+ faz até três tentativas read-only da árvore FA-MIB para reduzir perda transitória de identidade.

## Ownership por IP — 1.10.10+

Quando um IP descoberto pelo Network já pertence no NetBox a `virtualization.vminterface`:

```text
→ DELEGATED
→ NOOP
→ owner Hypervisor
→ nenhuma escrita Network
```

Na 1.10.13 essa decisão passa a ser explicitamente prioritária sobre a ponte de nome.

## Dell Networking — 1.10.10+

Modelos físicos Dell identificados por ENTITY-MIB/modelo de hardware têm prioridade sobre Linux/SSH/Web genérico.

Validados no DCM:

```text
N2024      → NETWORK_SWITCH / HIGH
PCT7024    → NETWORK_SWITCH / HIGH
S4128F-ON  → NETWORK_SWITCH / HIGH
```

## Diagnóstico automático do PLAN Network

`netbox-discovery run` mostra:

```text
NETWORK PLAN DIAGNÓSTICO
NETWORK DELEGADOS AO HYPERVISOR
NETWORK NOVOS OBJETOS READY
NETWORK AJUSTES READY
NETWORK PENDÊNCIAS POR MOTIVO
NETWORK PENDÊNCIAS DETALHADAS
```

## Política Network

```text
READY       → elegível para escrita somente com --apply
DELEGATED   → pertencente a outro pipeline; NOOP no Network
REVIEW      → não escreve
BLOCKED     → não escreve
run         → dry-run
run --apply → IMPORT apenas de READY + AUDIT
```

O importer recalcula o PLAN com o planner atual antes de qualquer APPLY.

## Hypervisor LIVE PASS — 1.10.8+

Validação final de referência:

```text
Objetos comparados: 282
OK: 282
MISMATCH: 0
MISSING: 0
AMBIGUOUS: 0
COMPARE STATUS: OK
```

## Segurança operacional

```text
Network run                 = dry-run
Network run --apply         = escrita de READY + AUDIT
DELEGATED                   = nunca escreve no Network
Hypervisor run              = dry-run
Hypervisor run --compare    = read-only
Hypervisor run --apply      = escrita após preflight
REVIEW/BLOCKED              = não escrevem
DELETE Hypervisor           = nunca automático
```

## Operação

```bash
netbox-discovery version
netbox-discovery status
netbox-discovery self-test
netbox-discovery health

netbox-discovery run
netbox-discovery run --apply

netbox-discovery hypervisor check
netbox-discovery hypervisor run
netbox-discovery hypervisor run --compare
netbox-discovery hypervisor run --apply

netbox-discovery update status
netbox-discovery update check
netbox-discovery update run
```

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
