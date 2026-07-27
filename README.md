# netbox-discovery

Produto BKPCLOUD para descoberta, reconciliação e inventário seguro de infraestrutura no NetBox.

**Versão atual:** 1.10.4 — PRODUCT V1  
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

## Reclassificação segura multi-contexto — 1.10.4

A 1.10.4 adiciona uma etapa explícita de reclassificação para corrigir objetos que já existem no NetBox, mas foram gravados anteriormente no Tenant/Site errado.

O PLAN pode produzir:

```text
READY / RECLASSIFY_SAFE
```

Essa ação só é criada quando o produto reencontra **a mesma identidade forte** no NetBox. As evidências aceitas são serial/UUID e/ou vínculo inequívoco de IP/MAC ao mesmo objeto.

Exemplo:

```text
Device já existente: MIZU/DCM
Rede autoritativa atual: 10.2.1.0/24
Mapping atual: MIZU/FBA

PLAN:
READY / RECLASSIFY_SAFE
MIZU/DCM → MIZU/FBA
```

Regras de segurança:

- identidade global ambígua nunca vira migração automática; fica `REVIEW`;
- serial e IP/MAC apontando para objetos diferentes ficam `REVIEW`;
- a reclassificação preserva o mesmo ID do objeto, em vez de criar duplicata;
- Host pode ter Tenant/Site corrigidos;
- VM pode ter Tenant corrigido e continua vinculada ao Host/Cluster autoritativo;
- IPs já pertencentes ao objeto acompanham a correção de Tenant;
- Cluster/Prefix podem ser reclassificados somente quando a correspondência global é única e segura;
- não existe DELETE automático.

O comando continua dry-run por padrão:

```bash
netbox-discovery hypervisor run
```

A escrita real continua exigindo:

```bash
netbox-discovery hypervisor run --apply
```

A funcionalidade `RECLASSIFY_SAFE` da 1.10.4 deve permanecer **NOT LIVE** até passar CI e ser validada em dry-run e APPLY controlado no ambiente real. Consulte `docs/HOMOLOGACAO.md`.

## Delta de inventário Hypervisor — 1.10.4

O discovery compara a coleta atual com o snapshot multi-contexto anterior.

Quando uma VM existia na coleta anterior e não aparece mais na atual, a saída informa:

```text
HYPERVISOR INVENTORY CHANGE
REMOVED/REVIEW
DELETE automático: NÃO
```

A ausência vira `REVIEW/NOOP`. O produto **não apaga a VM do NetBox automaticamente**.

## Rede de gerenciamento autoritativa VMware — 1.10.3

Um ESXi pode ter vários vmkernel com o serviço VMware `management` habilitado. Isso **não significa** que todas essas redes são redes de gerenciamento autoritativas do Host nem que devem virar mappings Tenant/Site.

A partir da 1.10.3 o resolver separa:

```text
vmkernel com serviço management
            ≠
rede autoritativa usada para posicionar o ESXi no Site
```

Para VMware, a seleção é conservadora:

1. prefere o vmkernel cujo IP corresponde à resolução do FQDN/nome do ESXi;
2. se não houver essa evidência, prefere `vmk0` quando ela está marcada como management;
3. se restar somente uma rede management candidata, usa essa rede;
4. se houver várias candidatas sem evidência forte, não adivinha: o Host fica sem resolução de contexto e deve aparecer em `REVIEW`.

As demais interfaces/vmkernel continuam sendo evidência de inventário. Elas apenas deixam de decidir Tenant/Site.

Caso real que originou a correção no DCM:

```text
4 Hosts ESXi
Datacenter: DCM
management service observado em 11 redes
rede de gestão conhecida dos Hosts: 10.1.1.0/24
redes auxiliares observadas: 192.168.140/141/142/143/160/161/180/181/190/191
```

A 1.10.2 agrupava as 11 redes por Datacenter. A 1.10.3 corrige a causa: somente a rede autoritativa participa do mapping de Site.

## Wizard multi-contexto

O configurador:

1. conecta no hypervisor;
2. coleta Hosts, Datacenter, Cluster e interfaces;
3. seleciona a rede autoritativa de gerenciamento de cada Host;
4. agrupa redes autoritativas que pertencem claramente ao mesmo VMware Datacenter;
5. pergunta Tenant/Site uma vez por grupo de Datacenter;
6. grava internamente um mapping para cada CIDR autoritativo daquele grupo;
7. se um Datacenter realmente tiver várias redes de gestão válidas e não representar um único Site, permite abrir o grupo e mapear por rede;
8. cria ou reutiliza Tenant Group, Tenant e Site quando autorizado.

No runtime:

- o Host é resolvido somente pela rede de gerenciamento autoritativa;
- a VM herda o contexto Tenant/Site do Host onde está rodando;
- IP da VM é fallback;
- sem resolução confiável o objeto vira `REVIEW`;
- identidade forte já existente fora do contexto alvo pode virar `RECLASSIFY_SAFE` na 1.10.4, somente quando inequívoca;
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

A seleção autoritativa VMware 1.10.3 possui evidência `LIVE PASS` no DCM. O resolver multi-contexto das duas sources e o dry-run real também já possuem evidência ao vivo. A nova reclassificação automática 1.10.4 permanece separada e só pode ser promovida após CI e validação real específica.

## Documentação obrigatória

- `README.md`
- `docs/MANUAL.md`
- `docs/COMANDOS-RAPIDOS.md`
- `docs/HOMOLOGACAO.md`
- `RELEASE-NOTES.md`
- `SECURITY.md`
