# netbox-discovery 1.11.16 — Comandos rápidos

## Atualizar e validar

```bash
netbox-discovery update run
netbox-discovery version
netbox-discovery check
netbox-discovery status
```

## Analisar o último PLAN sem comando manual

Resumo:

```bash
netbox-discovery plan summary
```

Bloqueados:

```bash
netbox-discovery plan blocked
```

Em revisão:

```bash
netbox-discovery plan review
```

READY:

```bash
netbox-discovery plan ready
```

DELEGATED:

```bash
netbox-discovery plan delegated
```

Limitar linhas ou retornar JSON:

```bash
netbox-discovery plan blocked --limit 20
netbox-discovery plan summary --json
```

Todos são somente leitura.

## Auto-update

```bash
netbox-discovery update scheduler status
netbox-discovery update scheduler enable
```

Cada execução automática faz:

```text
UPDATE PREFLIGHT → COLETA
```

## Configurar redes

```bash
netbox-discovery configure
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
netbox-discovery scheduler disable
netbox-discovery scheduler status
```

## Scheduler Hypervisor

```bash
netbox-discovery hypervisor scheduler enable
netbox-discovery hypervisor scheduler disable
netbox-discovery hypervisor scheduler status
```

## Segurança

```text
run              = sem escrita
run --apply      = escrita READY após proteções
plan summary     = somente leitura
plan blocked     = somente leitura
REVIEW           = não escreve
DELEGATED        = não escreve
BLOCKED          = não escreve
UPDATE PREFLIGHT = não altera automation.apply
```

## Logs

```bash
journalctl -u netbox-discovery.service --no-pager -n 200
journalctl -u netbox-discovery-update.service --no-pager -n 100
```
