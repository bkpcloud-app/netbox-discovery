# netbox-discovery

Produto BKPCLOUD para descoberta, classificação, reconciliação e inventário seguro de infraestrutura no NetBox.

**Versão atual:** 1.11.19 — PRODUCT V1  
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

## Identidade estável obrigatória para novos Devices

A 1.11.19 adiciona uma proteção final independente de role ou classe:

```text
novo READY/CREATE + discovery_uid WEAK
→ REVIEW/NOOP
→ nenhuma interface ou intenção de IP é escrita
```

Isso impede que equipamentos identificados apenas por nome, certificado, serviço ou hash fraco sejam criados automaticamente. Novos Devices precisam chegar ao PLAN com identidade estável, normalmente:

```text
SERIAL:<fabricante>:<serial>
MGMT-MAC:<mac>
```

A regra protege inclusive roles genéricas como `WINDOWS_HOST`, `HOST_OR_APPLIANCE` e `SMS_GATEWAY`. Devices existentes não são rebaixados por essa regra; continuam sujeitos às políticas de reconciliação e atualização segura.

## Write guard final e bootstrap de sites pequenos

O write guard é calculado uma única vez, depois de todas as políticas finais do Planner, incluindo a validação de identidade estável.

Sites com menos de 50 Devices usam:

```text
SMALL_SITE_BOOTSTRAP_ABSOLUTE_ONLY
```

Nesse estágio:

- os limites absolutos de CREATE, UPDATE, REPAIR e TOTAL continuam obrigatórios;
- somente a regra percentual fica adiada;
- o percentual volta a ser obrigatório quando a base alcançar 50 Devices;
- o padrão pode ser ajustado com `NETBOX_DISCOVERY_PERCENT_MIN_BASE`;
- conflitos de identidade, nomes duplicados, REVIEW e DELEGATED continuam protegidos.

## Relatório nativo do PLAN

```bash
netbox-discovery plan summary
netbox-discovery plan blocked
netbox-discovery plan review
netbox-discovery plan ready
netbox-discovery plan delegated
```

Esses comandos são somente leitura e mostram Run ID, status, escrita no NetBox, write guard, decisões, ações, motivos, IP, nome e role. `--json` fornece saída estruturada.

## Instalação e atualização

```bash
netbox-discovery update run
netbox-discovery version
netbox-discovery check
netbox-discovery status
```

O updater consulta o canal `stable`, valida o candidato, cria backup, instala preservando configuração, testa e executa rollback/quarentena em falha.

## Auto-update e schedulers

Cada execução automática Network ou Hypervisor executa update preflight antes da coleta. Falha temporária do GitHub é registrada e a coleta continua com a versão instalada válida. O updater não modifica `automation.apply`.

```bash
netbox-discovery scheduler enable
netbox-discovery scheduler disable
netbox-discovery scheduler status
```

## Redes grandes

O Discovery V6 divide prefixos grandes, como `/16`, em lotes `/24`, elimina sobreposição, aplica paralelismo controlado e apresenta erro explícito por lote.

## Segurança

- nenhuma exclusão automática de Device;
- nenhum PATCH automático de nome;
- nome existente no NetBox é preservado;
- VM confirmada permanece delegada;
- serial conflitante não é gravado;
- identidade `WEAK` nunca cria novo Device;
- `REVIEW`, `DELEGATED` e `BLOCKED` nunca escrevem;
- `READY/CREATE` e `READY/UPDATE_SAFE` escrevem somente com `--apply`;
- limites absolutos permanecem ativos durante bootstrap;
- percentual é obrigatório após a base mínima;
- relatórios do PLAN são somente leitura.

## Documentação

- `docs/MANUAL.md`;
- `docs/COMANDOS-RAPIDOS.md`;
- `docs/HOMOLOGACAO.md`;
- `RELEASE-NOTES.md`;
- `SECURITY.md`;
- `docs/PATCH-1.11.19.md`.
