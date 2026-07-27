# netbox-discovery

Produto BKPCLOUD para descoberta, reconciliação e inventário seguro de infraestrutura no NetBox.

**Versão atual:** 1.10.7 — PRODUCT V1  
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

Conectores:

- VMware vCenter ou ESXi standalone;
- Proxmox VE;
- Microsoft Hyper-V via WinRM/NTLM.

Modos de source:

```text
single_site
multi_site
multi_tenant
```

## Migração coordenada de Cluster/Site — 1.10.7

A 1.10.7 corrige a migração de clusters NetBox já existentes quando o Cluster e seus Devices-host precisam sair de um Site antigo e ir para outro Site.

O NetBox exige que um Device host pertença ao mesmo Site do Cluster quando o Cluster possui `scope` de Site. Portanto não é seguro mover simplesmente o Cluster antes dos Hosts nem mover os Hosts enquanto o Cluster ainda está preso ao Site antigo.

A sequência 1.10.7 é:

```text
RECLASSIFY PREFLIGHT
→ valida todos os hosts membros do Cluster
→ remove temporariamente o scope opcional do Cluster
→ move os Devices-host para o Site alvo
→ reaplica o scope do Cluster no Site alvo
→ continua a reconciliação de VMs
```

Proteções:

- todos os hosts do Cluster que estão fora do Site alvo precisam estar cobertos por `HOST / RECLASSIFY_SAFE`;
- host com rack/location não muda de Site automaticamente;
- se a composição do Cluster mudar, o preflight bloqueia;
- falha parcial mantém journal e pode ser reavaliada antes de nova tentativa;
- nenhuma rotina executa DELETE automático.

Essa correção foi adicionada após o APPLY real de 27/07/2026 parar corretamente no NetBox com HTTP 400 ao tentar mover o Cluster `FBA` enquanto dois Devices-host ainda estavam em `DCM`.

## Comparação NetBox × Hypervisor — 1.10.7

O modo oficial read-only:

```bash
netbox-discovery hypervisor run --compare
```

coleta o estado atual das sources, lê o NetBox e compara Tenant/Site atual versus Tenant/Site esperado pelos mappings.

A saída mostra:

```text
OK
MISMATCH
MISSING
AMBIGUOUS
```

para Hosts, VMs, Clusters e Prefixes, além de listar todas as divergências no terminal.

Regras:

- não executa POST/PATCH;
- usa o lock global e não roda durante APPLY/Update;
- VMs associadas a Cluster usam o scope do Cluster como Site efetivo;
- VMs associadas diretamente a Device usam o Site do Device;
- gera relatório `MULTI-hypervisor-compare-*.json`;
- `NetBox write: NÃO`.

## Preflight global antes de qualquer escrita — 1.10.6+

A partir da 1.10.6, `hypervisor run --apply` não inicia nenhuma escrita logo após o PLAN apresentado ao operador.

Antes do primeiro POST/PATCH, o produto obrigatoriamente:

```text
1. reconstrói o PLAN multi-contexto usando o estado atual do NetBox;
2. aborta se surgir qualquer REVIEW ou BLOCKED;
3. exige que o conjunto RECLASSIFY_SAFE permaneça idêntico ao dry-run;
4. revalida a identidade forte de cada objeto imediatamente antes da reclassificação;
5. somente depois libera RECLASSIFY_SAFE / CREATE / UPDATE_SAFE.
```

A saída esperada antes da primeira escrita é:

```text
HYPERVISOR PREFLIGHT GLOBAL MULTI-CONTEXT
PREFLIGHT GLOBAL: OK
NetBox write até aqui: NÃO
```

E, para contextos com migração:

```text
RECLASSIFY PREFLIGHT Tenant/Site: OK
NetBox write: NÃO
```

Se identidade, `existing_id`, Tenant/Site alvo ou conjunto de migrações mudar entre dry-run e APPLY, o processo aborta antes da primeira escrita.

## Diagnóstico automático do PLAN — 1.10.5+

O operador **não precisa abrir JSON nem executar Python auxiliar** para descobrir o que o Hypervisor pretende criar.

O próprio:

```bash
netbox-discovery hypervisor run
```

lista automaticamente no terminal:

```text
HYPERVISOR NOVOS OBJETOS READY
READY / CREATE

HYPERVISOR AJUSTES/MIGRAÇÕES SEGURAS PENDENTES
READY / UPDATE_SAFE
READY / RECLASSIFY_SAFE

HYPERVISOR PENDÊNCIAS DO PLAN
REVIEW
BLOCKED
```

