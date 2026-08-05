# Manual Operacional — netbox-discovery

**Produto:** netbox-discovery  
**Versão:** 1.11.16 — PRODUCT V1  
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

## 2. Atualização

```bash
netbox-discovery update run
netbox-discovery version
netbox-discovery check
netbox-discovery status
```

O updater consulta `stable`, valida o candidato, cria backup, preserva configurações, instala, testa e executa rollback quando necessário.

## 3. Auto-update

O instalador habilita `netbox-discovery-update.timer` com execução diária, `Persistent=true` e atraso aleatório de até 30 minutos.

Antes de cada coleta automática Network ou Hypervisor:

```text
netbox-discovery update scheduled
→ valida e instala atualização disponível
→ self-test/check
→ rollback e quarentena em falha
→ coleta com a versão instalada válida
```

Falha temporária do GitHub é registrada, mas não cancela a coleta. O updater não altera `automation.apply`.

## 4. Configuração

```bash
netbox-discovery configure
```

O assistente define tenant, tenant group, site, token, SSL, redes, exclusões, communities e automação. Ele não inicia descoberta nem escreve no NetBox.

## 5. Execução manual

Dry-run:

```bash
netbox-discovery run
```

APPLY controlado:

```bash
netbox-discovery run --apply
```

Nunca use `--apply` antes de revisar o PLAN.

## 6. Relatório nativo do PLAN

A partir da 1.11.16, não é necessário montar comandos Python para ler JSON.

Resumo do último PLAN do site configurado:

```bash
netbox-discovery plan summary
```

Listagens detalhadas:

```bash
netbox-discovery plan blocked
netbox-discovery plan review
netbox-discovery plan ready
netbox-discovery plan delegated
netbox-discovery plan all
```

Opções:

```bash
netbox-discovery plan blocked --limit 20
netbox-discovery plan summary --json
netbox-discovery plan blocked --json
```

O relatório mostra:

```text
Site
Run ID
Run status
NetBox write
arquivo PLAN
quantidade de registros
decisões e ações
motivos agrupados de BLOCKED e REVIEW
IP, nome, role, decisão, ação, motivos e diffs por registro
```

Todos esses comandos são somente leitura.

## 7. Status sem mistura histórica

```bash
netbox-discovery status
```

Na 1.11.16, quando o último RUN é dry-run, a saída informa:

```text
IMPORT: NÃO EXECUTADO NESTE RUN (dry-run)
AUDIT: NÃO EXECUTADO NESTE RUN (dry-run)
```

O status não apresenta mais IMPORT/AUDIT antigos como se pertencessem ao dry-run atual.

## 8. Execução fora da sessão SSH

```bash
UNIT="netbox-discovery-manual-$(date +%Y%m%d-%H%M%S)"
systemd-run --unit="$UNIT" --collect /usr/local/bin/netbox-discovery run
```

Acompanhar:

```bash
journalctl -fu "$UNIT.service"
```

Parar a coleta:

```bash
systemctl stop "$UNIT.service"
```

`CTRL+C` encerra somente a visualização do journal.

## 9. Schedulers

Network:

```bash
netbox-discovery scheduler enable
netbox-discovery scheduler disable
netbox-discovery scheduler status
```

Hypervisor:

```bash
netbox-discovery hypervisor scheduler enable
netbox-discovery hypervisor scheduler disable
netbox-discovery hypervisor scheduler status
```

Em proxies `network_proxy` com virtualização centralizada, o scheduler Hypervisor local permanece desabilitado.

## 10. Redes grandes

Discovery V6 divide prefixos maiores que `/24` em lotes `/24`, remove sobreposição, usa paralelismo controlado, registra progresso e informa erro por lote.

## 11. Decisões

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
- PATCH automático de nome é proibido;
- serial placeholder ou conflitante não é gravado;
- Device manual é preservado;
- VM confirmada não vira Device físico duplicado;
- write guard bloqueia impacto anormal;
- relatório do PLAN nunca altera o NetBox.

## 13. Caminhos

```text
Aplicação:              /opt/netbox-discovery
Configuração:           /opt/netbox-discovery/config.yml
Configurações por site: /opt/netbox-discovery/config/sites
Relatórios:             /opt/netbox-discovery/reports
Estado de update:       /var/lib/netbox-discovery/update-state.json
Backups de update:      /var/lib/netbox-discovery/update-backups
Lock global:            /var/lock/netbox-discovery-global.lock
```

## 14. Critérios de homologação

```text
Self-test: PASS
Check: PASS
BLOCKED: 0
WRITE GUARD: PASS
Runtime blocked: 0
Erros: 0
Assets FAIL: 0
Checks FAIL: 0
PLAN posterior convergente
```
