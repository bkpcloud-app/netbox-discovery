#!/bin/bash
set -euo pipefail

TARGET="/opt/netbox-discovery"
SRC="$(cd "$(dirname "$0")" && pwd)/netbox-discovery"
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

for cmd in nmap snmpget snmpwalk; do
  if ! command -v "$cmd" >/dev/null 2>&1; then
    echo "ERRO: dependência ausente: $cmd" >&2
    exit 1
  fi
done

mkdir -p "$TARGET"/{reports,logs,cache,backups,config/sites}
BACKUP="$TARGET/backups/pre-product-v1-$STAMP"
mkdir -p "$BACKUP"

# Backup only code/configuration, never duplicate reports/logs/cache.
for item in VERSION workflow.yml config.yml bin lib modules config systemd; do
  if [[ -e "$TARGET/$item" ]]; then
    cp -a "$TARGET/$item" "$BACKUP/"
  fi
done

# Product package intentionally contains no live config.yml, so customer/site
# credentials and configuration are preserved on upgrades.
\cp -af "$SRC/." "$TARGET/"

chmod +x "$TARGET/bin/netbox-discovery"
find "$TARGET/modules" -type f -name '*.py' -exec chmod 750 {} \;
chmod 750 "$TARGET/bin/netbox-discovery"
[[ -f "$TARGET/config.yml" ]] && chmod 600 "$TARGET/config.yml"
find "$TARGET/config/sites" -type f -name 'snmp-communities.conf' -exec chmod 600 {} \; 2>/dev/null || true

ln -sfn "$TARGET/bin/netbox-discovery" /usr/local/bin/netbox-discovery

install -m 0644 "$TARGET/systemd/netbox-discovery.service" /etc/systemd/system/netbox-discovery.service
install -m 0644 "$TARGET/systemd/netbox-discovery.timer" /etc/systemd/system/netbox-discovery.timer
install -m 0644 "$TARGET/systemd/netbox-discovery-hypervisor.service" /etc/systemd/system/netbox-discovery-hypervisor.service
install -m 0644 "$TARGET/systemd/netbox-discovery-hypervisor.timer" /etc/systemd/system/netbox-discovery-hypervisor.timer
systemctl daemon-reload
# Safety: installer never enables or starts the timer.

/usr/bin/python3 -m py_compile \
  "$TARGET/lib/config.py" \
  "$TARGET/lib/netbox.py" \
  "$TARGET/modules/discovery/network.py" \
  "$TARGET/modules/inventory/classifier.py" \
  "$TARGET/modules/inventory/reconciler.py" \
  "$TARGET/modules/inventory/planner.py" \
  "$TARGET/modules/inventory/pipeline.py" \
  "$TARGET/modules/importers/importer.py" \
  "$TARGET/modules/auditors/inventory.py" \
  "$TARGET/modules/product/configurator.py" \
  "$TARGET/modules/product/runner.py" \
  "$TARGET/modules/product/status.py" \
  "$TARGET/modules/hypervisor/config.py" \
  "$TARGET/modules/hypervisor/collectors.py" \
  "$TARGET/modules/hypervisor/engine.py" \
  "$TARGET/modules/hypervisor/configurator.py" \
  "$TARGET/modules/hypervisor/checker.py" \
  "$TARGET/modules/hypervisor/runner.py" \
  "$TARGET/modules/hypervisor/status.py"

printf '\nNETBOX-DISCOVERY PRODUCT V1 INSTALADO\n'
printf 'Versão: %s\n' "$(cat "$TARGET/VERSION")"
printf 'Backup: %s\n' "$BACKUP"
printf 'Schedulers network/hypervisor: NÃO HABILITADOS pelo instalador\n'

if [[ -f "$TARGET/config.yml" ]]; then
  "$TARGET/bin/netbox-discovery" check
  echo "CONFIG EXISTENTE: PRESERVADA"
  echo "Próximo comando operacional: netbox-discovery status"
else
  echo "CONFIG: ainda não criada"
  echo "Execute: netbox-discovery init"
fi
