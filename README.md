# netbox-discovery

Produto BKPCLOUD para descoberta, reconciliação e inventário seguro de infraestrutura no NetBox.

**Versão atual:** 1.10.9 — PRODUCT V1  
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

Conectores Hypervisor:

- VMware vCenter/ESXi;
- Proxmox VE;
- Microsoft Hyper-V via WinRM/NTLM.

## Diagnóstico automático do PLAN de rede — 1.10.9

O primeiro dry-run real do DCM em 27/07/2026 encontrou 64 hosts ativos e reconciliou 60 assets, mas o PLAN terminou com:

```text
READY: 7
REVIEW: 47
BLOCKED: 6
```

A partir da 1.10.9, o próprio pipeline de rede mostra no terminal:

```text
NETWORK PLAN DIAGNÓSTICO
NETWORK NOVOS OBJETOS READY
NETWORK AJUSTES READY
NETWORK PENDÊNCIAS POR MOTIVO
NETWORK PENDÊNCIAS DETALHADAS
```

Para cada `REVIEW`/`BLOCKED`, o produto exibe:

- IP e nome desejado;
- role e confiança;
- motivos do PLAN;
- estado/motivo do matching;
- fabricante, modelo e serial;
- SNMP name/object-id/MAC de gerenciamento;
- evidência usada pelo CLASSIFY.

Objetivo: nenhuma operação normal deve exigir abrir JSON ou executar Python ad-hoc para descobrir por que um asset não está `READY`.

A 1.10.9 **não afrouxa as regras de segurança**. Ela torna as decisões existentes visíveis para orientar as próximas correções do classificador/reconciliador/planner.

## Política Network

```text
READY       → elegível para escrita somente com --apply
REVIEW      → não escreve
BLOCKED     → não escreve
run         → dry-run
run --apply → IMPORT apenas de READY + AUDIT
```

O PLAN bloqueia ou revisa, entre outros casos:

- confiança abaixo de HIGH;
- role UNKNOWN;
- OOB sem parent;
- conflito de serial/MAC/IP/nome;
- IP já pertencente a outro Device;
- IP associado a objeto externo, como interface de VM;
- drift de inventário que não deve ser sobrescrito cegamente.

## VM acompanha Tenant/Site do Host/Cluster — 1.10.8

Quando uma VM existente é reclassificada, o produto:

```text
revalida identidade forte da VM
→ relê Device/Cluster atual
→ confirma Parent no Site alvo
→ PATCH tenant + site juntos
→ ajusta Tenant dos IPs vinculados
```

Se o Parent estiver fora do Site alvo, `VM PARENT PREFLIGHT` bloqueia o lote.

## Migração coordenada de Cluster/Site — 1.10.7

Quando Cluster scoped e Devices-host precisam mudar juntos de Site:

```text
RECLASSIFY PREFLIGHT
→ valida todos os hosts do Cluster
→ remove temporariamente scope do Cluster
→ move Devices-host
→ reaplica scope no Site alvo
→ continua VMs
```

Sem DELETE automático.

## Compare Hypervisor — 1.10.7+

```bash
netbox-discovery hypervisor run --compare
```

Somente leitura. Compara Hosts, VMs, Clusters e Prefixes e retorna:

```text
OK
MISMATCH
MISSING
AMBIGUOUS
```

Após o APPLY 1.10.8 no DCM, a validação real fechou em:

```text
Objetos comparados: 282
OK: 282
MISMATCH: 0
MISSING: 0
AMBIGUOUS: 0
COMPARE STATUS: OK
```

## Preflight Hypervisor

Antes da primeira escrita:

```text
HYPERVISOR PREFLIGHT GLOBAL MULTI-CONTEXT
→ reconstruir PLAN atual
→ REVIEW/BLOCKED precisam ser 0
→ conjunto RECLASSIFY_SAFE precisa permanecer igual
→ revalidar identidade forte
→ só então escrever
```

## Identidade e reconciliação

Regras conservadoras:

- nome sozinho nunca autoriza migração/reclassificação forte;
- serial/UUID, IP e MAC são evidências fortes quando inequívocas;
- MAC de gerenciamento autoritativo é usado para reconciliação de rede;
- MACs auxiliares permanecem evidência, mas não fundem assets sozinhos;
- inventário não é apagado automaticamente por ausência em uma coleta.

## Estrutura Tenant/Site

O produto é genérico. Não existe hardcode de cliente.

```text
Tenant Group [opcional]
└── Tenant
    └── Site
```

## Segurança operacional

```text
Network run                 = dry-run
Network run --apply         = escrita de READY + AUDIT
Hypervisor run              = dry-run
Hypervisor run --compare    = read-only
Hypervisor run --apply      = escrita após preflight
REVIEW/BLOCKED              = não escrevem
DELETE Hypervisor           = nunca automático
```

Outras proteções:

- Network, Hypervisor, Compare e Update compartilham lock global;
- GET pode receber retry seguro;
- POST/PATCH não recebe retry cego;
- APPLY Hypervisor mantém journal;
- schedulers Network/Hypervisor são opt-in;
- auto-update `stable` usa backup, validação e rollback.

## Operação

```bash
netbox-discovery version
netbox-discovery status
netbox-discovery self-test
netbox-discovery health

netbox-discovery run
netbox-discovery run --apply
netbox-discovery scheduler status

netbox-discovery hypervisor check
netbox-discovery hypervisor run
netbox-discovery hypervisor run --compare
netbox-discovery hypervisor run --apply
netbox-discovery hypervisor status

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
