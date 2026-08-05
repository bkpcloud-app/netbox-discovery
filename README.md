# netbox-discovery

Produto BKPCLOUD para descoberta, classificação, reconciliação e inventário seguro de infraestrutura no NetBox.

**Versão atual:** 1.11.18 — PRODUCT V1  
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

## Write guard final e bootstrap de sites pequenos

O write guard é calculado uma única vez, depois de todas as políticas finais do Planner.

Na 1.11.18, sites com menos de 50 Devices entram automaticamente na política:

```text
SMALL_SITE_BOOTSTRAP_ABSOLUTE_ONLY
```

Nesse estágio:

- os limites absolutos de CREATE, UPDATE, REPAIR e TOTAL continuam obrigatórios;
- somente a regra percentual fica adiada;
- o percentual volta a ser obrigatório quando a base alcançar 50 Devices;
- o padrão pode ser ajustado com `NETBOX_DISCOVERY_PERCENT_MIN_BASE`;
- conflitos de identidade, nomes duplicados, REVIEW e DELEGATED continuam bloqueados normalmente.

Isso evita que uma base inicial pequena torne impossível o primeiro inventário. Exemplo: 17 mudanças sobre 13 Devices equivalem a 131%, mas ainda ficam abaixo do limite absoluto padrão de 25 criações.

O relatório nativo apresenta:

```text
WRITE GUARD: PASS|BLOCK
WRITE GUARD POLÍTICA: SMALL_SITE_BOOTSTRAP_ABSOLUTE_ONLY|ABSOLUTE_AND_PERCENT
percentual: ADIADO|ATIVO
base mínima
eligible_total
live_devices
change_percent
violations
```

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
- `docs/PATCH-1.11.18.md`.
