# Manual Operacional — netbox-discovery

**Produto:** netbox-discovery  
**Versão:** 1.10.14 — PRODUCT V1  
**Distribuição oficial:** `bkpcloud-app/netbox-discovery`  
**Canal de produção:** `stable`  
**NetBox BKPCLOUD:** `https://inventory.bkpcloud.app.br:8080`

> `CI PASS` não equivale a `LIVE PASS`. Estado real em `docs/HOMOLOGACAO.md`.

## 1. Execução Network

Dry-run:

```bash
netbox-discovery run
```

Escrita explícita:

```bash
netbox-discovery run --apply
```

Fluxo 1.10.14:

```text
DISCOVER
→ CLASSIFY V5
→ RECONCILE V5
→ PLAN V4
→ PREFLIGHT GLOBAL FINALIZE
→ IMPORT normal
→ REPAIR_SAFE
→ AUDIT FINALIZE
```

## 2. Decisões

| Decisão/Ação | Significado | Escrita |
|---|---|---|
| `READY/CREATE` | novo Device físico validado | somente com `--apply` |
| `READY/UPDATE_SAFE` | complemento seguro | somente com `--apply` |
| `READY/REPAIR_SAFE_VM_DUPLICATE` | corrige Device duplicado criado pelo produto | somente após preflight global |
| `READY/NOOP` | inventário já convergente | não altera |
| `DELEGATED` | ownership do Hypervisor | não |
| `REVIEW` | evidência insuficiente | não |
| `BLOCKED` | conflito forte | não |

## 3. Dell PowerVault MD32xx

Identificação:

```text
sysObjectID = .1.3.6.1.4.1.674.10893.2.31
```

Dois endpoints viram um único asset somente quando:

1. existem exatamente dois registros;
2. ambos têm o mesmo `sysObjectID` exato;
3. ambos têm o mesmo `sysName` não genérico;
4. ambos estão `STORAGE/HIGH`;
5. não há serial conflitante;
6. os IPs são consecutivos.

Resultado:

```text
Device STORAGE
├─ MGMT
└─ MGMT-2
```

Não existe merge por nome isolado.

## 4. Reparo seguro de Device duplicado de VM

A ação `REPAIR_SAFE_VM_DUPLICATE` exige simultaneamente:

- uma única VM pelo nome;
- uma única interface da VM pelo MAC VMware;
- Device criado pelo produto;
- descrições originais do produto no Device, interface e IP;
- ausência de serial e vínculos manuais;
- ausência de objetos de inventário, console, energia, front/rear ports e bays;
- ausência de cabo;
- um único IP e uma única interface alvo;
- VM sem outro primary IPv4.

A execução faz:

```text
1. move o IP para virtualization.vminterface
2. define primary_ip4 da VM se estiver vazio
3. limpa primary/oob do Device duplicado
4. remove somente MACs criados pelo produto nesse Device
5. remove somente o Device duplicado criado pelo produto
```

A VM não é removida. Qualquer diferença live bloqueia o reparo.

## 5. Preflight global

Antes da primeira escrita:

```text
recalcula PLAN V4
→ valida todos os READY normais
→ valida todos os REPAIR_SAFE
→ relê Device, VM, interfaces, IPs, MACs e relacionamentos
→ cria REPAIR_JOURNAL
→ somente então escreve
```

Falha:

```text
PREFLIGHT GLOBAL FINALIZE: BLOQUEADO
NetBox write: NÃO
```

## 6. Recuperação de falha parcial

Se o IP já tiver sido movido, mas o Device ainda existir:

```text
RECOVERY_AFTER_IP_MOVE
```

A próxima execução faz novo preflight, preserva o IP na VM e conclui apenas a limpeza segura restante.

Relatório:

```text
/opt/netbox-discovery/reports/<SITE>-repair-journal-*.json
```

## 7. Ordem de escrita

A 1.10.14 executa primeiro o IMPORT normal. Se ele falhar, o reparo destrutivo ainda não começou.

Depois, cada reparo é revalidado novamente imediatamente antes da ação.

## 8. Audit final

O `auditor_v4` combina:

- auditoria dos READY normais;
- confirmação de que o Device duplicado foi removido;
- confirmação de que o IP pertence à interface da VM;
- confirmação do primary IPv4;
- idempotência: o asset reparado deve ficar `DELEGATED/NOOP`.

Saída:

```text
AUDIT FINALIZE RESULTADO
Status: PASS | PASS_WITH_WARNINGS | FAIL
```

## 9. REVIEW residual

Um asset sem identidade forte pode permanecer `REVIEW` e ser ignorado pelo importer. Isso não bloqueia READY seguros.

Nunca force classificação para “zerar a tela”.

## 10. Ownership Hypervisor

Precedência:

```text
IP em virtualization.vminterface → DELEGATED
```

Fallback:

```text
MAC VMware + VM única por nome → DELEGATED
```

Device físico + VM inequívoca permanece `BLOCKED`, exceto quando atende integralmente ao `REPAIR_SAFE_VM_DUPLICATE`.

## 11. Storage ME4/ME5

Mantém FA-MIB:

```text
connUnitType=storage-subsystem(11)
connUnitId válido
connUnitSn válido
```

`connUnitId=000...000` é ignorado. Há até três tentativas read-only e anti-flap de identidade forte por até 48 horas.

## 12. Falha operacional

```text
1. preservar relatórios e journal
2. não editar em massa no NetBox
3. não repetir --apply cegamente
4. executar o mesmo comando somente após analisar a proteção apresentada
5. deixar o recovery do produto concluir o estado parcial
```

## 13. Hypervisor

```bash
netbox-discovery hypervisor configure
netbox-discovery hypervisor check
netbox-discovery hypervisor run
netbox-discovery hypervisor run --compare
netbox-discovery hypervisor run --apply
```

Estado de referência: `282/282 OK`, sem divergência Tenant/Site.

## 14. Caminhos

```text
Aplicação:              /opt/netbox-discovery
Configuração:           /opt/netbox-discovery/config.yml
Config Hypervisor:      /etc/netbox-discovery/hypervisors.json
Relatórios:             /opt/netbox-discovery/reports
Backups:                /opt/netbox-discovery/backups
Lock global:            /var/lock/netbox-discovery-global.lock
```
