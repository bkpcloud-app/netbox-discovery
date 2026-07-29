# Dell PowerVault — Comandos rápidos

## MD3200 — validar SMcli

```bash
runuser -u zabbix -- \
  env HOME=/var/lib/zabbix \
  /usr/bin/SMcli \
  10.1.1.56 10.1.1.57 \
  -S \
  -c "show storageArray healthStatus;"
```

## MD3200 — executar cache manualmente

```bash
systemctl start dell-md3200-cache.service
systemctl --no-pager --full status dell-md3200-cache.service
journalctl -u dell-md3200-cache.service --no-pager -n 100
```

## MD3200 — validar timer

```bash
systemctl status dell-md3200-cache.timer
systemctl list-timers --all | grep dell-md3200-cache
```

## MD3200 — listar arquivos do cache

```bash
find /var/lib/zabbix/md3200-cache \
  -maxdepth 3 \
  -type f \
  -printf '%M %u:%g %s bytes %p\n'
```

## MD3200 — testar cache como Zabbix

```bash
runuser -u zabbix -- \
  /usr/lib/zabbix/externalscripts/dell_md3200_cache.py \
  health \
  10.1.1.56 \
  10.1.1.57 \
  300
```

Resultado esperado:

```text
available = 1
return_code = 0
storage_health = optimal
cache_stale = 0
errors =
```

## Proxy Zabbix

```bash
systemctl --no-pager --full status zabbix-proxy
grep -E '^[[:space:]]*Timeout=' /etc/zabbix/zabbix_proxy.conf
```

## Comunicação com as controladoras

```bash
ping -c 3 10.1.1.56
ping -c 3 10.1.1.57

timeout 5 bash -c '</dev/tcp/10.1.1.56/2463' && echo OK
timeout 5 bash -c '</dev/tcp/10.1.1.57/2463' && echo OK
```

## ME4024 — controladoras

```text
Controller A: 10.1.1.52
Controller B: 10.1.1.53
```

## Macros ME4024

```text
{$POWERVAULT.IP.A}
{$POWERVAULT.IP.B}
{$POWERVAULT.API.USER}
{$POWERVAULT.API.PASSWORD}
```

## Macros MD3200

```text
{$MD3200.IP.A} = 10.1.1.56
{$MD3200.IP.B} = 10.1.1.57
{$MD3200.SMCLI} = /usr/bin/SMcli
```
