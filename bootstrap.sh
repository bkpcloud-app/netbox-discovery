#!/bin/bash
set -euo pipefail

# NETBOX-DISCOVERY V1.5.1 - DNS TOOLS
# O discovery utiliza DNS reverso como enriquecimento. O comando dig é
# instalado automaticamente, mas a ausência/falha de DNS não é fatal.
ensure_dns_tools() {
    if command -v dig >/dev/null 2>&1; then
        return 0
    fi

    echo "Instalando dependência DNS (dig)..."

    if command -v dnf >/dev/null 2>&1; then
        dnf install -y bind-utils
    elif command -v yum >/dev/null 2>&1; then
        yum install -y bind-utils
    elif command -v apt-get >/dev/null 2>&1; then
        apt-get update
        DEBIAN_FRONTEND=noninteractive apt-get install -y dnsutils
    else
        echo "ERRO: não foi possível instalar o comando dig."
        echo "Instale bind-utils (RHEL/CentOS) ou dnsutils (Debian/Ubuntu)."
        exit 1
    fi

    if ! command -v dig >/dev/null 2>&1; then
        echo "ERRO: dig continua indisponível após instalação."
        exit 1
    fi
}

ensure_dns_tools
# /NETBOX-DISCOVERY V1.5.1 - DNS TOOLS


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
if [[ -f /opt/netbox-discovery/config.yml ]]; then
  echo "===== STATUS ====="
  netbox-discovery status || true
  echo
  echo "CONFIG EXISTENTE PRESERVADA."
  echo "PRÓXIMO PASSO: netbox-discovery check"
else
  echo "===== INSTALAÇÃO NOVA ====="
  echo "CONFIG: ainda não criada (comportamento esperado)."
  echo "Nenhuma varredura foi iniciada."
  echo "Scheduler permanece desabilitado."
  echo "PRÓXIMO PASSO: netbox-discovery init"
fi
