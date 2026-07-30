# netbox-discovery 1.11.2 — Matriz de Homologação

## Estados

```text
LIVE PASS     = validado ao vivo com evidência
LIVE PARTIAL  = parte relevante validada
CI PASS       = regressões automatizadas passaram
NOT LIVE      = ainda não validado ao vivo
```

CI PASS não equivale a LIVE PASS.

## Hypervisor central

**Estado anterior:** LIVE PASS.

```text
Objetos comparados: 282
OK: 282
MISMATCH: 0
MISSING: 0
AMBIGUOUS: 0
COMPARE STATUS: OK
```

O coletor central continua responsável pelos vCenters. Filiais não executam hypervisor local.

## FBA — linha de base

**Ciclo 1.10.18:** LIVE PASS em 29/07/2026.

```text
Hosts ativos: 288
Assets reconciliados: 283
Devices após APPLY: 179
DELEGATED/HYPERVISOR: 37
Assets FAIL: 0
Checks FAIL: 0
```

**Dry-run 1.11.0 em 30/07/2026:** LIVE PARTIAL.

```text
Hosts ativos: 290
Assets planejados: 285
READY/CREATE: 5
READY/UPDATE_SAFE: 10
DELEGATED_VM: 37
REVIEW: 64
BLOCKED: 0
WRITE GUARD: PASS
NetBox write: NÃO
```

Esse dry-run confirmou nomes SNMP repetidos, Printer-MIB, virtualização centralizada e write guard, mas também revelou falsos positivos de CFTV, modelo repetido de Kyocera, serial placeholder Pantum e detalhes parciais de VM. Esses pontos foram corrigidos antes da 1.11.2.

## Estado da 1.11.2

**Estado:** CI/NOT LIVE até novo dry-run no FBA.

### Funções cobertas por regressão

```text
Windows Server separado de Windows Workstation
Windows 11 → WORKSTATION-WINDOWS
Windows Server 2022 → SERVER-WINDOWS
RDP genérico não decide edição
conflito de edição não altera role
Device manual não recebe correção automática
serial placeholder rejeitado
serial forte conflitante bloqueado
Printer-MIB escolhe serial válido
Hikvision/ONVIF extrai modelo, firmware e serial
CFTV genérico não classifica Dell/Seagate como câmera
nome existente permanece protegido
VM central permanece DELEGATED
write guard bloqueia impacto anormal
```

## Atualização obrigatória

A release será distribuída pelo canal `stable`. Não usar instalador manual.

```bash
netbox-discovery update run
```

Depois:

```bash
netbox-discovery version
netbox-discovery self-test
netbox-discovery status
netbox-discovery run
```

Não usar `--apply` antes de revisar o relatório.

## Versões esperadas

```text
Versão: 1.11.2
Discovery: 4.5-product
Classifier: 5.3-product
Planner: 5.0-product
Importer: 5.9-product
Pipeline: 3.0-product
WRITE GUARD: PASS
NetBox write: NÃO
```

## Critérios do dry-run FBA

1. `SW-BA17-LB43JZ` e `SW-BA17-KPC2C1` continuam distintos.
2. Nome manual no NetBox não gera PATCH de nome.
3. Impressoras exibem serial válido, fonte, candidatos e rejeições.
4. `03000000` não aparece como serial elegível.
5. Kyocera não apresenta modelo duplicado, como `ECOSYS ... ECOSYS`.
6. Hikvision recebe fabricante/modelo/firmware/serial quando ISAPI ou ONVIF anônimo responder.
7. Câmera sem identidade suficiente permanece REVIEW, sem serial inventado.
8. Dell/iDRAC não aparece como `VIDEO_SURVEILLANCE_DEVICE`.
9. Windows Server comprovado aponta para `SERVER-WINDOWS`.
10. Windows 11/10 comprovado aponta para `WORKSTATION-WINDOWS`.
11. Windows sem edição comprovada permanece REVIEW.
12. Device manual não recebe troca automática de role.
13. Os 37 itens de VM continuam DELEGATED e não geram Device físico.
14. `WRITE GUARD: PASS` e `NetBox write: NÃO`.
15. Nenhum serial com `serial_confidence: CONFLICT` fica elegível para escrita.

## APPLY controlado

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
preview posterior sem CREATE/UPDATE_SAFE/REPAIR_SAFE inesperado
```

## Proteções obrigatórias

```text
PATCH automático de name inexistente
Device manual preservado
role Windows só muda com edição comprovada
serial placeholder/conflitante não é gravado
VM central nunca vira Device físico duplicado
REVIEW/BLOCKED/DELEGATED não escrevem
nenhuma VM é removida
```

## Schedulers

```text
Auto-update stable: LIVE PASS
Network scheduler: DISABLED durante homologação
Hypervisor local na filial: NÃO REQUERIDO
```
