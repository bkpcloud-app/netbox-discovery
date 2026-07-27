#!/bin/bash
set -euo pipefail

REPO_URL="https://github.com/bkpcloud-app/netbox-discovery.git"
DEST="/tmp/netbox-discovery-install"
REF="${NETBOX_DISCOVERY_REF:-stable}"

if [[ "$(id -u)" != "0" ]]; then
  echo "ERRO: execute como root." >&2
  exit 1
fi

install_git() {
  command -v git >/dev/null 2>&1 && return 0
  echo "Git não encontrado. Instalando dependência inicial..."
  if command -v dnf >/dev/null 2>&1; then
    dnf install -y git ca-certificates
  elif command -v yum >/dev/null 2>&1; then
    yum install -y git ca-certificates
  elif command -v apt-get >/dev/null 2>&1; then
    export DEBIAN_FRONTEND=noninteractive
    apt-get update
    apt-get install -y git ca-certificates
  else
    echo "ERRO: não encontrei dnf, yum ou apt-get." >&2
    exit 1
  fi
}

install_git

echo "===== BAIXANDO NETBOX-DISCOVERY ====="
rm -rf "$DEST"
git clone --depth 1 --branch "$REF" "$REPO_URL" "$DEST"
cd "$DEST"

[[ -f VERSION ]] || { echo "ERRO: VERSION não encontrado." >&2; exit 1; }
[[ -f bootstrap.sh ]] || { echo "ERRO: bootstrap.sh não encontrado." >&2; exit 1; }

echo
echo "Versão do produto: $(cat VERSION)"
echo "Origem: $REPO_URL"
echo "Canal/Ref: $REF"
echo
echo "===== INSTALANDO ====="
bash bootstrap.sh
