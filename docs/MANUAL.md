# Manual Operacional — netbox-discovery

**Produto:** netbox-discovery  
**Versão:** 1.10.10 — PRODUCT V1  
**Distribuição oficial:** `bkpcloud-app/netbox-discovery`  
**Canal de produção:** `stable`  
**NetBox BKPCLOUD:** `https://inventory.bkpcloud.app.br:8080`

> `CI PASS` não equivale a `LIVE PASS`. Estado real em `docs/HOMOLOGACAO.md`.

## 1. Pipeline Network

Dry-run:

```bash
netbox-discovery run
```

Fluxo:

```text
DISCOVER → CLASSIFY → RECONCILE → PLAN
```

Escrita explícita:

```bash
netbox-discovery run --apply
```

Fluxo:

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

## 3. DELEGATED / ownership Hypervisor — 1.10.10

Quando um IP descoberto pela rede já existe no NetBox vinculado a:

```text
virtualization.vminterface
```

o Network reconhece que o objeto é inventariado pelo pipeline Hypervisor:

```text
Network discovery
→ IP existente em virtualization.vminterface
→ DELEGATED
→ NOOP
→ nenhuma criação de dcim.device
```

O objetivo é impedir duplicação física de uma VM e remover falso `REVIEW`.

`DELEGATED` nunca é consumido pelo IMPORT Network porque apenas `READY` é elegível.

## 4. VM candidata sem correspondência

Um MAC/asset claramente virtual, mas ainda sem vínculo a uma VM do NetBox, não é criado como Device físico.

Resultado:

```text
REVIEW
VIRTUAL_MACHINE_CANDIDATE_NO_VM_MATCH
```

Isso permite investigar lacuna do inventário Hypervisor sem contaminar `dcim.device`.

## 5. Dell switches — 1.10.10

O hardware model/ENTITY-MIB tem prioridade sobre SSH/Linux/Web genérico.

Famílias reconhecidas incluem padrões Dell Networking como:

```text
Nxxxx
PCTxxxx / PowerConnect
Sxxxx...
Zxxxx...
```

Exemplos do ambiente real:

```text
N2024
PCT7024
S4128F-ON
```

Quando o modelo confirma a família, role interna:

```text
NETWORK_SWITCH
```

Target NetBox:

```text
NETWORK SWITCH
```

## 6. Diagnóstico Network

A partir da 1.10.9/1.10.10, `netbox-discovery run` mostra:

```text
NETWORK PLAN DIAGNÓSTICO
NETWORK DELEGADOS AO HYPERVISOR
NETWORK NOVOS OBJETOS READY
NETWORK AJUSTES READY
NETWORK PENDÊNCIAS POR MOTIVO
NETWORK PENDÊNCIAS DETALHADAS
```

READY e pendências exibem evidência CLASSIFY, SNMP e asset class quando disponível.

Não faz parte da operação normal abrir PLAN com Python ad-hoc.

## 7. Identidade Network

Evidências fortes:

- serial válido;
- MAC de gerenciamento autoritativo;
- LLDP chassis ID válido;
- IP associado de forma inequívoca.

Regras:

- MAC secundário não funde assets sozinho;
- nome sozinho não é identidade forte;
- IP de VM já pertencente a `virtualization.vminterface` não vira Device físico;
- ausência em uma coleta não autoriza DELETE.

## 8. Interfaces/IPs físicos

O Network cria intenção apenas para interfaces de gerenciamento/OOB observadas.

Não expande automaticamente todas as portas IF-MIB de um switch.

```text
Device físico
→ interface MGMT/OOB
→ IP
→ primary IPv4 quando aplicável
```

## 9. Segurança do APPLY Network

Antes de autorizar `--apply`, revisar o PLAN.

- somente `READY` escreve;
- `DELEGATED`, `REVIEW` e `BLOCKED` não escrevem;
- IMPORT recalcula PLAN antes da execução;
- falha em APPLY para no primeiro erro inesperado;
- não fazer correção em massa manual no NetBox para facilitar o discovery.

## 10. Hypervisor

Comandos:

```bash
netbox-discovery hypervisor configure
netbox-discovery hypervisor check
netbox-discovery hypervisor run
netbox-discovery hypervisor run --compare
netbox-discovery hypervisor run --apply
netbox-discovery hypervisor status
```

O fluxo multi-contexto está LIVE PASS na linha 1.10.8 para placement Tenant/Site, Cluster/Site, VM Parent/Site, APPLY/AUDIT e compare final.

Validação de referência:

```text
Objetos comparados: 282
OK: 282
MISMATCH: 0
MISSING: 0
AMBIGUOUS: 0
COMPARE STATUS: OK
```

## 11. Falha parcial

```text
1. confirmar processo/lock
2. não repetir --apply cegamente
3. usar compare/dry-run apropriado
4. revisar estado real
5. somente então retomar
```

## 12. Update

```bash
netbox-discovery update status
netbox-discovery update check
netbox-discovery update run
```

`stable` usa backup, validação, preservação de configuração e rollback de candidato inválido.

## 13. Schedulers

```bash
netbox-discovery scheduler status
netbox-discovery hypervisor scheduler status
netbox-discovery update scheduler status
```

Network e Hypervisor são opt-in.

## 14. Caminhos

```text
Aplicação:              /opt/netbox-discovery
Configuração principal: /opt/netbox-discovery/config.yml
Config Hypervisor:      /etc/netbox-discovery/hypervisors.json
Config por Site:        /opt/netbox-discovery/config/sites/
Relatórios:             /opt/netbox-discovery/reports
Backups:                /opt/netbox-discovery/backups
Lock global:            /var/lock/netbox-discovery-global.lock
```
