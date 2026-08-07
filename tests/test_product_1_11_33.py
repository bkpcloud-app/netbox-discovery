#!/usr/bin/env python3
import os

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

COMMAND = (
    "curl -fsSL https://raw.githubusercontent.com/bkpcloud-app/netbox-discovery/stable/install-from-github.sh "
    "-o /tmp/netbox-discovery-install.sh && bash /tmp/netbox-discovery-install.sh && "
    "netbox-discovery init && netbox-discovery check && netbox-discovery scheduler enable && "
    "netbox-discovery run --apply"
)
ENDPOINT = "https://inventory.bkpcloud.app.br"
DOCS = [
    "README.md",
    "docs/MANUAL.md",
    "docs/COMANDOS-RAPIDOS.md",
    "docs/NOVA-UNIDADE-DOIS-PASSOS.md",
]


def read(path):
    with open(os.path.join(ROOT, path), "r") as handle:
        return handle.read()


def main():
    for path in DOCS:
        text = read(path)
        assert COMMAND in text, "%s não contém o comando oficial de instalação limpa" % path
        assert ENDPOINT in text, "%s não contém o endpoint oficial" % path
        zero_section = text.lower()
        assert "instala" in zero_section and "scheduler" in zero_section, path

    manual = read("docs/MANUAL.md")
    quick = read("docs/COMANDOS-RAPIDOS.md")
    new_site = read("docs/NOVA-UNIDADE-DOIS-PASSOS.md")

    for text, path in ((manual, "MANUAL"), (quick, "COMANDOS-RAPIDOS"), (new_site, "NOVA-UNIDADE")):
        assert "Permitir IMPORT automático" in text, "%s sem orientação de auto-apply" % path
        assert "Não" in text or "não" in text

    assert "https://inventory.bkpcloud.app.br:8080" not in manual
    assert "https://inventory.bkpcloud.app.br:8080" not in quick
    assert "https://inventory.bkpcloud.app.br:8080" not in new_site

    print("ALL 1.11.33 ZERO-INSTALL DOCUMENTATION TESTS PASSED")


if __name__ == "__main__":
    main()
