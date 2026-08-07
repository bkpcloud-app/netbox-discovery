# Nova unidade — instalação direta e fluxo controlado

Este documento reúne os dois modos suportados para iniciar um cliente/site novo no `netbox-discovery`.

## MODO A — instalação do zero com ativação imediata

Use quando a unidade já pode entrar em produção com descoberta e escrita automática.

Executar como `root`:

```bash
curl -fsSL https://raw.githubusercontent.com/bkpcloud-app/netbox-discovery/stable/install-from-github.sh -o /tmp/netbox-discovery-install.sh && bash /tmp/netbox-discovery-install.sh && netbox-discovery init && netbox-discovery check && netbox-discovery scheduler enable && netbox-discovery run --apply
```

Durante o `init`, informar:

```text
Cliente/Tenant
Tenant Group, quando aplicável
Site
Token do NetBox
Redes CIDR
Exclusões
SNMP e communities
Habilitar execução automática: SIM
Agenda: daily, salvo exceção
Permitir IMPORT automático: SIM
Salvar: SIM
Testar NetBox: SIM
```

NetBox oficial:

```text
https://inventory.bkpcloud.app.br
```

Não usar `:8080`.

A mesma linha executa:

```text
instalação
→ init
→ check
→ scheduler enable
→ DISCOVER
→ CLASSIFY
→ RECONCILE
→ PLAN
→ IMPORT --apply dos READY
→ AUDIT
```

A primeira varredura ocorre imediatamente. Não é necessário aguardar o timer da madrugada.

Com `automation.apply=true`, as execuções agendadas seguintes também podem aplicar automaticamente os registros `READY`. `REVIEW`, `DELEGATED` e `BLOCKED` permanecem sem escrita.

### Validação

```bash
netbox-discovery version
netbox-discovery check
netbox-discovery status
netbox-discovery scheduler status
```

## MODO B — fluxo controlado com revisão do PLAN

Use quando a unidade precisa de aprovação humana antes da primeira escrita.

### PASSO 1 — preparar e revisar

```bash
curl -fsSL https://raw.githubusercontent.com/bkpcloud-app/netbox-discovery/stable/install-from-github.sh -o /tmp/netbox-discovery-install.sh && bash /tmp/netbox-discovery-install.sh
netbox-discovery init
netbox-discovery scheduler disable
netbox-discovery check
netbox-discovery run
netbox-discovery plan summary
netbox-discovery plan ready --limit 200
netbox-discovery plan review --limit 200
netbox-discovery plan blocked --limit 200
netbox-discovery status
```

Durante o `init`, informar Tenant, Site, token, redes, exclusões e communities. Não habilitar IMPORT automático nessa etapa.

O PASSO 1 é somente leitura para o inventário. Enviar o PLAN para revisão.

### PASSO 2 — atualizar e colocar em produção

Depois da aprovação do PLAN:

```bash
netbox-discovery update run
netbox-discovery go-live
```

O `go-live` executa internamente:

```text
IMPORT --apply
→ AUDIT
→ novo PLAN e summary
→ validação de convergência
→ preservação de Tenant, Site, token, redes, exclusões e communities
→ automation.apply=false
→ scheduler Network enable
→ validação final de enabled=true e apply=false
→ status
```

`REVIEW`, `BLOCKED` e `DELEGATED` nunca são escritos.

Se IMPORT, AUDIT, PLAN ou convergência falhar, o scheduler não é habilitado. Se a validação final detectar estado inseguro, o scheduler é desabilitado antes do erro.

### Resultado esperado do modo controlado

```text
IMPORT: erros 0
AUDIT: PASS
CONVERGÊNCIA: PASS
SCHEDULER NETWORK: ENABLED
APPLY AUTOMÁTICO: NÃO
GO-LIVE: PASS
```

## Scheduler Hypervisor

O scheduler Hypervisor permanece independente dos dois fluxos acima. Instalação de uma unidade Network não habilita automaticamente virtualização.

## Segurança

- não colocar token ou community diretamente na linha de comando;
- usar o modo direto somente quando escrita automática estiver aprovada para a unidade;
- no modo controlado, manter scheduler/auto-apply desabilitados durante a revisão;
- somente registros `READY` são elegíveis para escrita;
- `REVIEW`, `DELEGATED` e `BLOCKED` não escrevem;
- mudanças pendentes após um APPLY devem ser analisadas antes de repetição cega.
