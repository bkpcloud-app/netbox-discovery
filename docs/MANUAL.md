# Manual Operacional — netbox-discovery

**Produto:** netbox-discovery  
**Versão:** 1.11.33 — PRODUCT V1  
**Distribuição oficial:** `bkpcloud-app/netbox-discovery`  
**Canal de produção:** `stable`

> `CI PASS` não equivale a `LIVE PASS`. Use escrita automática somente em unidades em que esse modo operacional foi aprovado.

## 1. Instalação do zero — unidade nova com ativação imediata

Para uma unidade nova, em servidor limpo, quando a intenção é instalar, configurar, habilitar o scheduler e executar a primeira descoberta imediatamente, o comando operacional oficial é:

```bash
curl -fsSL https://raw.githubusercontent.com/bkpcloud-app/netbox-discovery/stable/install-from-github.sh -o /tmp/netbox-discovery-install.sh && bash /tmp/netbox-discovery-install.sh && netbox-discovery init && netbox-discovery check && netbox-discovery scheduler enable && netbox-discovery run --apply
```

Executar como `root`.

Durante `netbox-discovery init`, informar:

```text
Cliente/Tenant: cliente da unidade, por exemplo MIZU
Tenant Group: grupo do cliente, quando aplicável, por exemplo POLIMIX
Site: código da unidade, por exemplo FVI
NetBox: fixo em https://inventory.bkpcloud.app.br
Token: token válido do NetBox
SSL: conforme a política do ambiente
Redes CIDR: todas as redes que devem ser descobertas nessa unidade
Exclusões: IPs/CIDRs que não devem ser varridos
SNMP: habilitar quando usado
Communities: communities SNMP da unidade
Habilitar execução automática: SIM
Agenda systemd OnCalendar: daily, salvo necessidade diferente
Permitir IMPORT automático: SIM, quando a unidade deve escrever automaticamente no NetBox
Salvar configuração: SIM
Testar conexão com NetBox: SIM
```

O `init` apenas grava a configuração. Depois dele, a mesma linha continua automaticamente com:

```text
CHECK
→ habilitação do scheduler Network
→ DISCOVER imediato
→ CLASSIFY
→ RECONCILE
→ PLAN
→ IMPORT --apply dos registros READY
→ AUDIT
```

Portanto, nesse modo não é necessário esperar a execução da madrugada para a primeira coleta.

Com `automation.enabled=true` e `automation.apply=true`, as execuções agendadas seguintes voltam a descobrir a unidade e podem gravar registros `READY` no NetBox. `REVIEW`, `DELEGATED` e `BLOCKED` continuam sem escrita.

### Validação após a instalação

```bash
netbox-discovery version
netbox-discovery check
netbox-discovery status
netbox-discovery scheduler status
```

Resultado operacional esperado:

```text
CONFIG: OK
TENANT: <cliente>
SITE: <site>
NETBOX URL: https://inventory.bkpcloud.app.br
Scheduler Network: habilitado
Primeiro RUN: concluído sem erro
```

## 2. Instalação controlada com revisão antes da escrita

Quando a unidade exigir revisão humana do PLAN antes da primeira escrita, usar o procedimento documentado em `docs/NOVA-UNIDADE-DOIS-PASSOS.md`. Nesse fluxo, o primeiro `run` é dry-run e o GO-LIVE ocorre somente depois da aprovação.

## 3. Componentes

```text
Discovery V6:   4.6-product
Classifier V8:  5.6-product
Reconciler V5:  3.3-product
Planner V11:    5.3-product
Importer V12:   6.1-product
Auditor V11:    6.9-product
```

## 4. Atualização e validação

```bash
netbox-discovery update run
netbox-discovery version
netbox-discovery check
netbox-discovery status
```

O updater consulta `stable`, valida o candidato, cria backup, preserva configurações, instala, testa e executa rollback quando necessário.

O endpoint oficial do NetBox é:

```text
https://inventory.bkpcloud.app.br
```

Não usar `:8080`.

## 5. Dry-run e relatório

```bash
netbox-discovery run
netbox-discovery plan summary
netbox-discovery plan blocked
netbox-discovery plan review
netbox-discovery plan ready
```

Todos os comandos de relatório são somente leitura.

## 6. Identidade estável obrigatória para novos Devices

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

## 7. Propriedade global de MAC

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

## 8. Write guard final

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

## 9. Bootstrap de site pequeno

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

## 10. GO-LIVE controlado

Depois da revisão e aprovação do PLAN, o comando operacional é:

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

Esse é o modo controlado. Ele termina com scheduler habilitado e `APPLY=NÃO`.

Resultado esperado:

```text
GO-LIVE: PASS
SCHEDULER NETWORK: ENABLED
APPLY AUTOMÁTICO: NÃO
```

## 11. APPLY manual

```bash
netbox-discovery run --apply
```

Executa o pipeline completo com escrita dos registros `READY` e auditoria. É o comando usado na instalação direta da seção 1.

O comando abaixo continua disponível para operação dirigida do estágio de importação:

```bash
netbox-discovery import --apply
```

## 12. Falha de APPLY

Se um APPLY terminar com erro:

```text
não repetir imediatamente
recalcular o PLAN contra o estado atual
revisar se houve Device, interface ou IP parcial
```

Falha depois de `PREFLIGHT: OK` deve ser tratada como possível escrita parcial.

## 13. Auto-update e scheduler

```bash
netbox-discovery scheduler enable
netbox-discovery scheduler disable
netbox-discovery scheduler status
```

O serviço agendado executa a atualização `stable` antes da coleta e depois chama o `scheduled-run`.

A escrita noturna depende de `automation.apply`:

```text
automation.apply=false → coleta/PLAN sem escrita
automation.apply=true  → coleta/PLAN/IMPORT/AUDIT conforme proteções do produto
```

## 14. Hypervisor

O scheduler Network e o scheduler Hypervisor são independentes. Instalar uma unidade de rede não habilita automaticamente coleta de hypervisor.

Comandos:

```bash
netbox-discovery hypervisor check
netbox-discovery hypervisor run
netbox-discovery hypervisor run --apply
netbox-discovery hypervisor scheduler status
```

## 15. Critérios de homologação

```text
Self-test: PASS
Check: PASS
endpoint NetBox sem :8080
nenhum novo Device com identidade WEAK em READY
nenhum READY com MAC pertencente a outro objeto
READY/NOOP parcial reutiliza a interface live por MAC
nenhuma interface é criada antes da resolução de ownership da MAC
MAC repetida no mesmo registro não cria interface duplicada
preflight global de IP e MAC antes da escrita
WRITE GUARD calculado sobre decisões finais
Erros: 0
AUDIT concluído
scheduler no modo planejado para a unidade
```
