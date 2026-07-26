#!/usr/bin/env python3

CONFIG_FILE = "/opt/netbox-discovery/config.yml"
LOCKED_NETBOX_URL = "https://inventory.bkpcloud.app.br:8080"


def _convert(value):
    value = value.strip().strip('"').strip("'")

    if value.lower() == "true":
        return True
    if value.lower() == "false":
        return False
    if value.lower() in ("null", "none", "~"):
        return None

    return value


def _normalized_url(value):
    return str(value or "").strip().rstrip("/").lower()


def load_config(path=CONFIG_FILE):
    config = {}
    section = None

    with open(path, "r") as file:
        for raw_line in file:
            if not raw_line.strip() or raw_line.lstrip().startswith("#"):
                continue

            indent = len(raw_line) - len(raw_line.lstrip())
            line = raw_line.strip()

            if indent == 0 and line.endswith(":"):
                section = line[:-1].strip()
                config[section] = {}
                continue

            if ":" not in line:
                continue

            key, value = line.split(":", 1)
            key = key.strip()
            value = _convert(value)

            if indent > 0 and section:
                config[section][key] = value
            else:
                config[key] = value
                section = None

    if "netbox" not in config or not isinstance(config.get("netbox"), dict):
        config["netbox"] = {}

    configured_url = config["netbox"].get("url")
    if configured_url and _normalized_url(configured_url) != _normalized_url(LOCKED_NETBOX_URL):
        raise RuntimeError(
            "Endpoint NetBox não autorizado: %s. Este produto usa somente %s"
            % (configured_url, LOCKED_NETBOX_URL)
        )
    config["netbox"]["url"] = LOCKED_NETBOX_URL

    required = [
        ("netbox", "token"),
        ("netbox", "verify_ssl"),
    ]

    for parent, key in required:
        if parent not in config or key not in config[parent]:
            raise RuntimeError(
                "Configuração obrigatória ausente: %s.%s" % (parent, key)
            )

    return config
