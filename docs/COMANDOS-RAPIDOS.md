# netbox-discovery 1.10.2 — Comandos rápidos

## Versão e saúde

```bash
netbox-discovery version
netbox-discovery status
netbox-discovery self-test
netbox-discovery health
netbox-discovery health --json
```

## Instalar em Proxy novo

```bash
curl -fsSL https://raw.githubusercontent.com/bkpcloud-app/netbox-discovery/stable/install-from-github.sh | bash
```

## Atualizar

```bash
netbox-discovery update status
netbox-discovery update check
netbox-discovery update run
```

## Configuração principal

```bash
netbox-discovery init
netbox-discovery check
```

NetBox fixo:

```text
https://inventory.bkpcloud.app.br:8080
```

## Hypervisor — configurar

```bash
netbox-discovery hypervisor configure
```

Modo da source:

```text
1 - single_site
2 - multi_site
3 - multi_tenant
```

### VMware multi-contexto — 1.10.2

O wizard não pergunta mais Tenant/Site cegamente para cada vmkernel `management`.

Ele primeiro agrupa por VMware Datacenter quando a associação é inequívoca:

```text
Datacenter: DCM
Hosts: ESX01, ESX02, ESX03, ESX04
Redes VMware com serviço management (11): ...
Usar um único Tenant/Site para todas estas redes deste Datacenter? [S/n]:
```

- `S` → pergunta Tenant/Site uma vez e aplica aos CIDRs daquele grupo;
- `N` → abre revisão detalhada por rede;
- rede sem Datacenter único continua individual;
- sources antigas permanecem `single_site` até edição explícita.

## Hypervisor — validar e dry-run

```bash
netbox-discovery hypervisor check
netbox-discovery hypervisor run
```

Sem `--apply`: **não escreve inventário**.

Revise:

```text
Contextos Tenant/Site
READY
REVIEW
BLOCKED
UPDATE_SAFE
alvo=Tenant/Site
```

## Hypervisor — APPLY

Somente após dry-run revisado:

```bash
netbox-discovery hypervisor run --apply
```

Nunca repetir APPLY cegamente quando o AUDIT deixar `REVIEW` ou `UPDATE_SAFE` residual.

## Hypervisor — scheduler

```bash
netbox-discovery hypervisor scheduler status
netbox-discovery hypervisor scheduler enable
netbox-discovery hypervisor scheduler disable
```

Durante homologação, mantenha desabilitado.

## Rede — dry-run

```bash
netbox-discovery run
```

## Rede — APPLY

```bash
netbox-discovery run --apply
```

## Rede — scheduler

```bash
netbox-discovery scheduler status
netbox-discovery scheduler enable
netbox-discovery scheduler disable
```

## Política

```text
READY   → elegível para escrita somente com --apply
REVIEW  → não escreve
BLOCKED → não escreve
NOOP    → preserva
```

Hypervisor não executa DELETE automático.

## Auto-update

```bash
netbox-discovery update scheduler status
netbox-discovery update scheduler enable
netbox-discovery update scheduler disable
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
Lock global:            /var/lock/netbox-discovery-global.lock
```

## Homologação

```text
docs/HOMOLOGACAO.md
```

CI verde ≠ automaticamente homologado ao vivo.

## DCM — sequência atual

```text
1. atualizar para a stable atual
2. editar uma source por vez
3. escolher multi_tenant quando o manager atender vários Tenants/Sites
4. revisar grupos de Datacenter e redes management
5. confirmar Tenant/Site
6. repetir na segunda source
7. hypervisor check
8. hypervisor run SEM --apply
9. revisar redistribuição dos objetos já existentes
10. só então considerar APPLY
```
