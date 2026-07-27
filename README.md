# netbox-discovery

Produto BKPCLOUD para descoberta, reconciliação e inventário seguro de infraestrutura no NetBox.

**Versão atual:** 1.10.2 — PRODUCT V1  
**Distribuição:** repositório público oficial `bkpcloud-app/netbox-discovery`  
**Canal padrão:** `stable`  
**NetBox BKPCLOUD:** `https://inventory.bkpcloud.app.br:8080`

> A documentação faz parte da release. Desde a 1.10.1 o self-test e o CI bloqueiam publicação quando a versão dos documentos obrigatórios diverge do `VERSION`.

## Pipelines independentes

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

Principais características:

- dry-run por padrão;
- identidade física por serial/MAC/IP e outras evidências;
- `management_mac` preferencialmente por IP → SNMP ifIndex → MAC;
- MACs secundários são evidência, não identidade forte isolada;
- classificação conservadora;
- `READY` pode escrever; `REVIEW` e `BLOCKED` não escrevem;
- preflight antes da primeira escrita;
- sem DELETE automático.

### Hypervisor

```text
netbox-discovery hypervisor configure
netbox-discovery hypervisor check
netbox-discovery hypervisor run
netbox-discovery hypervisor run --apply
netbox-discovery hypervisor status
```

Conectores:

- VMware vCenter ou ESXi standalone;
- Proxmox VE;
- Microsoft Hyper-V via WinRM/NTLM.

Cada source possui um modo de inventário:

```text
1 - single_site
    Todos os hosts/VMs pertencem ao Tenant/Site principal desta instalação.

2 - multi_site
    O hypervisor atende vários Sites do mesmo Tenant.

3 - multi_tenant
    O hypervisor atende vários Tenants e Sites.
```

Sources criadas antes da 1.10 permanecem em `single_site` por compatibilidade até serem editadas.

## Wizard multi-contexto — 1.10.2

No VMware, um ESXi pode expor vários vmkernel com o serviço `management` habilitado. Portanto **rede de management não é automaticamente sinônimo de Site**.

A partir da 1.10.2 o configurador:

1. conecta no hypervisor;
2. coleta Hosts, Datacenter, Cluster e vmkernel de gerenciamento;
3. agrupa as redes que pertencem claramente ao mesmo VMware Datacenter;
4. pergunta Tenant/Site **uma vez por grupo de Datacenter**;
5. grava internamente um mapping para cada CIDR daquele grupo;
6. se o Datacenter não representar um único Site, permite abrir o grupo e mapear rede por rede;
7. redes sem Datacenter único ou compartilhadas entre Datacenters continuam em revisão individual;
8. cria ou reutiliza Tenant Group, Tenant e Site quando autorizado.

Exemplo:

```text
Datacenter: DCM
Hosts: vm-ae01, vm-ae02, vm-ae03, vm-ae04
Redes VMware com serviço management (11):
10.1.1.0/24, ...

Usar um único Tenant/Site para todas estas redes deste Datacenter? [S/n]: S
Tenant Group: POLIMIX
Tenant: MIZU
Site: DCM
```

Isso reduz erro humano e evita pedir o mesmo Tenant/Site repetidamente quando vários vmkernel pertencem ao mesmo conjunto de Hosts.

No runtime:

- o Host é resolvido pelos mappings de rede de gerenciamento;
- a VM herda o contexto Tenant/Site do Host onde está rodando;
- IP da VM é fallback;
- sem resolução confiável o objeto vira `REVIEW`;
- serial/UUID já existente fora do contexto alvo vira `REVIEW` para reclassificação/migração, nunca CREATE duplicado;
- o pipeline Hypervisor não executa DELETE automático.

## Estrutura Tenant/Site

O produto é genérico. **Não existe hardcode de cliente como `MIZU → POLIMIX`.**

No `init`, a relação é informada na configuração:

```text
Tenant Group [opcional]
└── Tenant
    └── Site
```

No modo Hypervisor multi-contexto, os mappings podem apontar para vários Tenants/Sites. Vínculos conflitantes são bloqueados; não são sobrescritos silenciosamente.

## Segurança operacional

```text
run sem --apply             = leitura/PLAN, sem escrita de inventário
hypervisor run sem --apply  = leitura/PLAN, sem escrita de inventário
--apply                      = escrita somente de READY
REVIEW                       = não escreve
BLOCKED                      = não escreve
```

Outras proteções:

- Network, Hypervisor e Update compartilham lock global;
- GETs podem receber retry seguro; POST/PATCH não recebem retry cego;
- APPLY Hypervisor mantém journal das escritas concluídas;
- credenciais Hypervisor ficam em arquivo root-only `0600`;
- scheduler de Network e Hypervisor é opt-in;
- auto-update `stable` é habilitado por padrão com backup, validação e rollback;
- nenhuma rotina Hypervisor executa DELETE automático.

## Instalação em Proxy novo

Como `root`:

```bash
curl -fsSL https://raw.githubusercontent.com/bkpcloud-app/netbox-discovery/stable/install-from-github.sh | bash
```

O instalador preserva configuração existente durante upgrades e não habilita os schedulers Network/Hypervisor.

## Primeiro uso

```bash
netbox-discovery init
netbox-discovery check
```

Quando existir virtualização:

```bash
netbox-discovery hypervisor configure
netbox-discovery hypervisor check
netbox-discovery hypervisor run
# revisar PLAN antes de qualquer escrita
netbox-discovery hypervisor run --apply
```

Depois, se desejado:

```bash
netbox-discovery run
# revisar PLAN
netbox-discovery run --apply
```

Não existe `full-run`.

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

## Estado de homologação

**CI verde não significa automaticamente homologação ao vivo.**

A matriz oficial fica em `docs/HOMOLOGACAO.md`.

Na 1.10.2, o agrupamento por Datacenter foi criado após a primeira tentativa real no DCM mostrar 11 redes VMware `management` para apenas 4 Hosts. A lógica passou CI antes de promoção, mas só deve ser marcada `LIVE PASS` depois da repetição do wizard no DCM.

## Documentação obrigatória

- `README.md`
- `docs/MANUAL.md`
- `docs/COMANDOS-RAPIDOS.md`
- `docs/HOMOLOGACAO.md`
- `RELEASE-NOTES.md`
- `SECURITY.md`
