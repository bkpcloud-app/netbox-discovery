# Manual Operacional — netbox-discovery

**Produto:** netbox-discovery  
**Versão:** 1.11.15 — PRODUCT V1  
**Distribuição oficial:** `bkpcloud-app/netbox-discovery`  
**Canal de produção:** `stable`

> `CI PASS` não equivale a `LIVE PASS`. Consulte `docs/HOMOLOGACAO.md` antes de liberar APPLY automático.

## 1. Componentes

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

## 2. Atualização manual

```bash
netbox-discovery update run
```

Validação:

```bash
netbox-discovery version
netbox-discovery check
netbox-discovery status
```

O updater consulta o `stable`, valida o pacote candidato, cria backup, preserva configurações, instala, testa e executa rollback quando necessário.

## 3. Auto-update diário

O instalador habilita:

```text
netbox-discovery-update.timer
```

Política padrão:

```text
OnCalendar=daily
Persistent=true
RandomizedDelaySec=30m
```

Comandos:

```bash
netbox-discovery update scheduler status
netbox-discovery update scheduler enable
netbox-discovery update scheduler disable
```

## 4. Atualização antes de cada coleta automática

Na 1.11.15, os serviços automáticos Network e Hypervisor executam o updater antes da coleta.

Sequência efetiva:

```text
systemd inicia o serviço
→ netbox-discovery update scheduled
→ consulta a versão do canal stable
→ se houver versão superior, valida o candidato
→ cria backup
→ instala preservando configuração
→ executa self-test e check
→ em falha, executa rollback e quarentena
→ inicia a coleta com a instalação disponível
```

A etapa de update é um preflight tolerante a indisponibilidade externa:

- atualização disponível e válida: instala e segue;
- nenhuma atualização: segue imediatamente;
- GitHub indisponível: registra o erro e segue com a versão instalada;
- versão candidata inválida: rollback/quarentena e segue com a versão instalada válida;
- outro processo usando o lock global: update é adiado e a coleta respeita o mesmo lock.

Essa automação não habilita APPLY e não muda `automation.apply`.

## 5. Scheduler Network

```bash
netbox-discovery scheduler enable
netbox-discovery scheduler disable
netbox-discovery scheduler status
```

Ao habilitar, o timer de coleta e o timer de update permanecem ativos. Ao desabilitar a coleta, o update continua independente.

Fluxo sem escrita:

```text
UPDATE PREFLIGHT
→ DISCOVER
→ CLASSIFY
→ RECONCILE
→ PLAN
```

Fluxo com escrita somente quando explicitamente configurado e homologado:

```text
UPDATE PREFLIGHT
→ DISCOVER
→ CLASSIFY
→ RECONCILE
→ PLAN
→ WRITE GUARD
→ IMPORT READY
→ AUDIT
```

## 6. Scheduler Hypervisor

```bash
netbox-discovery hypervisor scheduler enable
netbox-discovery hypervisor scheduler disable
netbox-discovery hypervisor scheduler status
```

O Hypervisor usa a mesma regra de update preflight. Em proxies `network_proxy` com virtualização centralizada, o scheduler Hypervisor local deve permanecer desabilitado.

## 7. Configuração

```bash
netbox-discovery configure
```

O assistente permite definir:

- tenant e tenant group;
- site;
- token e validação SSL;
- redes CIDR;
- exclusões IP/CIDR;
- comunidades SNMP;
- automação Network.

O assistente não inicia descoberta e não escreve no NetBox.

## 8. Execução manual

Dry-run:

```bash
netbox-discovery run
```

APPLY controlado:

```bash
netbox-discovery run --apply
```

Nunca use `--apply` antes de revisar o PLAN e confirmar `BLOCKED=0`, write guard e identidade.

## 9. Execução fora da sessão SSH

```bash
UNIT="netbox-discovery-manual-$(date +%Y%m%d-%H%M%S)"
systemd-run --unit="$UNIT" --collect /usr/local/bin/netbox-discovery run
```

Acompanhar:

```bash
journalctl -fu "$UNIT.service"
```

`CTRL+C` encerra somente a visualização. Para parar a coleta:

```bash
systemctl stop "$UNIT.service"
```

## 10. Redes grandes

Discovery V6:

- divide prefixos maiores que `/24` em lotes `/24`;
- elimina sobreposição duplicada;
- usa paralelismo controlado;
- registra progresso;
- informa timeout e erro por lote;
- mantém descoberta SNMP read-only;
- não depende da sessão SSH.

## 11. Decisões e escrita

```text
READY/CREATE       → escreve somente com --apply
READY/UPDATE_SAFE  → escreve somente com --apply
READY/NOOP         → não altera
DELEGATED          → não escreve
REVIEW             → não escreve
BLOCKED            → não escreve
```

## 12. Segurança de identidade

- nome existente no NetBox é autoridade;
- PATCH automático de `name` é proibido;
- serial placeholder ou conflitante não é gravado;
- Device manual é preservado;
- VM confirmada não vira Device físico duplicado;
- primary IP existente pode ser preservado por política;
- write guard bloqueia impacto anormal;
- auditoria posterior deve ter `Assets FAIL=0` e `Checks FAIL=0` para LIVE PASS.

## 13. Status esperado

```bash
netbox-discovery status
```

Campos principais:

```text
Versão instalada
Canal de update
Auto-update timer
Tenant/Site
Network scheduler
APPLY
Último RUN
PLAN
WRITE GUARD
IMPORT
AUDIT
Inventário de virtualização
```

## 14. Caminhos

```text
Aplicação:             /opt/netbox-discovery
Configuração:          /opt/netbox-discovery/config.yml
Configurações por site:/opt/netbox-discovery/config/sites
Relatórios:            /opt/netbox-discovery/reports
Estado de update:      /var/lib/netbox-discovery/update-state.json
Backups de update:     /var/lib/netbox-discovery/update-backups
Lock global:           /var/lock/netbox-discovery-global.lock
Unidades systemd:      /etc/systemd/system
```

## 15. Homologação operacional

Uma implantação só deve ser considerada concluída quando apresentar:

```text
Self-test: PASS
Check: PASS
BLOCKED: 0
WRITE GUARD: PASS
Runtime blocked: 0
Erros: 0
Assets FAIL: 0
Checks FAIL: 0
novo PLAN sem mudança elegível inesperada
```
