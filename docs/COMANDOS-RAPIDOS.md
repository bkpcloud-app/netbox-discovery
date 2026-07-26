# netbox-discovery V1.8.0 — Comandos rápidos

## Instalar/atualizar

```bash
curl -fsSL https://raw.githubusercontent.com/bkpcloud-app/netbox-discovery/main/install-from-github.sh | bash
```

## Configuração principal

```bash
netbox-discovery init
netbox-discovery check
```

NetBox fixo do produto:

```text
https://inventory.bkpcloud.app.br:8080
```

## Hypervisor — executar primeiro quando existir virtualização

```bash
netbox-discovery hypervisor configure
netbox-discovery hypervisor check
netbox-discovery hypervisor run
```

Sem `--apply`: somente coleta e PLAN.

Após revisar:

```bash
netbox-discovery hypervisor run --apply
netbox-discovery hypervisor status
```

Plataformas: VMware vCenter/ESXi, Proxmox VE e Hyper-V WinRM/NTLM.

Scheduler independente:

```bash
netbox-discovery hypervisor scheduler enable
netbox-discovery hypervisor scheduler status
netbox-discovery hypervisor scheduler disable
```

## Rede — permanece como antes

```bash
netbox-discovery run
```

Após revisar o PLAN:

```bash
netbox-discovery run --apply
netbox-discovery status
```

Scheduler independente:

```bash
netbox-discovery scheduler enable
netbox-discovery scheduler status
netbox-discovery scheduler disable
```

## Política

```text
READY   → elegível para escrita
REVIEW  → não escreve
BLOCKED → não escreve
NOOP    → preserva
```

Não existe `full-run`. Os pipelines são deliberadamente separados.
Recomendação: agenda Hypervisor primeiro; agenda de Rede depois.

## Caminhos

```text
Aplicação:             /opt/netbox-discovery
Configuração principal:/opt/netbox-discovery/config.yml
Credenciais Hypervisor:/etc/netbox-discovery/hypervisors.json
Dependências isoladas: /opt/netbox-discovery/vendor
Sites:                 /opt/netbox-discovery/config/sites/
Relatórios:            /opt/netbox-discovery/reports
```
