#!/usr/bin/env python3

CONFIG_FILE = "/opt/netbox-discovery/config.yml"


def _convert(value):
    value = value.strip().strip('"').strip("'")

    if value.lower() == "true":
        return True
    if value.lower() == "false":
        return False
    if value.lower() in ("null", "none", "~"):
        return None

    return value


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

    required = [
        ("netbox", "url"),
        ("netbox", "token"),
        ("netbox", "verify_ssl"),
    ]

    for parent, key in required:
        if parent not in config or key not in config[parent]:
            raise RuntimeError(
                "Configuração obrigatória ausente: %s.%s" % (parent, key)
            )

    return config
