# Manual Operacional — netbox-discovery

**Produto:** netbox-discovery  
**Versão:** 1.11.14 — PRODUCT V1  
**Distribuição oficial:** `bkpcloud-app/netbox-discovery`  
**Canal de produção:** `stable`

> `CI PASS` não equivale a `LIVE PASS`. Consulte `docs/HOMOLOGACAO.md` antes de liberar APPLY automático em um cliente.

## 1. Componentes atuais

```text
Discovery V6:   4.6-product
Classifier V8:  5.6-product
Reconciler V5:  3.3-product
Planner V11:    5.3-product
Importer V12:   6.1-product
Auditor V11:    6.9-product
Pipeline:        3.4-product
Runner:          3.4-product
```

## 2. Instalação e atualização

O instalador preserva configuração, token, redes, exclusões e comunidades SNMP. Antes de substituir o produto, executa self-test e cria backup.

Atualização manual:

```bash
netbox-discovery update run
```

Validação:

```bash
netbox-discovery version
netbox-discovery check
netbox-discovery status
```

O updater trabalha no canal `stable`, valida o pacote antes e depois da instalação e executa rollback quando a nova versão não passa no self-test.

## 3. Auto-update

A instalação habilita por padrão:

```text
netbox-discovery-update.timer
```

Configuração padrão:

```text
OnCalendar=daily
Persistent=true
RandomizedDelaySec=30m
```

Verificar:

```bash
netbox-discovery update scheduler status
```

Habilitar manualmente:

```bash
netbox-discovery update scheduler enable
```

Desabilitar manualmente:

```bash
netbox-discovery update scheduler disable
```

### Garantia ao habilitar coleta automática

Os timers Network e Hypervisor possuem dependência `Wants` do timer de atualização. Portanto, ao iniciar qualquer scheduler de coleta, o auto-update também é iniciado.

Essa dependência não usa `Also=`. Assim, desabilitar um scheduler de coleta não desabilita o auto-update.

## 4. Configuração Network

```bash
netbox-discovery configure
```

O assistente grava:

```text
Tenant
Tenant Group opcional
Site
URL e token do NetBox
validação SSL
redes CIDR
exclusões
comunidades SNMP
automação
```

O assistente não inicia descoberta e não executa escrita.

Arquivos por site:

```text
/opt/netbox-discovery/config/sites/<SITE>/networks.conf
/opt/netbox-discovery/config/sites/<SITE>/exclusions.conf
/opt/netbox-discovery/config/sites/<SITE>/snmp-communities.conf
```

## 5. Execução Network

Dry-run completo:

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

Resultado esperado:

```text
NetBox write: NÃO
```

Execução com escrita:

```bash
netbox-discovery run --apply
```

Fluxo adicional:

```text
preflight
→ write guard
→ IMPORT somente de registros READY elegíveis
→ AUDIT
```

Nunca use `--apply` antes de revisar o PLAN.

## 6. Discovery LARGE-CIDR

Quando o conjunto passa de 4096 endereços candidatos, o Discovery V6 ativa o modo `LARGE-CIDR`.

Comportamento:

- consolida CIDRs sobrepostos;
- divide prefixos grandes em lotes de até `/24`;
- usa paralelismo controlado;
- aplica timeout individual por lote;
- repete somente lotes com falha;
- mostra progresso;
- inclui portas de infraestrutura, impressão, CFTV, virtualização e OT;
- evita rescue TCP exaustivo sobre dezenas de milhares de endereços ausentes.

Para execução longa fora da sessão SSH:

```bash
systemd-run --unit=netbox-discovery-manual --collect /usr/local/bin/netbox-discovery run
```

Acompanhar:

```bash
journalctl -fu netbox-discovery-manual.service
```

## 7. Decisões do PLAN

| Decisão/Ação | Significado | Escrita |
|---|---|---|
| `READY/CREATE` | novo Device validado | somente com `--apply` |
| `READY/UPDATE_SAFE` | enriquecimento protegido | somente com `--apply` |
| `READY/REPAIR_SAFE_VM_DUPLICATE` | reparo protegido de duplicidade | após preflight |
| `READY/NOOP` | convergente ou preservado | não |
| `DELEGATED` | ownership de VM/Hypervisor | não |
| `REVIEW` | evidência insuficiente | não |
| `BLOCKED` | conflito ou write guard | não |

## 8. Autoridade dos dados

```text
Nome existente              → NetBox
Nome observado              → DNS, SNMP, ONVIF ou protocolo
VM/cluster/host             → inventário central Hypervisor
Fabricante/modelo/serial    → protocolo específico ou MIB
IP ativo                    → descoberta de rede
```

O importer não altera automaticamente o nome de um Device existente.

## 9. Serial e identidade

Fontes de maior autoridade incluem:

```text
Hikvision ISAPI / ONVIF
Printer-MIB
FibreAlliance
Dell iDRAC
Siemens S7 / EtherNet-IP / BACnet / Modbus
ENTITY-MIB
```

São rejeitados placeholders, IP, MAC, modelo, hostname e conflitos entre fontes fortes.

Campos importantes no PLAN:

```text
serial
serial_source
serial_confidence
serial_candidates
serial_rejections
serial_conflict
```

## 10. Virtualização

Configuração:

```bash
netbox-discovery hypervisor configure
```

Dry-run:

```bash
netbox-discovery hypervisor run
```

Apply:

```bash
netbox-discovery hypervisor run --apply
```

Em filiais com inventário centralizado, VMs são tratadas como `DELEGATED`; o proxy Network não cria Devices físicos duplicados para elas.

## 11. Scheduler Network

Habilitar:

```bash
netbox-discovery scheduler enable
```

Status:

```bash
netbox-discovery scheduler status
```

Desabilitar:

```bash
netbox-discovery scheduler disable
```

A execução agendada usa `automation.enabled`, `automation.apply` e `automation.schedule` do `config.yml`.

Padrão seguro em configuração antiga migrada:

```yaml
automation:
  enabled: false
  apply: false
  schedule: daily
```

## 12. Scheduler Hypervisor

```bash
netbox-discovery hypervisor scheduler enable
netbox-discovery hypervisor scheduler status
netbox-discovery hypervisor scheduler disable
```

Ele também inicia o timer de auto-update como dependência.

## 13. Auditoria

Uma execução com APPLY só deve ser aceita como convergente quando apresentar:

```text
Runtime blocked: 0
Erros: 0
Assets FAIL: 0
Checks FAIL: 0
fresh PLAN sem mudança elegível inesperada
```

Warnings de preservação podem existir sem representar falha.

## 14. Caminhos

```text
Aplicação:              /opt/netbox-discovery
Configuração:           /opt/netbox-discovery/config.yml
Relatórios:             /opt/netbox-discovery/reports
Logs:                   /opt/netbox-discovery/logs
Backups de update:      /var/lib/netbox-discovery/update-backups
Lock global:            /var/lock/netbox-discovery-global.lock
Units systemd:          /etc/systemd/system
```

## 15. Política de documentação

Toda release deve atualizar a versão exata nos documentos oficiais:

```text
README.md
docs/MANUAL.md
docs/COMANDOS-RAPIDOS.md
docs/HOMOLOGACAO.md
RELEASE-NOTES.md
SECURITY.md
docs/PATCH-<VERSÃO>.md
```

O CI bloqueia publicação quando qualquer um desses documentos permanece em versão anterior.
