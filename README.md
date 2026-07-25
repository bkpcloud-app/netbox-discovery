# netbox-discovery

Produto BKPCLOUD para descoberta, classificação, reconciliação, planejamento, importação segura e auditoria de inventário no NetBox.

**Versão atual:** 1.5.0

## Pipeline

```text
DISCOVER
→ CLASSIFY
→ RECONCILE
→ PLAN
→ IMPORT
→ AUDIT
```

## Instalação

Este repositório deve permanecer **privado**.

Em um Proxy com acesso SSH de leitura ao repositório:

```bash
rm -rf /tmp/netbox-discovery-install && \
git clone --depth 1 git@github.com:bkpcloud-app/netbox-discovery.git /tmp/netbox-discovery-install && \
sudo bash /tmp/netbox-discovery-install/bootstrap.sh
```

Depois, em uma instalação nova:

```bash
netbox-discovery init
netbox-discovery check
netbox-discovery run
```

Somente depois de validar o PLAN:

```bash
netbox-discovery run --apply
```

## Segurança

- `run` sem `--apply` não grava no NetBox.
- `REVIEW` não é importado automaticamente.
- `BLOCKED` nunca é importado automaticamente.
- `AUDIT` é somente leitura.
- O instalador não habilita scheduler automaticamente.
- Configuração real, tokens, SNMP communities, relatórios e logs de clientes não pertencem ao Git.

## Atualização

No Proxy:

```bash
cd /tmp/netbox-discovery-install
git pull --ff-only
sudo bash bootstrap.sh
```

O instalador preserva a configuração operacional existente.

## Documentação

- [Manual completo](docs/MANUAL.md)
- [Comandos rápidos](docs/COMANDOS-RAPIDOS.md)

## Operação

```bash
netbox-discovery help
netbox-discovery status
netbox-discovery configure
netbox-discovery run
netbox-discovery run --apply
netbox-discovery scheduler status
```
