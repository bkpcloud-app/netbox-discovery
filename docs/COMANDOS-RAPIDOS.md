# netbox-discovery V1.6.0 — Comandos rápidos

## 1. Instalar em um Proxy zerado

Como `root`:

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

Não precisa ZIP, Deploy Key ou autenticação GitHub.

Em instalação nova é normal terminar com:

```text
CONFIG: ainda não criada (comportamento esperado).
PRÓXIMO PASSO: netbox-discovery init
```

## 2. Configurar cliente/site

```bash
netbox-discovery init
netbox-discovery check
```

O `init` salva a configuração e não inicia discovery.

## 3. Primeira execução segura

```bash
netbox-discovery run
```

```text
DISCOVER → CLASSIFY → RECONCILE → PLAN
```

Sem `--apply`: sem escrita no NetBox.

## 4. Execução completa com escrita

Somente depois de revisar o PLAN:

```bash
netbox-discovery run --apply
```

```text
DISCOVER → CLASSIFY → RECONCILE → PLAN → IMPORT → AUDIT
```

```text
READY   → elegível para escrita
REVIEW  → não importa automaticamente
BLOCKED → nunca importa automaticamente
NOOP    → não altera
```

## 5. Estado atual

```bash
netbox-discovery status
```

## 6. Alterar configuração

```bash
netbox-discovery configure
```

## 7. Scheduler

Recomendação inicial:

```text
Automação: SIM
Agenda: daily
Import automático: NÃO
```

```bash
netbox-discovery scheduler enable
netbox-discovery scheduler status
netbox-discovery scheduler disable
```

## 8. Atualizar produto

```bash
curl -fsSL https://raw.githubusercontent.com/bkpcloud-app/netbox-discovery/main/install-from-github.sh | bash
```

Configuração existente é preservada.

## 9. Comandos úteis

```bash
netbox-discovery help
netbox-discovery version
netbox-discovery check
netbox-discovery discover
netbox-discovery classify
netbox-discovery reconcile
netbox-discovery plan
netbox-discovery inventory
netbox-discovery import
netbox-discovery import --apply
netbox-discovery audit
netbox-discovery run
netbox-discovery run --apply
netbox-discovery status
```

## 10. Caminhos principais

```text
Aplicação:     /opt/netbox-discovery
Configuração: /opt/netbox-discovery/config.yml
Sites:         /opt/netbox-discovery/config/sites/
Relatórios:    /opt/netbox-discovery/reports
Logs:          /opt/netbox-discovery/logs
Backups:       /opt/netbox-discovery/backups
```

## 11. Fluxo oficial para site novo

```text
INSTALAR DO GITHUB
→ INIT
→ CHECK
→ RUN
→ CONFERIR PLAN
→ RUN --APPLY
→ STATUS
→ SCHEDULER
```

Não editar inventário manualmente para “ajudar” o discovery.
Não começar um site novo diretamente com `--apply`.
