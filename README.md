# netbox-discovery

Produto BKPCLOUD para descoberta, classificação, reconciliação, planejamento, importação segura e auditoria de inventário no NetBox.

**Versão atual:** 1.6.0 — PRODUCT V1
**Distribuição:** repositório público oficial `bkpcloud-app/netbox-discovery`

## Pipeline

```text
DISCOVER
→ CLASSIFY
→ RECONCILE
→ PLAN
→ IMPORT
→ AUDIT
```

## Instalação em Proxy zerado

O fluxo oficial não usa ZIP, Deploy Key, GitHub App ou credencial do GitHub.

Cole como `root`:

```bash
bash -lc '
set -euo pipefail
if ! command -v curl >/dev/null 2>&1; then
    if command -v dnf >/dev/null 2>&1; then dnf install -y curl ca-certificates
    elif command -v yum >/dev/null 2>&1; then yum install -y curl ca-certificates
    elif command -v apt-get >/dev/null 2>&1; then apt-get update && apt-get install -y curl ca-certificates
    else echo "ERRO: não encontrei dnf, yum ou apt-get"; exit 1
    fi
fi
curl -fsSL https://raw.githubusercontent.com/bkpcloud-app/netbox-discovery/main/install-from-github.sh | bash
'
```

O instalador de origem:

- instala `git` caso esteja ausente;
- clona o repositório público por HTTPS;
- executa o `bootstrap.sh`;
- instala Python/Nmap/SNMP quando necessário;
- preserva configuração existente em upgrade;
- não executa discovery;
- não habilita scheduler;
- em instalação nova termina pedindo `netbox-discovery init`.

## Primeiro uso

```bash
netbox-discovery init
netbox-discovery check
netbox-discovery run
```

Revise o PLAN. Somente depois:

```bash
netbox-discovery run --apply
netbox-discovery status
```

## Segurança operacional

- `run` sem `--apply` não grava no NetBox.
- `REVIEW` não é importado automaticamente.
- `BLOCKED` nunca é importado automaticamente.
- `NOOP` não altera o objeto.
- `AUDIT` é somente leitura.
- O instalador não habilita scheduler automaticamente.
- `init` e `configure` não iniciam varredura.

## Segurança do repositório público

Este repositório contém somente produto e documentação.

**Nunca versionar:**

- `config.yml` real;
- token do NetBox;
- community SNMP real;
- senhas/chaves privadas;
- `.pem`;
- relatórios, logs ou backups de clientes.

## Atualização

Execute novamente o instalador oficial:

```bash
curl -fsSL https://raw.githubusercontent.com/bkpcloud-app/netbox-discovery/main/install-from-github.sh | bash
```

A instalação preserva a configuração operacional existente.

Para fixar explicitamente a versão 1.5.2:

```bash
NETBOX_DISCOVERY_REF=v1.5.2 bash -c "$(curl -fsSL https://raw.githubusercontent.com/bkpcloud-app/netbox-discovery/main/install-from-github.sh)"
```

## Documentação

- [Manual completo](docs/MANUAL.md)
- [Comandos rápidos](docs/COMANDOS-RAPIDOS.md)
- [Notas da release](RELEASE-NOTES.md)
- [Política de segurança](SECURITY.md)

## Operação

```bash
netbox-discovery help
netbox-discovery version
netbox-discovery status
netbox-discovery configure
netbox-discovery run
netbox-discovery run --apply
netbox-discovery scheduler status
```