E fecha com um resumo de escrita do dry-run:

```text
CREATE READY: N
UPDATE_SAFE/RECLASSIFY_SAFE READY: N
REVIEW/BLOCKED: N
NetBox write: NÃO
```

A análise é automática. A única ação manual obrigatória continua sendo a autorização de escrita real:

```bash
netbox-discovery hypervisor run --apply
```

## Reclassificação segura multi-contexto — 1.10.4+

O PLAN pode produzir:

```text
READY / RECLASSIFY_SAFE
```

quando o produto reencontra a mesma identidade forte no NetBox fora do Tenant/Site autoritativo.

Evidências fortes:

- serial/UUID único;
- IP inequivocamente vinculado ao mesmo objeto;
- MAC inequivocamente vinculado ao mesmo objeto;
- combinação coerente dessas evidências.

Proteções:

- nome sozinho nunca autoriza migração;
- identidade global ambígua vira `REVIEW`;
- serial e IP/MAC apontando para objetos diferentes vira `REVIEW`;
- preserva o mesmo ID do objeto;
- Host pode ter Tenant/Site corrigidos;
- VM pode ter Tenant corrigido mantendo o posicionamento físico por Host/Cluster;
- IPs vinculados acompanham o Tenant quando necessário;
- não existe DELETE automático.

## Delta de inventário Hypervisor — 1.10.4+

O discovery compara a coleta atual com o snapshot multi-contexto anterior.

VM presente anteriormente e ausente agora:

```text
HYPERVISOR INVENTORY CHANGE
REMOVED/REVIEW
REVIEW / NOOP
DELETE automático: NÃO
```

Ausência nunca vira exclusão automática.

## Rede de gerenciamento autoritativa VMware — 1.10.3+

Um ESXi pode ter vários vmkernel com o serviço VMware `management` habilitado. Isso não significa que todas essas redes devam decidir Tenant/Site.

Seleção conservadora:

1. IP de vmkernel que corresponde ao FQDN/nome do ESXi;
2. `vmk0` marcada como management;
3. única rede management candidata;
4. múltiplas candidatas sem evidência forte → sem resolução automática / `REVIEW`.

As demais interfaces continuam no inventário, mas não posicionam o Host.

## Resolver multi-contexto

Host:

```text
rede de gerenciamento autoritativa
→ mapping mais específico
→ Tenant/Site
```

VM:

```text
VM
→ Host onde está executando
→ Tenant/Site do Host
```

IP da VM é fallback. Sem evidência confiável, o objeto vira `REVIEW`.

## Estrutura Tenant/Site

O produto é genérico. Não existe hardcode de cliente.

```text
Tenant Group [opcional]
└── Tenant
    └── Site
```

## Segurança operacional

```text
run sem --apply             = dry-run
hypervisor run sem --apply  = dry-run
hypervisor run --compare    = comparação read-only
--apply                      = escrita somente de READY após preflight global
REVIEW                       = não escreve
BLOCKED                      = não escreve
DELETE Hypervisor            = nunca automático
```

Outras proteções:

- Network, Hypervisor e Update compartilham lock global;
- GETs podem receber retry seguro;
- POST/PATCH não recebem retry cego;
- APPLY Hypervisor mantém journal das escritas;
- credenciais Hypervisor ficam em arquivo root-only `0600`;
- schedulers Network/Hypervisor são opt-in;
- auto-update `stable` usa backup, validação e rollback.

## Instalação

```bash
curl -fsSL https://raw.githubusercontent.com/bkpcloud-app/netbox-discovery/stable/install-from-github.sh | bash
```

## Operação

```bash
netbox-discovery version
netbox-discovery status
netbox-discovery self-test
netbox-discovery health
netbox-discovery health --json

netbox-discovery update status
netbox-discovery update check
netbox-discovery update run

netbox-discovery hypervisor check
netbox-discovery hypervisor run
netbox-discovery hypervisor run --compare
netbox-discovery hypervisor status
```

## Caminhos

```text
Aplicação:              /opt/netbox-discovery
Configuração principal: /opt/netbox-discovery/config.yml
Config Hypervisor:      /etc/netbox-discovery/hypervisors.json
Dependências isoladas:  /opt/netbox-discovery/vendor
Config por Site:        /opt/netbox-discovery/config/sites/
Relatórios:             /opt/netbox-discovery/reports
Backups:                /opt/netbox-discovery/backups
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
