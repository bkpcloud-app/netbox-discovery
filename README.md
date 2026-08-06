# netbox-discovery

Produto BKPCLOUD para descoberta, classificação, reconciliação e inventário seguro de infraestrutura no NetBox.

**Versão atual:** 1.11.23 — PRODUCT V1  
**Distribuição:** `bkpcloud-app/netbox-discovery`  
**Canal de produção:** `stable`

## Pipeline atual

```text
DISCOVER V6 / 4.6-product
→ CLASSIFY V8 / 5.6-product
→ RECONCILE V5 / 3.3-product
→ PLAN V11 / 5.3-product
→ IMPORT V12 / 6.1-product
→ AUDIT V11 / 6.9-product
```

`netbox-discovery run` é read-only. Escrita no NetBox só ocorre com `netbox-discovery run --apply` e permanece protegida por PLAN, write guard, preflight, identidade e auditoria.

## GO-LIVE nativo

A 1.11.23 adiciona o comando operacional padrão:

```bash
netbox-discovery go-live
```

Ele executa, em uma única ação nativa:

```text
IMPORT --apply
→ AUDIT
→ novo PLAN
→ validação de convergência
→ força automation.apply=false
→ habilita o scheduler Network
→ valida o estado final
```

Se qualquer etapa falhar, o fluxo para antes da habilitação do scheduler. O resultado aprovado termina com scheduler habilitado e `APPLY=NÃO`.

## Preflight global de MAC

A 1.11.20 passou a verificar todos os MACs finais do PLAN contra a tabela global `dcim/mac-addresses` antes da primeira escrita.

```text
MAC livre ou sem vínculo
→ elegível conforme as demais políticas

MAC já vinculada à interface do mesmo Device existente
→ preservada

MAC vinculada a outro Device, VM ou objeto
→ BLOCKED/NOOP no PLAN
→ bloqueada novamente pelo preflight do IMPORT
```

A 1.11.21 corrigiu o preflight legado para usar o proprietário real da interface e não bloquear um `READY/NOOP` já reconciliado.

A 1.11.22 corrige também o runtime final. Antes de criar ou localizar interface por nome, o Importer resolve a MAC global:

```text
MAC já vinculada à interface do mesmo Device
→ reutiliza a interface existente
→ não cria interface duplicada
→ ensure_mac preserva o vínculo

MAC vinculada a outro Device, VM ou objeto
→ bloqueia antes de qualquer criação

MAC ausente ou sem vínculo
→ segue o fluxo normal de interface
```

Isso cobre recuperação de APPLY parcial mesmo quando o nome da interface live diverge do nome atual do `spec`.

A checagem ocorre em camadas independentes:

1. Planner V11, antes do write guard;
2. preflight legado por owner real;
3. Importer V12, antes da primeira escrita;
4. runtime do Importer V2, antes da criação de interface por nome.

Se a consulta global de MAC estiver indisponível no APPLY, o processo falha fechado.

## Identidade estável obrigatória para novos Devices

A 1.11.19 adicionou uma proteção final independente de role ou classe:

```text
novo READY/CREATE + discovery_uid WEAK
→ REVIEW/NOOP
→ nenhuma interface ou intenção de IP é escrita
```

Novos Devices precisam chegar ao PLAN com identidade estável, normalmente:

```text
SERIAL:<fabricante>:<serial>
MGMT-MAC:<mac>
```

## Write guard final e bootstrap de sites pequenos

O write guard é calculado uma única vez, depois de todas as políticas finais do Planner.

Sites com menos de 50 Devices usam:

```text
SMALL_SITE_BOOTSTRAP_ABSOLUTE_ONLY
```

Os limites absolutos continuam obrigatórios; apenas o percentual fica adiado até a base mínima.

## Relatório nativo do PLAN

```bash
netbox-discovery plan summary
netbox-discovery plan blocked
netbox-discovery plan review
netbox-discovery plan ready
netbox-discovery plan delegated
```

Todos são somente leitura.

## Instalação e atualização

```bash
netbox-discovery update run
netbox-discovery version
netbox-discovery check
netbox-discovery status
```

## Auto-update e schedulers

```bash
netbox-discovery scheduler enable
netbox-discovery scheduler disable
netbox-discovery scheduler status
```

O updater não modifica `automation.apply`. O `go-live` força `automation.apply=false` antes de habilitar o scheduler.

## Segurança

- nenhuma exclusão automática de Device;
- nenhum PATCH automático de nome;
- nome existente no NetBox é preservado;
- identidade `WEAK` nunca cria novo Device;
- MAC vinculada a outro objeto nunca é reassociada automaticamente;
- MAC já pertencente ao mesmo Device reutiliza a interface live;
- interface não é criada antes de resolver ownership de MAC;
- `REVIEW`, `DELEGATED` e `BLOCKED` nunca escrevem;
- limites absolutos permanecem ativos durante bootstrap;
- `go-live` habilita o scheduler somente com `APPLY=NÃO` confirmado.

## Documentação

- `docs/MANUAL.md`;
- `docs/COMANDOS-RAPIDOS.md`;
- `docs/HOMOLOGACAO.md`;
- `docs/NOVA-UNIDADE-DOIS-PASSOS.md`;
- `RELEASE-NOTES.md`;
- `SECURITY.md`;
- `docs/PATCH-1.11.23.md`.
