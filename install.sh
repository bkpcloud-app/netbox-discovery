#!/bin/bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
TARGET="/opt/netbox-discovery"
SRC="$ROOT/netbox-discovery"
STAMP="$(date +%Y%m%d-%H%M%S)"

if [[ "$(id -u)" != "0" ]]; then
  echo "ERRO: execute como root." >&2
  exit 1
fi

if [[ ! -x /usr/bin/python3 ]]; then
  echo "ERRO: /usr/bin/python3 não encontrado." >&2
  exit 1
fi

/usr/bin/python3 - <<'PY'
import sys
if sys.version_info < (3, 6):
    raise SystemExit('ERRO: Python 3.6+ é obrigatório')
print('PYTHON: {0}.{1}.{2}'.format(*sys.version_info[:3]))
PY

for cmd in nmap snmpget snmpwalk git; do
  if ! command -v "$cmd" >/dev/null 2>&1; then
    echo "ERRO: dependência ausente: $cmd" >&2
    exit 1
  fi
done

# Validate candidate before touching the installed product.
/usr/bin/python3 "$SRC/modules/product/selftest.py" --base "$SRC" --package-root "$ROOT"

mkdir -p "$TARGET"/{reports,logs,cache,backups,config/sites}
BACKUP="$TARGET/backups/pre-product-v1-$STAMP"
mkdir -p "$BACKUP"

for item in VERSION workflow.yml config.yml bin lib modules config systemd; do
  if [[ -e "$TARGET/$item" ]]; then
    cp -a "$TARGET/$item" "$BACKUP/"
  fi
done

# Live config.yml and site files are not shipped in the package, therefore
# credentials/site configuration survive upgrades.
\cp -af "$SRC/." "$TARGET/"

# Migrate legacy preserved configurations before any scheduler command is used.
# Missing automation fields are added with safe defaults. The exact official
# NetBox endpoint is migrated from :8080 to HTTPS/443 and, by product policy,
# verify_ssl=false is set for that endpoint. Customer-specific URLs are not
# touched.
if [[ -f "$TARGET/config.yml" ]]; then
  /usr/bin/python3 "$TARGET/modules/product/config_migrations.py" \
    --config "$TARGET/config.yml" \
    --ensure-network-automation \
    --migrate-netbox-url
fi

chmod +x "$TARGET/bin/netbox-discovery" "$TARGET/bin/netbox-discovery-wrapper"
find "$TARGET/modules" -type f -name '*.py' -exec chmod 750 {} \;
chmod 750 "$TARGET/bin/netbox-discovery" "$TARGET/bin/netbox-discovery-wrapper"
[[ -f "$TARGET/config.yml" ]] && chmod 600 "$TARGET/config.yml"
find "$TARGET/config/sites" -type f -name 'snmp-communities.conf' -exec chmod 600 {} \; 2>/dev/null || true

# Public command uses the wrapper. All legacy/subcommands are delegated to the
# original command; go-live is handled natively by the product.
ln -sfn "$TARGET/bin/netbox-discovery-wrapper" /usr/local/bin/netbox-discovery

for unit in \
  netbox-discovery.service \
  netbox-discovery.timer \
  netbox-discovery-hypervisor.service \
  netbox-discovery-hypervisor.timer \
  netbox-discovery-update.service \
  netbox-discovery-update.timer; do
  install -m 0644 "$TARGET/systemd/$unit" "/etc/systemd/system/$unit"
done

systemctl daemon-reload

# Product policy: stable auto-update is on by default. Network and Hypervisor
# automation remain opt-in.
systemctl enable --now netbox-discovery-update.timer

/usr/bin/python3 "$TARGET/modules/product/selftest.py" --base "$TARGET"

printf '\nNETBOX-DISCOVERY PRODUCT V1 INSTALADO\n'
printf 'Versão: %s\n' "$(cat "$TARGET/VERSION")"
printf 'Backup: %s\n' "$BACKUP"
printf 'Auto-update stable: HABILITADO\n'
printf 'Schedulers network/hypervisor: NÃO HABILITADOS pelo instalador\n'

if [[ -f "$TARGET/config.yml" ]]; then
  /usr/local/bin/netbox-discovery check
  echo "CONFIG EXISTENTE: PRESERVADA"
  echo "Próximo comando operacional: netbox-discovery status"
else
  echo "CONFIG: ainda não criada"
  echo "Execute: netbox-discovery init"
fi
