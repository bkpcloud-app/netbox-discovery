#!/bin/bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"

if [[ "$(id -u)" != "0" ]]; then
  echo "ERRO: execute como root." >&2
  exit 1
fi

install_dependencies() {
  local missing=0
  for cmd in python3 nmap snmpget snmpwalk; do
    command -v "$cmd" >/dev/null 2>&1 || missing=1
  done

  [[ "$missing" -eq 0 ]] && return 0

  echo "Instalando dependências..."

  if command -v dnf >/dev/null 2>&1; then
    dnf install -y python3 nmap net-snmp-utils
  elif command -v yum >/dev/null 2>&1; then
    yum install -y python3 nmap net-snmp-utils
  elif command -v apt-get >/dev/null 2>&1; then
    export DEBIAN_FRONTEND=noninteractive
    apt-get update
    apt-get install -y python3 nmap snmp
  else
    echo "ERRO: gerenciador de pacotes não suportado." >&2
    exit 1
  fi
}

install_dependencies

echo "===== INSTALANDO NETBOX-DISCOVERY ====="
bash "$ROOT/install.sh"

echo
echo "===== STATUS ====="
netbox-discovery status 2>/dev/null || true

echo
if [[ ! -f /opt/netbox-discovery/config.yml ]]; then
  echo "PRÓXIMO PASSO: netbox-discovery init"
else
  echo "CONFIG EXISTENTE PRESERVADA."
  echo "PRÓXIMO PASSO: netbox-discovery check"
fi
