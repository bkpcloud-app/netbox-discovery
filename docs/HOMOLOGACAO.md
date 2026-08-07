# netbox-discovery 1.11.34 — Matriz de Homologação

## Estados

```text
LIVE PASS     = validado ao vivo com evidência
LIVE PARTIAL  = parte relevante validada
CI PASS       = regressões automatizadas passaram
NOT LIVE      = ainda não validado em ambiente real
```

CI PASS não substitui LIVE PASS.

## FBA

**Estado:** LIVE PASS como referência funcional.

## DCM

**Estado:** LIVE PASS para o pipeline Network histórico e LIVE PASS para o pipeline Hypervisor multi-contexto validado nas versões 1.11.29+.

Evidência histórica do Network:

```text
IMPORT: 27/27 processados
Runtime blocked: 0
Erros: 0
MAC RECONCILE: PASS
AUDIT: PASS
Assets FAIL: 0
Checks FAIL: 0
READY/CREATE posterior: 0
READY/NOOP posterior: 27
Network scheduler: ENABLED
```

Evidência do Hypervisor multi-contexto:

```text
PREFLIGHT GLOBAL: OK
Contextos escritos: 12
Reclassificações seguras: 53
Audit multi-contexto: PASS
MISMATCH: 0
MISSING: 0
```

A execução que produziu essa evidência ainda apresentou cinco VMs `_replica` de FVI como AMBIGUOUS por UUID divergente. A 1.11.30 adicionou a regra restrita de refresh de UUID para réplica VMware com nome único. A regra possui CI PASS; uma execução live posterior específica dessa correção deve ser registrada quando houver evidência.

## Instalação direta de unidade nova

Procedimento oficial:

```bash
curl -fsSL https://raw.githubusercontent.com/bkpcloud-app/netbox-discovery/stable/install-from-github.sh -o /tmp/netbox-discovery-install.sh && bash /tmp/netbox-discovery-install.sh && netbox-discovery init && netbox-discovery check && netbox-discovery scheduler enable && netbox-discovery run --apply
```

Requisitos do `init` para operação automática:

```text
NetBox: https://inventory.bkpcloud.app.br
Habilitar execução automática: SIM
Permitir IMPORT automático: SIM
Salvar: SIM
Testar NetBox: SIM
```

Resultado esperado:

```text
CONFIG: OK
scheduler Network: ENABLED
primeiro RUN executado imediatamente
IMPORT/AUDIT conforme registros READY e proteções
```

## GO-LIVE controlado

O fluxo controlado continua disponível:

```bash
netbox-discovery go-live
```

Ele termina com scheduler Network habilitado e `APPLY=NÃO` quando a convergência é aprovada.

## Contrato de documentação e higiene — 1.11.34

A 1.11.34 não altera a lógica de descoberta, classificação ou escrita do inventário. Ela endurece a manutenção do produto:

```text
VERSION raiz e pacote sincronizados
documentos obrigatórios na versão EXATA
nota PATCH da versão obrigatória
Ponto de retomada obrigatório no Manual
config.yml.example no endpoint HTTPS/443
artefatos obsoletos conhecidos ausentes
main sincronizado com stable após promoção
```

Artefatos removidos por não terem referência de runtime/CI e estarem desatualizados:

```text
SHA256SUMS
netbox-discovery/docs/PRODUCT-V1.md
netbox-discovery/workflow.yml
```

Os módulos versionados antigos permanecem porque a implementação atual reutiliza camadas anteriores e a suíte de regressão depende dessa cadeia. Não são classificados como lixo sem refatoração prévia.

## Regressões obrigatórias atuais

```text
configurador usa HTTPS/443 sem :8080
updater evita falso ATUALIZADO por cache
instalação limpa documentada
versão exata em todos os documentos obrigatórios
Ponto de retomada presente no Manual
config.yml.example sem :8080
artefatos obsoletos não retornam
wrapper público reconhece go-live
Network run --apply executa IMPORT e AUDIT
scheduler Network e Hypervisor permanecem independentes
REVIEW/DELEGATED/BLOCKED não escrevem
```

## Critérios gerais para LIVE PASS de unidade nova

```text
netbox-discovery version → versão stable atual
netbox-discovery check → PASS
CONFIG: OK
Tenant/Site corretos
NetBox URL sem :8080
primeiro RUN sem erro fatal
AUDIT sem FAIL crítico
scheduler no estado planejado
modo de APPLY coerente com a política da unidade
```
