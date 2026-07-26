# netbox-discovery Product V1 — 1.8.0

Produto único com dois pipelines independentes.

## Network

Comandos existentes, preservados:

- `netbox-discovery run`
- `netbox-discovery run --apply`
- `netbox-discovery status`
- `netbox-discovery scheduler ...`

Pipeline: `DISCOVER -> CLASSIFY -> RECONCILE -> PLAN -> IMPORT -> AUDIT`.

## Hypervisor

- `netbox-discovery hypervisor configure`
- `netbox-discovery hypervisor check`
- `netbox-discovery hypervisor run`
- `netbox-discovery hypervisor run --apply`
- `netbox-discovery hypervisor status`
- `netbox-discovery hypervisor scheduler ...`

Conectores: VMware vCenter/ESXi, Proxmox VE e Microsoft Hyper-V.

O Hypervisor cria/reconcilia a base de Prefixes configurados, Clusters, hosts físicos, VMs/containers, interfaces, MACs e IPs quando a evidência permite. Não apaga automaticamente.

## Ordem operacional recomendada

`Hypervisor` primeiro, `Network` depois. Não existe comando `full-run`; falhas e agendas permanecem isoladas.

## Endpoint

O endpoint NetBox é fixo em `https://inventory.bkpcloud.app.br:8080`. Configuração divergente é recusada.

## Política de segurança

- escrita exige `--apply` ou automação explicitamente configurada;
- `REVIEW`/`BLOCKED` não são escritos;
- preflight ocorre antes da primeira escrita;
- identidade por serial/UUID/IP/MAC evita duplicidade;
- nomes existentes no NetBox são autoritativos e não são sobrescritos;
- bindings existentes de interface por IP/MAC são preservados;
- Hypervisor não executa DELETE;
- credenciais Hypervisor ficam em arquivo root-only fora do repositório;
- timers não são habilitados pelo instalador.
