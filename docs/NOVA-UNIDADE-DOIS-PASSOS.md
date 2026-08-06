# Nova unidade — fluxo operacional em dois passos

Este procedimento é o padrão para iniciar um cliente/site novo no `netbox-discovery`.

## PASSO 1 — Preparar e revisar

Na instalação zerada, instalar e executar o assistente:

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

Durante o `init`, informar Tenant, Site, token, redes, exclusões e communities. Não habilitar automação nessa etapa.

O PASSO 1 é somente leitura para o inventário. O `init` pode criar ou vincular apenas Tenant, Tenant Group e Site.

Enviar a saída para revisão. Não executar o PASSO 2 sem aprovação.

## PASSO 2 — Atualizar e colocar em produção

Depois da aprovação do PLAN, são somente dois comandos padrão:

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

## Resultado esperado

```text
ATUALIZADO: 1.11.23
IMPORT: erros 0
AUDIT: PASS
CONVERGÊNCIA: PASS
SCHEDULER NETWORK: ENABLED
APPLY AUTOMÁTICO: NÃO
GO-LIVE: PASS
```

O scheduler Hypervisor permanece fora deste fluxo.

## Segurança

- não colocar token ou community diretamente na linha de comando;
- manter o scheduler desabilitado durante a revisão;
- o GO-LIVE escreve somente registros `READY` aprovados;
- mudanças READY pendentes após o novo PLAN bloqueiam a conclusão;
- o scheduler somente termina habilitado com `APPLY=NÃO` confirmado.
