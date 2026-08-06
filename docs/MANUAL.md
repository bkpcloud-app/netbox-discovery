# Manual Operacional — netbox-discovery

**Produto:** netbox-discovery  
**Versão:** 1.11.23 — PRODUCT V1  
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

```text
existing_device_id ausente
+ decision=READY
+ action=CREATE
+ discovery_uid iniciado por WEAK:
→ REVIEW/NOOP
```

Identidades normalmente aceitas:

```text
SERIAL:<fabricante>:<serial>
MGMT-MAC:<mac>
```

## 5. Propriedade global de MAC

A tabela `dcim/mac-addresses` é global no NetBox. O produto valida MACs em quatro pontos:

```text
PLAN V11
→ conflito vira BLOCKED/NOOP antes do write guard

preflight legado
→ valida owner real da dcim.interface

IMPORT V12
→ repete a consulta global antes da primeira escrita

runtime Importer V2
→ resolve MAC antes de procurar/criar interface por nome
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

Um APPLY anterior pode ter criado Device e interface antes de falhar. O próximo PLAN pode apresentar:

```text
READY/NOOP
existing_device_id preenchido
MAC já atribuída à interface live desse mesmo Device
```

A 1.11.21 corrigiu o preflight para aceitar esse estado quando o owner real é o mesmo Device.

A 1.11.22 corrige o runtime final:

```text
1. normaliza a MAC do spec;
2. consulta dcim/mac-addresses;
3. resolve a dcim.interface vinculada;
4. compara interface.device.id com o Device reconciliado;
5. reutiliza a interface live, mesmo que o nome seja diferente;
6. somente se não houver vínculo segue o fluxo por nome.
```

Assim, o Importer não cria uma segunda interface e só depois descobre que a MAC já estava na interface anterior.

O produto nunca transfere automaticamente uma MAC entre Devices ou entre Device e VM.

## 6. Write guard final

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
BLOCKED
```

## 7. Bootstrap de site pequeno

Quando a base possui menos de 50 Devices:

```text
policy = SMALL_SITE_BOOTSTRAP_ABSOLUTE_ONLY
percent_enforced = false
```

Permanecem obrigatórios:

```text
CREATE: 25
UPDATE_SAFE: 50
REPAIR_SAFE_VM_DUPLICATE: 20
TOTAL: 75
```

## 8. GO-LIVE padrão

Depois da revisão e aprovação do PLAN, o comando operacional oficial é:

```bash
netbox-discovery go-live
```

Ele executa automaticamente:

```text
IMPORT --apply
→ AUDIT
→ novo PLAN e summary
→ validação de convergência
→ automation.enabled=false e automation.apply=false
→ habilitação do scheduler Network
→ validação final de enabled=true e apply=false
→ status
```

O uso manual de uma cadeia longa de comandos não é necessário.

O fluxo falha fechado. Se IMPORT, AUDIT, PLAN, convergência ou validação final falhar, ele não conclui o GO-LIVE. Se detectar estado inseguro após habilitar o timer, desabilita o scheduler antes de encerrar com erro.

Resultado esperado:

```text
GO-LIVE: PASS
SCHEDULER NETWORK: ENABLED
APPLY AUTOMÁTICO: NÃO
```

## 9. APPLY manual excepcional

```bash
netbox-discovery import --apply
```

Usar somente para diagnóstico ou operação dirigida. No fluxo normal de unidade nova, usar `netbox-discovery go-live`.

## 10. Falha de APPLY

Se um APPLY terminar com erro:

```text
não repetir imediatamente
manter scheduler desabilitado
recalcular o PLAN contra o estado atual
revisar se houve Device, interface ou IP parcial
```

Falha depois de `PREFLIGHT: OK` deve ser tratada como possível escrita parcial.

## 11. Auto-update e scheduler

```bash
netbox-discovery scheduler enable
netbox-discovery scheduler disable
netbox-discovery scheduler status
```

O updater não altera `automation.apply`. O GO-LIVE força `automation.apply=false` antes da habilitação final.

## 12. Critérios de homologação

```text
Self-test: PASS
Check: PASS
nenhum novo Device com identidade WEAK em READY
nenhum READY com MAC pertencente a outro objeto
READY/NOOP parcial reutiliza a interface live por MAC
nenhuma interface é criada antes da resolução de ownership da MAC
MAC repetida no mesmo registro não cria interface duplicada
preflight global de IP e MAC antes da escrita
WRITE GUARD calculado sobre decisões finais
Erros: 0
PLAN posterior convergente
scheduler habilitado com APPLY=NÃO
```
