# Manual Operacional — netbox-discovery

**Produto:** netbox-discovery  
**Versão:** 1.11.21 — PRODUCT V1  
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

## 5. Propriedade global de MAC

A tabela `dcim/mac-addresses` é global no NetBox. O produto valida os MACs presentes nas interfaces finais do PLAN:

```text
PLAN V11
→ verifica propriedade global de cada MAC
→ conflito vira BLOCKED/NOOP
→ write guard calcula somente os restantes

IMPORT legado corrigido
→ valida o proprietário real da dcim.interface
→ não depende apenas de inferir a interface pelo IP do spec

IMPORT V12 --apply
→ repete a consulta global antes da primeira escrita
→ qualquer conflito ou falha de consulta bloqueia o lote antes de criar objetos
```

Regras:

```text
MAC sem objeto ou sem atribuição                 → permitido
MAC na interface do mesmo existing_device_id    → preservado
MAC em interface de outro Device                → bloqueado
MAC em virtualization.vminterface/outro objeto  → bloqueado
MAC duplicado na tabela global                   → bloqueado
owner da interface não resolvido                 → bloqueado
```

### Recuperação de APPLY parcial

Quando um APPLY anterior criou o Device e a interface antes de falhar, o próximo PLAN pode apresentar:

```text
READY/NOOP
existing_device_id preenchido
MAC já atribuída à interface live desse mesmo Device
```

Nesse caso, a 1.11.21 consulta a `dcim.interface` e compara seu proprietário real com o Device reconciliado. Se forem iguais, o preflight passa. Se forem diferentes, permanece bloqueado.

Uma mesma MAC repetida em mais de um `spec` do mesmo registro é avaliada apenas uma vez, evitando mensagens duplicadas.

O produto nunca transfere automaticamente uma MAC entre Devices ou entre Device e VM.

## 6. Write guard final

O write guard é calculado uma única vez depois das políticas finais de identidade, Windows, impressoras, virtualização, OOB, colisões, identidade estável e propriedade global de MAC.

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
BLOCKED por política de identidade ou MAC
```

## 7. Bootstrap de site pequeno

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

## 8. Interpretação do relatório

Exemplo de site pequeno:

```text
WRITE GUARD: PASS | elegíveis=13 | base=14 | mudanças=93%
WRITE GUARD POLÍTICA: SMALL_SITE_BOOTSTRAP_ABSOLUTE_ONLY | percentual=ADIADO | base mínima=50
```

Isso não significa APPLY automático. Significa apenas que as mudanças finais ficaram abaixo dos limites absolutos e passaram pelas políticas de identidade e propriedade global de MAC.

Conflitos como `DUPLICATE_DESIRED_NAME`, identidade fraca, MAC já pertencente a outro objeto, REVIEW, DELEGATED e outros BLOCKED continuam sem escrita.

## 9. APPLY

```bash
netbox-discovery import --apply
```

Somente após confirmar:

```text
WRITE GUARD: PASS
nenhum READY/CREATE com discovery_uid WEAK
nenhum READY com MAC pertencente a outro objeto
READY/NOOP parcial com owner real confirmado
BLOCKED analisados
READY/CREATE e READY/UPDATE_SAFE revisados
scheduler homologado
```

## 10. Falha de APPLY

Se um APPLY terminar com erro:

```text
não repetir o mesmo comando imediatamente
manter scheduler desabilitado
recalcular o PLAN contra o estado atual do NetBox
revisar READY/BLOCKED novamente
```

O relatório de IMPORT deve ser tratado como evidência de possível escrita parcial quando a falha ocorreu depois de `PREFLIGHT: OK`.

## 11. Auto-update e scheduler

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

## 12. Execução fora da sessão SSH

```bash
UNIT="netbox-discovery-manual-$(date +%Y%m%d-%H%M%S)"
systemd-run --unit="$UNIT" --collect /usr/local/bin/netbox-discovery run
journalctl -fu "$UNIT.service"
```

`CTRL+C` encerra somente a visualização.

## 13. Critérios de homologação

```text
Self-test: PASS
Check: PASS
nenhum novo Device com identidade WEAK em READY
nenhum READY com MAC pertencente a outro objeto
READY/NOOP parcial permitido somente quando interface owner = Device reconciliado
MAC repetida no mesmo registro avaliada uma vez
preflight global de IP e MAC antes da primeira escrita
WRITE GUARD calculado sobre decisões finais
limites absolutos preservados no bootstrap
percentual ativo em base madura
conflitos reais permanecem BLOCKED
Erros: 0
Assets FAIL: 0
Checks FAIL: 0
PLAN posterior convergente
```
