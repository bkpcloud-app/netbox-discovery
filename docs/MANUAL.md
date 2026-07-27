# Manual Operacional — netbox-discovery

**Produto:** netbox-discovery  
**Versão:** 1.10.9 — PRODUCT V1  
**Distribuição oficial:** `bkpcloud-app/netbox-discovery`  
**Canal de produção:** `stable`  
**NetBox BKPCLOUD:** `https://inventory.bkpcloud.app.br:8080`

> O estado de homologação real fica em `docs/HOMOLOGACAO.md`. CI verde não equivale a validação ao vivo.

---

## 1. Visão geral

O `netbox-discovery` automatiza descoberta, classificação, reconciliação, planejamento, importação segura e auditoria de inventário no NetBox.

### Rede

```text
netbox-discovery run
DISCOVER → CLASSIFY → RECONCILE → PLAN
```

Com escrita:

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

---

## 2. Decisões do PLAN

| Decisão | Significado | Escrita |
|---|---|---|
| `READY` | evidência suficiente | somente com `--apply` |
| `REVIEW` | precisa revisão | não |
| `BLOCKED` | conflito forte | não |

Ações:

| Ação | Significado |
|---|---|
| `CREATE` | objeto novo |
| `UPDATE_SAFE` | ajuste seguro |
| `RECLASSIFY_SAFE` | mesmo objeto em contexto incorreto, identidade forte |
| `NOOP` | nenhuma mudança necessária |
| `CONFLICT` | conflito; não escreve |

---

## 3. Network — diagnóstico automático do PLAN — 1.10.9

O primeiro dry-run real do DCM em 27/07/2026 encontrou:

```text
Hosts ativos: 64
Assets reconciliados: 60
READY: 7
REVIEW: 47
BLOCKED: 6
```

A 1.10.9 transforma essa análise em saída operacional do próprio produto.

Ao executar:

```bash
netbox-discovery run
```

o terminal passa a mostrar:

```text
===== NETWORK PLAN DIAGNÓSTICO =====
READY/CREATE: N
READY/UPDATE_SAFE: N
REVIEW: N
BLOCKED: N
NetBox write: NÃO

===== NETWORK NOVOS OBJETOS READY =====
...

===== NETWORK AJUSTES READY =====
...

===== NETWORK PENDÊNCIAS POR MOTIVO =====
CONFIDENCE_LOW: N
UNKNOWN_ROLE: N
IDENTITY_CONFLICT: N
IP_ASSIGNED_TO_EXTERNAL_OBJECT:...: N
...

===== NETWORK PENDÊNCIAS DETALHADAS =====
[1/N] REVIEW/BLOCKED | IP | nome | role | confidence | score
  Motivos: ...
  Match: ...
  Fabricante/Modelo/Serial: ...
  SNMP: name=... object_id=... mgmt_mac=...
  Evidência CLASSIFY: ...
```

Objetivo: não abrir JSON nem usar Python ad-hoc para entender por que um asset não está `READY`.

A 1.10.9 é uma release de **observabilidade/diagnóstico** do PLAN. Ela não reduz as travas existentes.

---

## 4. Network — política de classificação e segurança

O CLASSIFY atribui role e score. Confiança:

```text
score >= 85 → HIGH
score >= 55 → MEDIUM
score >= 30 → LOW
abaixo      → NONE
```

No PLAN:

- confiança diferente de `HIGH` → `REVIEW`;
- `UNKNOWN` → `REVIEW`;
- OOB sem parent → `REVIEW`;
- conflito de identidade → `BLOCKED`;
- IP pertencente a outro Device → `BLOCKED`;
- IP associado a objeto externo, como `virtualization.vminterface` → `REVIEW`;
- drift de serial/model/role/platform é reportado e não sobrescrito cegamente.

Apenas `READY` entra no IMPORT.

---

## 5. Network — identidade e reconciliação

O reconciliador usa evidência forte para decidir se dois registros representam o mesmo asset.

Prioridades:

- serial válido;
- MAC de gerenciamento autoritativo;
- LLDP chassis ID válido;
- tabela SNMP de IP combinada com identidade coerente.

A partir da linha V3 do reconciliador, MACs secundários/interface continuam como evidência, mas **não podem fundir dois assets independentes sozinhos**.

Regras importantes:

