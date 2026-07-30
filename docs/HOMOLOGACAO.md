# netbox-discovery 1.11.0 — Matriz de Homologação

## Estados

```text
LIVE PASS     = validado ao vivo com evidência
LIVE PARTIAL  = parte relevante validada, fluxo completo pendente
CI PASS       = regressões automatizadas passaram
NOT LIVE      = ainda não validado ao vivo
```

CI PASS não equivale a LIVE PASS.

## Hypervisor central

**Estado:** LIVE PASS.

```text
Objetos comparados: 282
OK: 282
MISMATCH: 0
MISSING: 0
AMBIGUOUS: 0
COMPARE STATUS: OK
```

O coletor central continua responsável pelos vCenters. A release 1.11.0 não exige hypervisor local nas filiais.

## Network — Site DCM

**Estado anterior:** LIVE PASS em 29/07/2026 com a 1.10.18.

```text
ownership Hypervisor → PASS
Dell switches → PASS
MD32xx multi-endpoint → PASS
ME4/ME5 storage → PASS
preflight global → PASS
IMPORT normal → PASS
MAC RECONCILE → PASS
REPAIR_SAFE de Device duplicado de VM → PASS
idempotência → PASS
Assets FAIL: 0
Checks FAIL: 0
```

A 1.11.0 ainda precisa de novo dry-run antes de qualquer APPLY no DCM.

## Network — Site FBA, linha de base

**Estado do ciclo 1.10.18:** LIVE PASS em 29/07/2026.

```text
Hosts ativos: 288
Assets reconciliados: 283
Devices antes: 175
READY: 175
REVIEW: 69
BLOCKED: 2
READY/CREATE: 4
READY/UPDATE_SAFE: 0
READY/NOOP: 171
DELEGATED/HYPERVISOR: 37
```

### APPLY de referência

```text
PREFLIGHT GLOBAL FINALIZE: OK
Assets READY processados: 175/175
Runtime blocked: 0
Erros: 0
MAC RECONCILE: PASS
Devices após: 179
```

### Audit de referência

```text
Status: PASS_WITH_WARNINGS
Assets PASS: 170
Assets WARN: 5
Assets FAIL: 0
Checks PASS: 1809
Checks WARN: 11
Checks FAIL: 0
READY/CREATE posterior: 0
READY/UPDATE_SAFE posterior: 0
READY/NOOP posterior: 175
```

## Network 1.11.0 — consolidação

**Estado:** CI/NOT LIVE até dry-run e APPLY controlado no FBA.

### Funções cobertas por regressão

```text
Siemens S7 estruturado
EtherNet/IP CIP Identity
ONVIF camera identity
OUI virtual como candidato, nunca confirmação isolada
hardware físico forte prevalece sobre indício de OUI virtual
Discovery UID estável por serial
nome existente no NetBox preservado
VIRTUAL_CANDIDATE não cria Device físico
DELEGATED_VM mostra VM/interface/cluster/host
write guard bloqueia volume anormal
importer rejeita PATCH de name
```

### Primeira etapa obrigatória: instalação controlada da branch

A 1.11.0 não deve ser mesclada no canal `main/stable` antes do teste live. Na FBA, instalar diretamente a branch do PR:

```bash
cd /tmp
rm -f install-from-github.sh
curl -fsSL -o install-from-github.sh \
  https://raw.githubusercontent.com/bkpcloud-app/netbox-discovery/main/install-from-github.sh
chmod +x install-from-github.sh
NETBOX_DISCOVERY_REF=agent/netbox-discovery-1.11.0-consolidation \
  ./install-from-github.sh
```

A instalação preserva a configuração operacional existente conforme as proteções do bootstrap/updater.

### Segunda etapa obrigatória: dry-run

```bash
netbox-discovery version
netbox-discovery self-test
netbox-discovery status
netbox-discovery run
```

Não usar `--apply` antes de revisar o relatório.

### Critérios do dry-run

```text
Versão: 1.11.0
Discovery: 4.4-product
Classifier: 5.2-product
Planner: 4.9-product
Pipeline: 3.0-product
WRITE GUARD: PASS
NetBox write: NÃO
```

Validar especificamente:

1. Os dois switches `SW-BA17` aparecem como objetos distintos quando serial/MAC forem fortes.
2. O nome SNMP original permanece como `observed_name`.
3. Um nome alterado manualmente no NetBox aparece como nome efetivo e não gera diff de nome.
4. A impressora `KM6E3D62` recebe identidade melhor quando Printer-MIB retornar dados, sem renomear o Device manual.
5. Os 37 servidores aparecem como `DELEGATED_VM/PASS`, com VM, interface, cluster, host físico e site.
6. O status mostra virtualização centralizada e hypervisor local não requerido.
7. Ubiquiti e Topdata existentes não são rebaixados por perda transitória de evidência.
8. iDRAC/service tag apresenta pai físico provável e permanece REVIEW quando a associação ainda não for segura.
9. Industrial apresenta protocolo, fabricante/modelo/serial quando retornados; caso contrário continua REVIEW sem modelo inventado.
10. CFTV usa ONVIF/fingerprint e não classifica apenas por porta web.
11. `VIRTUAL_CANDIDATE` não produz `READY/CREATE` de Device.
12. Nenhum item elegível está bloqueado pelo write guard em uma mudança normal.

### APPLY controlado

Somente depois do dry-run aprovado:

```bash
netbox-discovery run --apply
```

Critérios de LIVE PASS:

```text
PREFLIGHT GLOBAL FINALIZE: OK
WRITE GUARD: PASS
Runtime blocked: 0
Erros: 0
MAC RECONCILE: PASS
Assets FAIL: 0
Checks FAIL: 0
preview posterior sem READY/CREATE, READY/UPDATE_SAFE ou READY/REPAIR_SAFE elegível
```

### Proteções que precisam ser comprovadas

```text
PATCH automático de name inexistente
Device manual/específico preservado
VM central nunca criada como Device físico duplicado
REVIEW/BLOCKED/DELEGATED não escrevem
nenhuma VM removida
write guard bloqueia cenário anormal antes da primeira escrita
```

Até essa evidência, o estado correto da release é **CI/NOT LIVE**.

## Segurança operacional

```text
netbox-discovery run          → dry-run
netbox-discovery run --apply  → escreve somente READY
REVIEW/BLOCKED/DELEGATED      → não escrevem
DELETE de VM                  → proibido
Nome de Device existente      → não alterado
Device Type manual/específico → não substituído
```

## Schedulers

```text
Auto-update stable: LIVE PASS
Network scheduler: DISABLED
Hypervisor scheduler nas filiais: NÃO REQUERIDO
```

A habilitação do Network scheduler só deve ocorrer depois do LIVE PASS da 1.11.0.
