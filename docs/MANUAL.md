# Manual Operacional — netbox-discovery

**Produto:** netbox-discovery  
**Versão:** 1.11.18 — PRODUCT V1  
**Distribuição oficial:** `bkpcloud-app/netbox-discovery`  
**Canal de produção:** `stable`

> `CI PASS` não equivale a `LIVE PASS`. Não libere APPLY antes da revisão do PLAN.

## 1. Componentes

```text
Discovery V6:   4.6-product
Classifier V8:  5.6-product
Reconciler V5:  3.3-product
Planner V11:    5.3-product
Importer V12:   6.1-product
Auditor V11:    6.9-product
```

## 2. Atualização e validação

```bash
netbox-discovery update run
netbox-discovery version
netbox-discovery check
netbox-discovery status
```

O updater consulta `stable`, valida o candidato, cria backup, preserva configurações, instala, testa e executa rollback quando necessário.

## 3. Dry-run e relatório

```bash
netbox-discovery run
netbox-discovery plan summary
netbox-discovery plan blocked
netbox-discovery plan review
netbox-discovery plan ready
```

Todos os comandos de relatório são somente leitura.

## 4. Write guard final

O write guard é calculado uma única vez depois das políticas finais de identidade, Windows, impressoras, virtualização, OOB e colisões.

Entram no cálculo:

```text
READY/CREATE
READY/UPDATE_SAFE
READY/REPAIR_SAFE_VM_DUPLICATE
```

Não entram:

```text
READY/NOOP
REVIEW
DELEGATED
BLOCKED por política de identidade
```

## 5. Bootstrap de site pequeno

Na 1.11.18, quando a base possui menos de 50 Devices:

```text
policy = SMALL_SITE_BOOTSTRAP_ABSOLUTE_ONLY
percent_enforced = false
```

Apenas a regra percentual é adiada. Permanecem obrigatórios:

```text
CREATE: 25
UPDATE_SAFE: 50
REPAIR_SAFE_VM_DUPLICATE: 20
TOTAL: 75
```

Ao alcançar 50 Devices:

```text
policy = ABSOLUTE_AND_PERCENT
percent_enforced = true
PERCENT: 20%
```

A base mínima pode ser ajustada por:

```text
NETBOX_DISCOVERY_PERCENT_MIN_BASE
```

Não altere essa variável durante uma homologação sem registrar a decisão. O padrão é 50.

## 6. Interpretação do relatório

Exemplo de site pequeno:

```text
WRITE GUARD: PASS | elegíveis=17 | base=13 | mudanças=131%
WRITE GUARD POLÍTICA: SMALL_SITE_BOOTSTRAP_ABSOLUTE_ONLY | percentual=ADIADO | base mínima=50
```

Isso não significa APPLY automático. Significa apenas que 17 mudanças finais ficaram abaixo dos limites absolutos.

Conflitos como `DUPLICATE_DESIRED_NAME`, identidade fraca, REVIEW, DELEGATED e outros BLOCKED continuam sem escrita.

## 7. APPLY

```bash
netbox-discovery run --apply
```

Somente após confirmar:

```text
WRITE GUARD: PASS
BLOCKED analisados
READY/CREATE e READY/UPDATE_SAFE revisados
NetBox write anterior: NÃO
scheduler homologado
```

## 8. Auto-update e scheduler

Antes de cada execução automática:

```text
UPDATE PREFLIGHT → COLETA
```

O updater não altera `automation.apply`.

```bash
netbox-discovery scheduler enable
netbox-discovery scheduler disable
netbox-discovery scheduler status
```

## 9. Execução fora da sessão SSH

```bash
UNIT="netbox-discovery-manual-$(date +%Y%m%d-%H%M%S)"
systemd-run --unit="$UNIT" --collect /usr/local/bin/netbox-discovery run
journalctl -fu "$UNIT.service"
```

`CTRL+C` encerra somente a visualização.

## 10. Critérios de homologação

```text
Self-test: PASS
Check: PASS
WRITE GUARD calculado sobre decisões finais
limites absolutos preservados no bootstrap
percentual ativo em base madura
conflitos reais permanecem BLOCKED
Erros: 0
Assets FAIL: 0
Checks FAIL: 0
PLAN posterior convergente
```
