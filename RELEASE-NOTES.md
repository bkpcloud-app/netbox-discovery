## V1.10.9 — Diagnóstico automático do PLAN Network

Release criada a partir do primeiro dry-run real do pipeline de rede no DCM em 27/07/2026.

### Evidência live que motivou a mudança

```text
Hosts ativos: 64
Assets reconciliados: 60
READY: 7
REVIEW: 47
BLOCKED: 6
READY/CREATE: 3
READY/NOOP: 4
NetBox write: NÃO
```

O discovery encontrou switches e outros equipamentos físicos, mas o terminal não mostrava quais assets estavam em `REVIEW/BLOCKED` nem os motivos sem abrir JSON.

### Mudança

`netbox-discovery run` passa a mostrar automaticamente:

```text
NETWORK PLAN DIAGNÓSTICO
NETWORK NOVOS OBJETOS READY
NETWORK AJUSTES READY
NETWORK PENDÊNCIAS POR MOTIVO
NETWORK PENDÊNCIAS DETALHADAS
```

Para cada pendência, exibe:

- IP;
- nome desejado;
- role;
- confidence/score;
- reasons do PLAN;
- match_state/match_reason;
- fabricante/modelo/serial;
- SNMP name/object-id/MAC de gerenciamento;
- evidência usada pelo CLASSIFY.

### Segurança

A 1.10.9 não muda as regras de elegibilidade:

```text
READY   → pode escrever somente com --apply
REVIEW  → não escreve
BLOCKED → não escreve
```

Não adiciona DELETE automático e não exige Python ad-hoc para análise operacional.

### Objetivo da próxima etapa

Usar a saída live para agrupar as causas reais dos 47 REVIEW e 6 BLOCKED e então corrigir CLASSIFY/RECONCILE/PLAN por classe de problema, sem criar exceções específicas do DCM.

### Regressão

O CI valida que o diagnóstico mostra READY, REVIEW, BLOCKED, contagem por motivo, evidência CLASSIFY e `NetBox write: NÃO`.

---

## V1.10.8 — VM acompanha Tenant/Site do Host/Cluster

Hotfix criado após o APPLY real chegar a `PXMETAIS/MAC` e o NetBox rejeitar uma VM ainda com `site=DCM` depois que seu Device já havia mudado para `MAC`.

Correção:

```text
Host/Cluster já migrado
→ revalidar identidade forte da VM
→ reler Device/Cluster
→ VM PARENT PREFLIGHT
→ PATCH VM tenant + site juntos
→ ajustar Tenant dos IPs
```

Validação live final:

```text
VM PARENT PREFLIGHT PXMETAIS/MAC: OK | VMs=25
Hosts processados: 1
VMs processadas: 25
Erros: 0
HYPERVISOR AUDIT MULTI-CONTEXT: PASS
```

Compare independente:

```text
Objetos comparados: 282
OK: 282
MISMATCH: 0
MISSING: 0
AMBIGUOUS: 0
COMPARE STATUS: OK
```

Estado: **LIVE PASS**.

---

## V1.10.7 — Migração coordenada de Cluster/Site e compare read-only

Corrige dependência circular entre Cluster scoped e Devices-host mudando juntos de Site.

```text
RECLASSIFY PREFLIGHT
→ remove temporariamente scope do Cluster
→ move Hosts
→ reaplica scope no Site alvo
→ continua VMs
```

Também adiciona:

```bash
netbox-discovery hypervisor run --compare
```

Estados: `OK`, `MISMATCH`, `MISSING`, `AMBIGUOUS`.

Estado: **LIVE PASS**.

---

## V1.10.6 — Preflight global Hypervisor

Antes do primeiro POST/PATCH:

```text
reconstrói PLAN
→ REVIEW/BLOCKED = 0
→ conjunto RECLASSIFY_SAFE inalterado
→ identidade forte/existing_id/alvo revalidados
→ escrita
```

Estado: **LIVE PASS**.

---

## V1.10.5 — Diagnóstico completo do PLAN Hypervisor

Elimina Python ad-hoc para listar `READY/CREATE`, `UPDATE_SAFE`, `RECLASSIFY_SAFE`, `REVIEW` e `BLOCKED`.

Estado: **LIVE PASS**.
