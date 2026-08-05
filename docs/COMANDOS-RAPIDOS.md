# netbox-discovery 1.11.15 — Comandos rápidos

## Atualizar e validar

```bash
netbox-discovery update run
```

```bash
netbox-discovery version
```

```bash
netbox-discovery check
```

```bash
netbox-discovery status
```

## Auto-update

```bash
netbox-discovery update scheduler status
```

```bash
netbox-discovery update scheduler enable
```

A partir da 1.11.15, cada execução automática faz:

```text
UPDATE PREFLIGHT → COLETA
```

Se houver versão nova, ela é validada, instalada e testada antes da coleta. Se o GitHub estiver indisponível, a coleta segue com a versão instalada.

## Configurar redes

```bash
netbox-discovery configure
```

Conferir:

```bash
cat /opt/netbox-discovery/config/sites/$(awk '/^[[:space:]]*site:/{print $2; exit}' /opt/netbox-discovery/config.yml)/networks.conf
```

## Dry-run manual

```bash
netbox-discovery run
```

Não grava no NetBox.

## Executar em segundo plano

```bash
UNIT="netbox-discovery-manual-$(date +%Y%m%d-%H%M%S)"; echo "$UNIT" >/root/netbox-discovery-manual-unit; systemd-run --unit="$UNIT" --collect /usr/local/bin/netbox-discovery run
```

Acompanhar:

```bash
journalctl -fu "$(cat /root/netbox-discovery-manual-unit).service"
```

Parar:

```bash
systemctl stop "$(cat /root/netbox-discovery-manual-unit).service"
```

## Scheduler Network

```bash
netbox-discovery scheduler enable
```

```bash
netbox-discovery scheduler disable
```

```bash
netbox-discovery scheduler status
```

## Scheduler Hypervisor

```bash
netbox-discovery hypervisor scheduler enable
```

```bash
netbox-discovery hypervisor scheduler disable
```

```bash
netbox-discovery hypervisor scheduler status
```

## Segurança

```text
run              = sem escrita
run --apply      = escrita READY após proteções
REVIEW           = não escreve
DELEGATED        = não escreve
BLOCKED          = não escreve
UPDATE PREFLIGHT = não altera automation.apply
```

## Logs

```bash
journalctl -u netbox-discovery.service --no-pager -n 200
```

```bash
journalctl -u netbox-discovery-update.service --no-pager -n 100
```

## Arquivos

```text
/opt/netbox-discovery/config.yml
/opt/netbox-discovery/config/sites/<SITE>/networks.conf
/opt/netbox-discovery/reports
/var/lib/netbox-discovery/update-state.json
/var/lib/netbox-discovery/update-backups
```
