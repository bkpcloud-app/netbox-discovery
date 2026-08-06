# netbox-discovery 1.11.23

## Objetivo

Transformar o fechamento de uma unidade aprovada em um comando padrão do produto, sem cadeia manual extensa.

## Novo comando

```bash
netbox-discovery go-live
```

## Fluxo executado

```text
IMPORT --apply
→ AUDIT
→ PLAN
→ PLAN summary
→ convergência sem READY/CREATE, UPDATE_SAFE ou REPAIR_SAFE_VM_DUPLICATE
→ preservação da configuração operacional
→ automation.enabled=false
→ automation.apply=false
→ scheduler enable
→ validação de enabled=true e apply=false
→ status
```

## Compatibilidade

O instalador ativa `netbox-discovery-wrapper` como comando público. O wrapper delega todos os comandos existentes ao core anterior e trata somente `go-live` pelo novo módulo `modules/product/go_live.py`.

## Segurança

- exige root;
- usa somente o PLAN aprovado e o IMPORT oficial;
- não escreve REVIEW, DELEGATED ou BLOCKED;
- falha antes do scheduler quando IMPORT, AUDIT, PLAN ou convergência falham;
- força `automation.apply=false` antes de habilitar o scheduler;
- verifica o estado final;
- desabilita o scheduler se a verificação final detectar estado inseguro;
- preserva Tenant, Site, token, redes, exclusões e communities.

## Operação

```bash
netbox-discovery update run
netbox-discovery go-live
```

Resultado esperado:

```text
ATUALIZADO: 1.11.23
GO-LIVE: PASS
SCHEDULER NETWORK: ENABLED
APPLY AUTOMÁTICO: NÃO
```
