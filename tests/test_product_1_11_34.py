#!/usr/bin/env python3
import os

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
VERSION = open(os.path.join(ROOT, "VERSION"), "r").read().strip()


def read(path):
    with open(os.path.join(ROOT, path), "r") as handle:
        return handle.read()


def main():
    assert VERSION == "1.11.34"
    assert read("netbox-discovery/VERSION").strip() == VERSION

    exact = {
        "README.md": "**Versão atual:** %s" % VERSION,
        "docs/MANUAL.md": "**Versão:** %s" % VERSION,
        "docs/COMANDOS-RAPIDOS.md": "# netbox-discovery %s" % VERSION,
        "docs/HOMOLOGACAO.md": "# netbox-discovery %s" % VERSION,
        "RELEASE-NOTES.md": "## V%s" % VERSION,
        "SECURITY.md": "**Versão da política:** %s" % VERSION,
        "docs/PATCH-%s.md" % VERSION: "# netbox-discovery %s" % VERSION,
    }
    for path, marker in exact.items():
        assert os.path.isfile(os.path.join(ROOT, path)), path
        assert marker in read(path), "%s não está na versão exata %s" % (path, VERSION)

    manual = read("docs/MANUAL.md")
    assert "Ponto de retomada" in manual
    assert "NetBox → Zabbix" in manual
    assert "main" in manual and "stable" in manual
    assert "toda release" in manual.lower()

    example = read("netbox-discovery/config.yml.example")
    assert "url: https://inventory.bkpcloud.app.br\n" in example
    assert "https://inventory.bkpcloud.app.br:8080" not in example

    install = read("install.sh")
    assert "VERSION config.yml bin lib modules config systemd" in install
    assert "VERSION workflow.yml" not in install

    stale = (
        "SHA256SUMS",
        "netbox-discovery/docs/PRODUCT-V1.md",
        "netbox-discovery/workflow.yml",
    )
    for path in stale:
        assert not os.path.exists(os.path.join(ROOT, path)), "artefato obsoleto voltou: %s" % path

    print("ALL 1.11.34 REPOSITORY HYGIENE/CONTINUITY TESTS PASSED")


if __name__ == "__main__":
    main()
