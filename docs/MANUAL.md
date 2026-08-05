# Manual Operacional — netbox-discovery

**Produto:** netbox-discovery  
**Versão:** 1.11.19 — PRODUCT V1  
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

## 4. Identidade estável obrigatória para novos Devices

A última camada do Planner valida todo registro que terminou como novo `READY/CREATE`.

```text
existing_device_id ausente
+ decision=READY
+ action=CREATE
+ discovery_uid iniciado por WEAK:
→ REVIEW/NOOP
```

A proteção é independente de role e classe. Portanto, também cobre roles genéricas que não passam pelos validadores específicos, como:

```text
WINDOWS_HOST
HOST_OR_APPLIANCE
SMS_GATEWAY
```

Ao rebaixar o candidato, o Planner remove interfaces, intenções de IP, diffs e reparos do ciclo. O motivo registrado é:

```text
NEW_DEVICE_REQUIRES_STABLE_IDENTITY
```

Identidades normalmente aceitas para novos Devices:

```text
SERIAL:<fabricante>:<serial>
MGMT-MAC:<mac>
```

A regra não rebaixa Devices já existentes. Atualizações continuam submetidas à reconciliação, autoridade do NetBox e políticas de atualização segura.

## 5. Write guard final

O write guard é calculado uma única vez depois das políticas finais de identidade, Windows, impressoras, virtualização, OOB, colisões e identidade estável global.

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

## 6. Bootstrap de site pequeno

Quando a base possui menos de 50 Devices:

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

A base mínima pode ser ajustada por `NETBOX_DISCOVERY_PERCENT_MIN_BASE`. O padrão é 50.

## 7. Interpretação do relatório

Exemplo de site pequeno:

```text
WRITE GUARD: PASS | elegíveis=14 | base=13 | mudanças=108%
WRITE GUARD POLÍTICA: SMALL_SITE_BOOTSTRAP_ABSOLUTE_ONLY | percentual=ADIADO | base mínima=50
```

Isso não significa APPLY automático. Significa apenas que as mudanças finais ficaram abaixo dos limites absolutos e passaram pelas políticas de identidade.

Conflitos como `DUPLICATE_DESIRED_NAME`, identidade fraca, REVIEW, DELEGATED e outros BLOCKED continuam sem escrita.

## 8. APPLY

```bash
netbox-discovery run --apply
```

Somente após confirmar:

```text
WRITE GUARD: PASS
nenhum READY/CREATE com discovery_uid WEAK
BLOCKED analisados
READY/CREATE e READY/UPDATE_SAFE revisados
NetBox write anterior: NÃO
scheduler homologado
```

## 9. Auto-update e scheduler

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

## 10. Execução fora da sessão SSH

```bash
UNIT="netbox-discovery-manual-$(date +%Y%m%d-%H%M%S)"
systemd-run --unit="$UNIT" --collect /usr/local/bin/netbox-discovery run
journalctl -fu "$UNIT.service"
```

`CTRL+C` encerra somente a visualização.

## 11. Critérios de homologação

```text
Self-test: PASS
Check: PASS
nenhum novo Device com identidade WEAK em READY
WRITE GUARD calculado sobre decisões finais
limites absolutos preservados no bootstrap
percentual ativo em base madura
conflitos reais permanecem BLOCKED
Erros: 0
Assets FAIL: 0
Checks FAIL: 0
PLAN posterior convergente
```