- um FortiGate com múltiplas interfaces/IPs deve continuar sendo um único firewall quando a identidade forte confirma isso;
- redes industriais devem permanecer classificadas no contexto OT/Industrial definido para o Site;
- nome genérico repetido não é identidade forte;
- ausência em uma coleta não autoriza DELETE automático.

---

## 6. Network — interfaces e IPs

O PLAN cria intenção apenas para interfaces de gerenciamento/OOB observadas por IP.

Ele não cria automaticamente todas as portas de um switch só porque IF-MIB expôs centenas de interfaces.

Fluxo esperado:

```text
asset físico
→ interface MGMT/OOB
→ IP observado
→ primary IPv4 quando aplicável
```

MAC da interface de gerenciamento deve vir da relação SNMP IP ↔ ifIndex quando disponível; L2 observado é fallback.

---

## 7. Network — APPLY

Dry-run:

```bash
netbox-discovery run
```

Escrita:

```bash
netbox-discovery run --apply
```

Regras:

- somente `READY` escreve;
- `REVIEW` não escreve;
- `BLOCKED` não escreve;
- IMPORT deve ser idempotente;
- AUDIT é read-only;
- nenhuma correção em massa manual no NetBox faz parte do fluxo normal.

Durante desenvolvimento/homologação, o scheduler Network deve permanecer sem APPLY automático.

---

## 8. Hypervisor — preflight global — 1.10.6+

Antes da primeira escrita Hypervisor:

```text
DISCOVER
→ PLAN
→ autorização --apply
→ PREFLIGHT GLOBAL
→ RECLASSIFY PREFLIGHT
→ escrita READY
→ AUDIT
```

O preflight reconstrói o PLAN, exige `REVIEW/BLOCKED=0`, confirma o conjunto `RECLASSIFY_SAFE` e revalida identidades fortes.

---

## 9. Hypervisor — Cluster/Site — 1.10.7

Quando Cluster scoped e Hosts mudam juntos de Site:

```text
RECLASSIFY PREFLIGHT
→ remove temporariamente scope do Cluster
→ move Hosts
→ reaplica scope no Site alvo
→ continua VMs
```

Sem DELETE automático.

---

## 10. Hypervisor — VM/Parent — 1.10.8

Quando uma VM existente precisa acompanhar o Host/Cluster:

```text
revalida identidade da VM
→ relê Device/Cluster
→ confirma Parent no Site alvo
→ VM PARENT PREFLIGHT: OK
→ PATCH tenant + site juntos
→ ajusta Tenant dos IPs
```

---

## 11. Hypervisor — compare

```bash
netbox-discovery hypervisor run --compare
```

Somente leitura.

Estados:

```text
OK
MISMATCH
MISSING
AMBIGUOUS
```

Última validação completa do ambiente de referência em 27/07/2026:

```text
Objetos comparados: 282
OK: 282
MISMATCH: 0
MISSING: 0
AMBIGUOUS: 0
COMPARE STATUS: OK
```

---

## 12. Falha parcial e retomada

Depois de queda de SSH ou erro após escritas:

```text
1. confirmar processo/lock
2. não repetir --apply cegamente
3. usar compare/dry-run adequado
4. revisar estado real
5. somente então retomar
```

Não existe rollback cego.

---

## 13. Atualização

```bash
netbox-discovery update status
netbox-discovery update check
netbox-discovery update run
```

O updater `stable`:

- cria backup;
- valida candidato;
- preserva configuração;
- executa rollback em falha de validação;
- bloqueia downgrade;
- usa quarentena para versão quebrada.

---

## 14. Schedulers

```bash
netbox-discovery scheduler status
netbox-discovery hypervisor scheduler status
netbox-discovery update scheduler status
```

Network e Hypervisor são opt-in.

---

## 15. Saúde

```bash
netbox-discovery version
netbox-discovery status
netbox-discovery self-test
netbox-discovery health
netbox-discovery health --json
```

---

## 16. Caminhos

```text
Aplicação:              /opt/netbox-discovery
Configuração principal: /opt/netbox-discovery/config.yml
Config Hypervisor:      /etc/netbox-discovery/hypervisors.json
Config por Site:        /opt/netbox-discovery/config/sites/
Relatórios:             /opt/netbox-discovery/reports
Backups:                /opt/netbox-discovery/backups
Lock global:            /var/lock/netbox-discovery-global.lock
```

---

## 17. Homologação

A matriz oficial fica em:

```text
docs/HOMOLOGACAO.md
```

`CI PASS` não significa `LIVE PASS`.
