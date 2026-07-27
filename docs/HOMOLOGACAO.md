# netbox-discovery 1.10.8 — Matriz de Homologação

Este arquivo separa **implementação/CI** de **validação real ao vivo**.

## Estados

```text
LIVE PASS     = validado ao vivo com evidência
LIVE PARTIAL  = parte relevante validada, fluxo completo ainda pendente
CI PASS       = regressões automatizadas passaram
NOT LIVE      = ainda não validado ao vivo
```

> Nunca chamar uma função de homologada apenas porque o código existe ou o CI passou.

---

## Ambiente de referência

```text
Proxy: SNOC-AGL-DCM
Python: 3.6.8
Tenant Group base: POLIMIX
Tenant base: MIZU
Site base: DCM
NetBox: https://inventory.bkpcloud.app.br:8080
```

## Mappings LIVE

```text
10.1.1.0/24  -> MIZU/DCM
10.5.1.0/24  -> MIZU/FAB
10.2.1.0/24  -> MIZU/FBA
10.10.1.0/24 -> MIZU/FBE
10.9.1.0/24  -> MIZU/FFT
10.7.1.0/24  -> MIZU/FMN
10.6.1.0/24  -> MIZU/FMO
10.8.1.0/24  -> MIZU/FIB
10.3.1.0/24  -> MIZU/FPA
10.11.1.0/24 -> MIZU/FSO
10.4.1.0/24  -> MIZU/FVI
10.36.1.0/24 -> PXMETAIS/MAC
```

---

## Histórico relevante

```text
1.9.2   Tenant Group/Tenant/Site genérico                      LIVE PASS
1.9.3   dependências VMware isoladas                           LIVE PASS
1.9.4   configure/connect/save VMware                          LIVE PASS
1.9.6   política de IP autoritativo de VM                      LIVE PASS
1.10.3  management network autoritativa VMware                 LIVE PASS
1.10.3  resolver multi-contexto                                LIVE PASS
1.10.4  RECLASSIFY_SAFE em dry-run                             LIVE PASS
1.10.5  diagnóstico automático completo do PLAN               LIVE PASS
1.10.6  preflight global antes da primeira escrita             LIVE PASS
1.10.7  bridge Cluster/Site                                    LIVE PASS no FBA
1.10.7  compare read-only                                      LIVE PASS
1.10.8  VM parent/site bridge                                  NOT LIVE até novo APPLY
```

---

## 1.10.6 — primeiro APPLY multi-contexto

Preflight global ao vivo:

```text
PREFLIGHT GLOBAL: OK
READY/CREATE: 12
READY/UPDATE_SAFE: 53
READY/RECLASSIFY_SAFE: 44
REVIEW/BLOCKED: 0
NetBox write até aqui: NÃO
```

### DCM

```text
Hosts processados: 4
VMs processadas: 124
Erros: 0
```

### FAB

```text
RECLASSIFY PREFLIGHT MIZU/FAB: OK
Hosts processados: 1
VMs processadas: 4
Erros: 0
```

### FBA — falha que originou 1.10.7

```text
HTTP 400 /api/virtualization/clusters/4/
{"scope":["2 devices are assigned as hosts for this cluster but are not in site FBA"]}
```

Causa confirmada: tentativa de mover Cluster scoped antes dos Devices-host.

---

## 1.10.7 — bridge Cluster/Site

Sequência implementada:

```text
RECLASSIFY PREFLIGHT
→ validar Devices-host do Cluster
→ remover temporariamente o scope do Cluster
→ mover Hosts
→ reaplicar scope do Cluster no Site alvo
→ continuar VMs
```

### Validação real

Após atualização para 1.10.7, o APPLY atravessou o ponto que falhava no FBA.

Execuções concluídas com `Erros: 0`:

```text
MIZU/FBA
MIZU/FBE
MIZU/FFT
MIZU/FIB
MIZU/FMN
```

Depois de queda da sessão SSH, compare read-only confirmou:

```text
FBA: 51/51 NOOP
FBE: 13/13 NOOP
FFT: 8/8 NOOP
FIB: 6/6 NOOP
FMN: 12/12 NOOP
AMBIGUOUS: 0
```

Conclusão: bridge Cluster/Site = **LIVE PASS**.

---

## Compare read-only — 1.10.7

Comando:

```bash
netbox-discovery hypervisor run --compare
```

Validação real após APPLY parcial:

```text
Objetos comparados: 282
OK: 245
MISMATCH: 31
MISSING: 6
AMBIGUOUS: 0
NetBox write: NÃO
```

O compare mostrou corretamente que os Sites já concluídos viraram `NOOP` e restavam apenas contextos posteriores.

