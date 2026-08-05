# netbox-discovery 1.11.18 — Comandos rápidos

## Atualizar e validar

```bash
netbox-discovery update run
netbox-discovery version
netbox-discovery check
netbox-discovery status
```

## Analisar o último PLAN

```bash
netbox-discovery plan summary
netbox-discovery plan blocked
netbox-discovery plan review
netbox-discovery plan ready
netbox-discovery plan delegated
```

Todos são somente leitura.

## Write guard

Site pequeno, base menor que 50 Devices:

```text
WRITE GUARD POLÍTICA: SMALL_SITE_BOOTSTRAP_ABSOLUTE_ONLY
percentual=ADIADO
```

Continuam valendo:

```text
CREATE=25
UPDATE_SAFE=50
REPAIR=20
TOTAL=75
```

Base com 50 Devices ou mais:

```text
WRITE GUARD POLÍTICA: ABSOLUTE_AND_PERCENT
percentual=ATIVO
PERCENT=20%
```

## Dry-run

```bash
netbox-discovery run
```

Não grava no NetBox.

## Segundo plano

```bash
UNIT="netbox-discovery-manual-$(date +%Y%m%d-%H%M%S)"; echo "$UNIT" >/root/netbox-discovery-manual-unit; systemd-run --unit="$UNIT" --collect /usr/local/bin/netbox-discovery run
journalctl -fu "$(cat /root/netbox-discovery-manual-unit).service"
```

## Scheduler

```bash
netbox-discovery scheduler enable
netbox-discovery scheduler disable
netbox-discovery scheduler status
```

## Segurança

```text
run              = sem escrita
run --apply      = escrita READY após proteções
REVIEW           = não escreve
DELEGATED        = não escreve
BLOCKED          = não escreve
bootstrap        = adia só o percentual
limites absolutos= sempre ativos
```
