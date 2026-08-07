# Manual Operacional — netbox-discovery

**Produto:** netbox-discovery  
**Versão:** 1.11.34 — PRODUCT V1  
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

O updater **não altera `automation.apply`** e não transforma uma unidade read-only em unidade de escrita.

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

A tabela `dcim/mac-addresses` é global no NetBox. O produto valida MACs antes da escrita e novamente no runtime.

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

Um APPLY anterior pode ter criado Device e interface antes de falhar. O próximo PLAN pode apresentar `READY/NOOP` com a MAC já atribuída à interface live do mesmo Device. O produto aceita esse estado, reutiliza a interface live e não transfere automaticamente uma MAC entre Devices ou entre Device e VM.

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

Sites com menos de 50 Devices usam política de bootstrap com limites absolutos. Sites praticamente vazios possuem limite inicial específico para CREATE; sites estabelecidos voltam a aplicar também o percentual.

As proteções de identidade, MAC, preflight e TOTAL continuam obrigatórias.

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

O estágio de importação também pode ser executado de forma dirigida com:

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

A escrita agendada depende de `automation.apply`:

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
netbox-discovery hypervisor run --compare
netbox-discovery hypervisor scheduler status
```

O Hypervisor usa a origem de virtualização como autoridade de contexto. Site não é inferido pelo nome da VM. Host standalone pode ter Cluster nulo. Não existe DELETE automático.

## 15. Critérios de homologação

```text
Self-test: PASS
Check: PASS
endpoint NetBox sem :8080
nenhum novo Device com identidade WEAK em READY
nenhum READY com MAC pertencente a outro objeto
nenhuma interface criada antes da resolução de ownership da MAC
preflight global antes da escrita
WRITE GUARD calculado sobre decisões finais
Erros: 0
AUDIT concluído
scheduler no modo planejado para a unidade
```

## 16. Ponto de retomada — estado atual do projeto

Esta seção existe para permitir que uma revisão futura comece somente pelo link do repositório, sem depender do histórico de conversa. Antes de alterar o produto, ler esta seção, `RELEASE-NOTES.md`, `docs/HOMOLOGACAO.md` e a nota de patch da versão atual.

### Estado técnico confirmado

```text
Versão de referência: 1.11.34
Canal consumido pelos agentes: stable
Branch padrão exibido pelo GitHub: main
Endpoint NetBox: https://inventory.bkpcloud.app.br
Endpoint legado :8080: proibido para configuração nova
Network: instalação direta + scheduler + run --apply documentados
Hypervisor: pipeline multi-contexto validado em produção com 12 contextos e 53 reclassificações seguras
Hypervisor audit multi-contexto: PASS
Placement após APPLY validado sem MISMATCH e sem MISSING
DELETE automático: desabilitado
```

Na validação Hypervisor de produção anterior à regra específica de réplica, cinco VMs FVI com sufixo `_replica` ficaram protegidas por divergência de UUID. A 1.11.30 adicionou uma exceção estreita para VMware `_replica` com nome único, permitindo refresh do UUID e herança do Site autoritativo sem relaxar conflitos de outras VMs. Não registrar como `LIVE PASS` pós-1.11.30 sem nova evidência de execução.

### Decisões operacionais vigentes

```text
Site de VM vem do contexto autoritativo do hypervisor/parent, nunca do nome da VM.
Cluster só é preenchido quando existe Cluster real na origem; host standalone pode ficar sem Cluster.
Network e Hypervisor são pipelines independentes.
REVIEW/DELEGATED/BLOCKED não escrevem.
Não apagar Devices/VMs automaticamente.
Não pedir novamente diagnóstico de HTTPS/443: o endpoint público já está definido.
Instalação nova comum usa o comando único da seção 1 e não precisa de go-live depois.
GO-LIVE fica reservado ao fluxo controlado com revisão prévia.
```

### Próxima etapa funcional

**NetBox → Zabbix** é o próximo eixo do projeto. Antes de criar código novo, verificar se já existe módulo Zabbix no repositório. A integração deve começar em dry-run/auditoria, usando NetBox como fonte de verdade para inventário e metadados. Não habilitar DELETE automático na primeira versão.

Mapeamentos a validar antes da escrita no Zabbix:

```text
Tenant
Site
Device/VM
Primary IP
Role/Platform
Site → Zabbix Proxy ou Proxy Group
Tags
Host Groups
Templates
```

Credenciais/API do Zabbix não devem ser versionadas nem expostas em documentação pública.

## 17. Regra obrigatória de documentação e promoção

**Toda release** deve atualizar no mesmo PR:

```text
VERSION
netbox-discovery/VERSION
README.md
docs/MANUAL.md
docs/COMANDOS-RAPIDOS.md
docs/HOMOLOGACAO.md
RELEASE-NOTES.md
SECURITY.md
docs/PATCH-<VERSÃO>.md
```

O CI deve comparar a **versão exata** desses documentos com `VERSION`. Não basta existir `1.11.` em algum ponto do arquivo.

Fluxo de promoção:

```text
branch de trabalho
→ PR para stable
→ CI PASS
→ merge stable
→ sincronizar main com o mesmo commit de stable
→ confirmar VERSION e README em main
```

`stable` é o canal técnico de produção. `main` é a página padrão do GitHub. Os dois devem terminar no mesmo conteúdo após cada release para que o manual visto no navegador seja o mesmo manual consumido operacionalmente.

## 18. Higiene do repositório

Não manter arquivo apenas porque ele existia em versão antiga. Um arquivo só permanece quando houver pelo menos uma destas razões:

```text
é usado pelo runtime atual;
é importado por um componente atual;
é exigido por migração/compatibilidade suportada;
é executado pelo CI/regressões;
é documentação operacional vigente;
é evidência histórica ainda verificada por regressão.
```

Na 1.11.34 foram removidos artefatos comprovadamente obsoletos e não referenciados: `SHA256SUMS`, `netbox-discovery/docs/PRODUCT-V1.md` e `netbox-discovery/workflow.yml`. O exemplo `config.yml.example` foi corrigido para HTTPS/443.

Os módulos versionados antigos não devem ser apagados em massa: o Planner, Importer, Auditor e outras camadas atuais ainda reutilizam módulos anteriores e a suíte de regressão depende dessa cadeia. A remoção deles exige refatoração explícita e CI completo, não limpeza por aparência.

Branches de trabalho devem ser temporárias. A política desejada é manter `main`, `stable` e somente branches realmente ativas; branches já incorporadas não fazem parte do produto em execução.
