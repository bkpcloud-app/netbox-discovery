# Segurança do repositório

**Versão da política:** 1.10.16

O `netbox-discovery` é distribuído em repositório público. Código e documentação podem ser públicos; dados operacionais e credenciais de clientes não podem.

## Nunca versionar

- configuração real de cliente;
- tokens e communities;
- senhas VMware, Proxmox, Hyper-V ou NetBox;
- chaves privadas;
- relatórios, journals, logs e backups reais.

## Decisões Network

```text
READY/CREATE                    → escreve somente com --apply
READY/UPDATE_SAFE               → escreve somente com --apply
READY/REPAIR_SAFE_VM_DUPLICATE  → escreve após preflight global
READY/NOOP                      → não altera
DELEGATED                       → não escreve
REVIEW                          → não escreve
BLOCKED                         → não escreve
```

## Preflight global 1.10.16

Antes da primeira escrita da finalização:

1. recalcular o PLAN V6;
2. validar todos os READY normais;
3. validar ownership de todos os MACs esperados;
4. validar todos os `REPAIR_SAFE_VM_DUPLICATE`;
5. reler Device, VM, VM interfaces, IPs, interfaces físicas e MACs;
6. consultar relações de inventário, console, energia, front/rear ports e bays;
7. bloquear se qualquer consulta falhar ou qualquer relação inesperada existir;
8. criar `REPAIR_JOURNAL` read-only;
9. somente então permitir escrita.

Uma consulta indisponível nunca é interpretada como coleção vazia.

## MAC ownership de Devices

```text
MAC ausente ou sem vínculo → permitido
MAC na interface esperada → permitido
MAC duplicado             → bloqueado
MAC em outra interface    → bloqueado
MAC em VM/outro objeto    → bloqueado
```

Após o IMPORT normal, `MAC RECONCILE` pode criar ou atribuir o objeto MAC somente quando o IP resolve uma única `dcim.interface` do Device esperado.

## Fallback de VM com interface única sem MAC

O produto só pode criar/atribuir um MAC VMware na interface da VM durante um reparo quando todas as condições forem verdadeiras:

```text
uma única VM por nome
exatamente uma interface live nessa VM
interface sem outro MAC
exatamente um MAC VMware forte
MAC ausente, sem vínculo ou já na mesma interface
MAC não duplicado
MAC não pertencente a outro objeto
todas as proteções de ownership do Device/IP válidas
```

Bloqueios obrigatórios:

```text
VM com 0 ou mais de 1 interface
interface com MAC divergente
mais de um MAC VMware candidato
MAC já pertencente a dcim.interface ou outra VM interface
MAC duplicado globalmente
```

O MAC é revalidado antes da primeira escrita e novamente imediatamente antes do reparo destrutivo.

## DELETE restrito

Não existe DELETE genérico no Network.

A única remoção automática é um Device duplicado de VM quando:

- a descrição do Device comprova criação pelo produto;
- interfaces e IP mantêm descrições de ownership do produto;
- o Device não possui serial, rack, location, cluster, virtual chassis ou device bay;
- não existem inventory items, console, power, front/rear ports, device bays ou module bays;
- não existe cabo ou conexão manual;
- existe um único IP observado;
- existe uma única VM pelo nome;
- a interface alvo é comprovada por MAC exato ou pelo fallback de interface única;
- Tenant/Site permanecem válidos;
- a VM não possui outro primary IPv4.

Se qualquer condição falhar:

```text
BLOCKED
REPAIR_SAFE_NOT_ELIGIBLE
NetBox write: NÃO para o reparo
```

A VM nunca é removida.

## Ordem segura

```text
PREFLIGHT GLOBAL
→ IMPORT normal
→ MAC RECONCILE de Devices
→ revalidação live do reparo
→ VM MAC ENSURE, quando necessário
→ move IP para a VM
→ remove somente o Device duplicado do produto
→ AUDIT FINALIZE
```

Se o IMPORT normal ou o MAC RECONCILE falhar, nenhum Device duplicado é removido.

A criação do MAC na VM ocorre antes da movimentação do IP. Se uma falha posterior ocorrer, o estado permanece recuperável e um novo PLAN deve usar a correspondência MAC normal.

## Recuperação parcial

```text
RECOVERY_AFTER_IP_MOVE
```

A próxima execução pode concluir somente a limpeza restante, desde que todas as proteções continuem válidas.

## MD32xx

A união automática exige `sysObjectID` exato, mesmo sysName não genérico, exatamente dois endpoints, `STORAGE/HIGH`, IPs consecutivos e ausência de serial conflitante.

Nome igual sozinho nunca autoriza merge.

## Ownership Hypervisor

```text
IP em virtualization.vminterface → DELEGATED/NOOP
```

A ponte por nome nunca rebaixa um `DELEGATED` autoritativo.

## Identidade anti-flap

Identidade VMware e storage forte podem ser preservadas por até 48 horas no mesmo Site/IP.

Histórico VMware não autoriza reparo sozinho. Ele precisa passar pela correspondência live ou pelo fallback restrito de interface única. `connUnitId=000...000` não é identidade.

## Auditoria 1.10.16

O audit combinado confirma:

- convergência dos READY normais;
- MACs de Devices nas interfaces corretas;
- MAC da VM único, atribuído à interface correta e configurado como primary MAC;
- Device duplicado ausente;
- IP atribuído à VM interface correta;
- primary IPv4 correto;
- novo PLAN em `DELEGATED/NOOP` para o asset reparado.

AUDIT é read-only.

## Concorrência e retry

Network, Hypervisor, Compare e Update compartilham o lock global.

- POST/PATCH/DELETE não recebem retry cego;
- retries de FA-MIB são apenas leitura;
- falha parcial é preservada em journal/report;
- não executar correções manuais em massa para contornar o produto.

## Credenciais Hypervisor

```text
/etc/netbox-discovery/hypervisors.json
```

Permissão esperada: `0600`.

## Homologação

`CI PASS` não significa `LIVE PASS`.

Funcionalidade `NOT LIVE` não deve receber scheduler automático.
