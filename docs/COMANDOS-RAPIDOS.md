# netbox-discovery 1.11.14 — Comandos rápidos

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

## Versões esperadas

```text
Versão: 1.11.14
DISCOVER V6: OK
CLASSIFY V8: OK
RECONCILE V5: OK
PLAN V11: OK
IMPORT V12: OK
AUDIT V11: OK
```

Componentes:

```text
Discovery: 4.6-product
Classifier: 5.6-product
Reconciler: 3.3-product
Planner: 5.3-product
Importer: 6.1-product
Auditor: 6.9-product
Pipeline: 3.4-product
Runner: 3.4-product
```

## Executar Network sem escrita

```bash
netbox-discovery run
```

Resultado esperado:

```text
NetBox write: NÃO
```

## Executar Network com escrita

Somente após revisão do PLAN:

```bash
netbox-discovery run --apply
```

## Scheduler Network

```bash
netbox-discovery scheduler enable
```

```bash
netbox-discovery scheduler status
```

```bash
netbox-discovery scheduler disable
```

Ao habilitar, o timer de auto-update também é iniciado como dependência. Desabilitar a coleta não desabilita o auto-update.

## Auto-update

```bash
netbox-discovery update scheduler status
```

```bash
netbox-discovery update scheduler enable
```

Política padrão:

```text
diário
Persistent=true
RandomizedDelaySec=30m
canal stable
rollback automático
```

## Hypervisor

```bash
netbox-discovery hypervisor configure
```

```bash
netbox-discovery hypervisor run
```

```bash
netbox-discovery hypervisor scheduler enable
```

O scheduler Hypervisor também inicia o timer de auto-update como dependência.

## Configurar redes

```bash
netbox-discovery configure
```

Conferir:

```bash
cat /opt/netbox-discovery/config/sites/$(awk '/^[[:space:]]*site:/{print $2; exit}' /opt/netbox-discovery/config.yml)/networks.conf
```

## Redes grandes

Para `/16` ou coleta longa sem depender da sessão SSH:

```bash
systemd-run --unit=netbox-discovery-manual --collect /usr/local/bin/netbox-discovery run
```

```bash
journalctl -fu netbox-discovery-manual.service
```

## Segurança

```text
run              = sem escrita
run --apply      = IMPORT de READY + AUDIT
REVIEW/BLOCKED   = nunca escritos
nome existente   = preservado
scheduler padrão = apply false
```
