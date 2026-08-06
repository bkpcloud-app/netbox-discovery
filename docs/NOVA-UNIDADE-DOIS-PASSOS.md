# Nova unidade — fluxo operacional em dois passos

Este procedimento é o padrão para iniciar um cliente/site novo em uma instalação zerada do `netbox-discovery`.

Objetivos:

- evitar ciclos repetidos de comando, análise e novo comando;
- manter toda a preparação em uma única execução;
- impedir escrita de inventário antes da revisão humana do PLAN;
- aplicar, auditar, validar convergência e habilitar o scheduler em uma segunda execução única;
- salvar evidência completa em `/root`.

## Regra operacional

```text
PASSO 1
instala/atualiza
→ configura Tenant/Site/redes/credenciais
→ cria somente a estrutura base Tenant/Site no NetBox
→ mantém o scheduler Network desabilitado
→ executa CHECK + pipeline read-only
→ gera PLAN completo e relatório para revisão

REVISÃO HUMANA
→ analisar READY, REVIEW, BLOCKED e write guard
→ autorizar ou não o APPLY

PASSO 2
IMPORT --apply
→ AUDIT
→ novo PLAN
→ valida convergência sem READY/CREATE, UPDATE_SAFE ou REPAIR pendente
→ habilita o scheduler Network somente se tudo passar
```

`REVIEW`, `BLOCKED` e `DELEGATED` nunca são escritos pelo PASSO 2.

---

## PASSO 1 — Preparar, coletar e gerar o PLAN

Execute como `root` na nova unidade:

```bash
set -o pipefail; LOG="/root/netbox-discovery-preparacao-$(date +%Y%m%d-%H%M%S).log"; { curl -fsSL https://raw.githubusercontent.com/bkpcloud-app/netbox-discovery/stable/install-from-github.sh -o /tmp/netbox-discovery-install.sh && bash /tmp/netbox-discovery-install.sh && netbox-discovery init && netbox-discovery scheduler disable && netbox-discovery check && netbox-discovery run && netbox-discovery plan summary && netbox-discovery plan ready --limit 200 && netbox-discovery plan review --limit 200 && netbox-discovery plan blocked --limit 200 && netbox-discovery status; } 2>&1 | tee "$LOG"; RC=${PIPESTATUS[0]}; echo "RELATÓRIO: $LOG"; [ "$RC" -eq 0 ] && echo "PASSO 1: CONCLUÍDO — ENVIAR O RELATÓRIO PARA REVISÃO" || echo "PASSO 1: PAROU COM ERRO — ENVIAR O RELATÓRIO PARA DIAGNÓSTICO"
```

Durante o `netbox-discovery init`, informar:

- Cliente/Tenant;
- Tenant Group, quando aplicável;
- Site/unidade;
- token do NetBox;
- validação SSL;
- todas as redes CIDR;
- exclusões;
- comunidades SNMP, quando aplicável.

A automação pode ser respondida como `não`. Mesmo que seja marcada por engano, o comando executa `scheduler disable` antes da coleta.

### Resultado esperado

```text
CONFIG: OK
DISCOVER: concluído
RECONCILE: concluído
PLAN: gerado
NetBox write: NÃO
Network scheduler: DISABLED
RELATÓRIO: /root/netbox-discovery-preparacao-AAAAMMDD-HHMMSS.log
```

Enviar o arquivo de relatório ou a saída completa para revisão.

Não executar o PASSO 2 sem autorização.

---

## PASSO 2 — Aplicar, auditar, validar e habilitar

Executar somente depois da aprovação do PLAN:

```bash
set -o pipefail; LOG="/root/netbox-discovery-aplicacao-$(date +%Y%m%d-%H%M%S).log"; { netbox-discovery import --apply && netbox-discovery audit && netbox-discovery plan && netbox-discovery plan summary && python3 -c 'import glob,json,os,sys; files=glob.glob("/opt/netbox-discovery/reports/*-plan-*.json"); f=max(files,key=os.path.getmtime) if files else ""; p=json.load(open(f)) if f else {}; pending=[r for r in p.get("records",[]) if str(r.get("decision","")).strip()=="READY" and str(r.get("action","")).strip() in ("CREATE","UPDATE_SAFE","REPAIR_SAFE_VM_DUPLICATE")]; print("CONVERGÊNCIA: PASS" if not pending else "CONVERGÊNCIA: BLOQUEADA — %d mudança(s) READY pendente(s)"%len(pending)); sys.exit(0 if not pending else 1)' && netbox-discovery scheduler enable && netbox-discovery status; } 2>&1 | tee "$LOG"; RC=${PIPESTATUS[0]}; echo "RELATÓRIO: $LOG"; [ "$RC" -eq 0 ] && echo "PASSO 2: LIVE PASS — SCHEDULER HABILITADO" || echo "PASSO 2: PAROU COM ERRO — SCHEDULER NÃO FOI HABILITADO"
```

O uso de `&&` é obrigatório. Se IMPORT, AUDIT, PLAN ou convergência falhar, o scheduler não é habilitado.

### Resultado final esperado

```text
IMPORT: erros 0
AUDIT: PASS
Assets FAIL: 0
Checks FAIL: 0
READY/CREATE: 0
READY/UPDATE_SAFE: 0
CONVERGÊNCIA: PASS
Network scheduler: ENABLED
PASSO 2: LIVE PASS — SCHEDULER HABILITADO
```

O scheduler Hypervisor não é habilitado por este procedimento.

---

## Segurança

- não colocar token ou comunidade SNMP diretamente na linha de comando;
- o token é informado de forma oculta pelo `init`;
- o PASSO 1 não cria Devices, interfaces, IPs ou MACs de inventário;
- o `init` pode criar ou vincular somente Tenant, Tenant Group e Site;
- o PASSO 2 escreve apenas registros `READY` aprovados;
- qualquer falha interrompe a cadeia antes da habilitação do scheduler;
- manter o relatório para evidência e diagnóstico.
