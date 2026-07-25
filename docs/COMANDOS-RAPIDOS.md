# netbox-discovery V1.5.0 — Comandos rápidos

## 1. Instalar em um Proxy novo

Copie o pacote:

```text
netbox-discovery-v1.5.0-PRODUCT-V1.zip
```

para `/root` e execute:

```bash
cd /root

rm -rf /tmp/netbox-product-v1
mkdir -p /tmp/netbox-product-v1

unzip -o \
  /root/netbox-discovery-v1.5.0-PRODUCT-V1.zip \
  -d /tmp/netbox-product-v1

bash /tmp/netbox-product-v1/install.sh
```

## 2. Configurar um cliente/site novo

```bash
netbox-discovery init
```

Depois:

```bash
netbox-discovery check
```

O `init` configura o site, mas não inicia discovery automaticamente.

## 3. Primeira execução segura — sem gravar no NetBox

```bash
netbox-discovery run
```

Fluxo:

```text
DISCOVER
→ CLASSIFY
→ RECONCILE
→ PLAN
```

Sem `--apply` não há escrita no NetBox.

## 4. Execução completa com escrita real

Somente depois de validar o PLAN:

```bash
netbox-discovery run --apply
```

Fluxo:

```text
DISCOVER
→ CLASSIFY
→ RECONCILE
→ PLAN
→ IMPORT
→ AUDIT
```

Regras:

```text
READY   → elegível para escrita
REVIEW  → não importa automaticamente
BLOCKED → nunca importa automaticamente
NOOP    → não altera
```

## 5. Ver estado atual

```bash
netbox-discovery status
```

## 6. Alterar configuração

```bash
netbox-discovery configure
```

## 7. Scheduler

Configurar primeiro:

```bash
netbox-discovery configure
```

Recomendação inicial:

```text
Automação: SIM
Agenda: daily
Import automático: NÃO
```

Habilitar:

```bash
netbox-discovery scheduler enable
```

Verificar:

```bash
netbox-discovery scheduler status
```

Desabilitar:

```bash
netbox-discovery scheduler disable
```

## 8. Comandos úteis

```bash
netbox-discovery help
netbox-discovery version
netbox-discovery check
netbox-discovery discover
netbox-discovery classify
netbox-discovery reconcile
netbox-discovery plan
netbox-discovery inventory
netbox-discovery import
netbox-discovery import --apply
netbox-discovery audit
netbox-discovery run
netbox-discovery run --apply
netbox-discovery status
```

## 9. Caminhos principais

```text
Aplicação:     /opt/netbox-discovery
Configuração: /opt/netbox-discovery/config.yml
Sites:         /opt/netbox-discovery/config/sites/
Relatórios:    /opt/netbox-discovery/reports
Logs:          /opt/netbox-discovery/logs
Backups:       /opt/netbox-discovery/backups
```

## 10. Regra de ouro para cliente novo

```text
INSTALAR
→ INIT
→ CHECK
→ RUN
→ CONFERIR PLAN
→ RUN --APPLY
→ STATUS
→ SCHEDULER
```

Não editar inventário manualmente para “ajudar” o discovery.
Não começar um site novo diretamente com `--apply`.