Conclusão: compare read-only = **LIVE PASS**.

---

## Segundo APPLY 1.10.7 — evidência real

Preflight:

```text
PREFLIGHT GLOBAL: OK
READY/CREATE: 6
READY/UPDATE_SAFE: 11
READY/RECLASSIFY_SAFE: 31
REVIEW/BLOCKED: 0
```

Contextos concluídos com `Erros: 0`:

```text
MIZU/DCM
MIZU/FAB
MIZU/FBA
MIZU/FBE
MIZU/FFT
MIZU/FIB
MIZU/FMN
MIZU/FMO
MIZU/FPA
MIZU/FSO
MIZU/FVI
```

Em `PXMETAIS/MAC`, o Host `10.36.1.21` foi reclassificado para MAC. A primeira VM reclassificada falhou:

```text
RECLASSIFY PXMETAIS/MAC | READY=26
RECLASSIFY PREFLIGHT PXMETAIS/MAC: OK
HTTP 400 /api/virtualization/virtual-machines/467/
{"site":["The selected device (10.36.1.21) is not assigned to this site (DCM)."]}
```

### Causa raiz

A rotina histórica de `RECLASSIFY_SAFE` de VM fazia:

```text
PATCH VM: tenant=<alvo>
```

Quando a VM tinha `host_name`/Device, o campo `site` não era enviado.

Depois que o Host mudou de `DCM` para `MAC`, a VM continuou com `site=DCM`. Ao tentar alterar apenas o Tenant, o NetBox validou a relação VM ↔ Device e recusou o estado inconsistente.

Não é erro de mapping. É dependência de escrita entre Device e VM.

---

## 1.10.8 — VM acompanha Tenant/Site do Parent

**Estado:** NOT LIVE  
**CI:** pendente até a branch concluir CI

Correção implementada de forma genérica:

```text
Host/Cluster migration
→ revalidar identidade forte da VM novamente
→ reler Device/Cluster no NetBox
→ VM PARENT PREFLIGHT
→ confirmar parent no Site alvo
→ PATCH VM tenant + site no mesmo request
→ ajustar Tenant dos IPs da VM
```

Travas:

- VM ligada a Device: Device deve estar no Site alvo;
- VM ligada a Cluster: Cluster não pode estar scoped em outro Site;
- identidade da VM é revalidada depois das migrações do parent;
- `existing_id` precisa permanecer igual;
- se parent ainda estiver fora do Site alvo, nenhuma VM daquele contexto é alterada;
- sem DELETE automático.

Regressões 1.10.8:

- reproduz VM com `site=DCM` ligada a Device já movido para `MAC`;
- exige PATCH atômico `tenant + site`;
- confirma atualização do Tenant do IP vinculado;
- bloqueia VM se Device ainda estiver no Site antigo.

Essa lógica não contém hardcode de PXMETAIS, MAC, MIZU, DCM ou IP específico.

---

## Estado geral Hypervisor multi-contexto

**Estado:** LIVE PARTIAL

Já validado ao vivo:

- 2 sources VMware;
- 12 contextos;
- 22/22 Hosts resolvidos;
- 246 VMs resolvidas na coleta mais recente;
- `NÃO RESOLVIDOS: 0`;
- `AMBIGUOUS: 0` no compare;
- preflight global real;
- journal de falha parcial;
- retomada idempotente por `NOOP`;
- DCM/FAB/FBA/FBE/FFT/FIB/FMN/FMO/FPA/FSO/FVI aplicados sem erro;
- bridge de Cluster/Site validada ao vivo.

Ainda falta:

```text
1. CI PASS da 1.10.8
2. publicar 1.10.8 na stable
3. update real no SNOC-AGL-DCM
4. compare read-only do estado parcial PXMETAIS/MAC
5. dry-run/preflight limpo
6. novo APPLY apenas do residual
7. validar VM PARENT PREFLIGHT PXMETAIS/MAC
8. concluir PXMETAIS/MAC
9. AUDIT final
10. compare final sem divergências
11. segundo dry-run idempotente
12. promover fluxo completo para LIVE PASS
```

---

## Network — persistência MAC V2

**Estado:** CI PASS / NOT LIVE

A homologação completa ao vivo da persistência em `dcim/mac-addresses` continua separada deste fluxo Hypervisor.

---

## Schedulers

```text
Auto-update stable: LIVE PASS
Network scheduler: DISABLED durante homologação
Hypervisor scheduler: DISABLED durante homologação
```

Não habilitar APPLY automático enquanto o fluxo Hypervisor completo não estiver `LIVE PASS`.
