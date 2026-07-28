# Segurança do repositório

**Versão da política:** 1.10.17

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

## Preflight global 1.10.17

Antes da primeira escrita da finalização:

1. recalcular o PLAN V7;
2. validar todos os READY normais;
3. validar ownership de todos os MACs esperados;
4. validar todos os `REPAIR_SAFE_VM_DUPLICATE`;
5. reler Device, VM, VM interfaces, IPs, interfaces físicas e MACs;
6. consultar relações de inventário, console, energia, front/rear ports e bays;
7. bloquear se qualquer consulta falhar ou qualquer relação inesperada existir;
8. criar `REPAIR_JOURNAL` read-only;
9. somente então permitir escrita.

Uma consulta indisponível nunca é interpretada como coleção vazia.

## Criação de interface ausente na VM

A 1.10.17 só pode criar uma `virtualization.vminterface` durante um reparo quando todas as condições forem verdadeiras:

```text
uma única VM por nome
zero interfaces live nessa VM
exatamente um MAC VMware forte
MAC ausente ou sem vínculo
MAC não duplicado
MAC não pertencente a outro objeto
Device/IP/interfaces integralmente criados pelo produto
Device sem serial, escopo físico, cabo ou objetos relacionados
exatamente um IP observado ainda no Device duplicado
VM sem outro primary IPv4
```

A interface criada deve usar:

```text
name=MGMT
enabled=true
description=Descoberto pelo netbox-discovery hypervisor
```

Bloqueios obrigatórios:

```text
mais de uma VM por nome
uma ou mais interfaces live no caminho zero-interface
mais de um MAC VMware candidato
MAC já pertencente a dcim.interface ou outra VM interface
MAC duplicado globalmente
Device/IP/interface sem ownership do produto
qualquer vínculo manual ou objeto relacionado
```

## Fallback de interface única sem MAC

Quando a VM já possui exatamente uma interface, o produto pode criar/atribuir o MAC VMware somente se a interface não possuir outro MAC e todas as demais proteções do reparo continuarem válidas.

VM com múltiplas interfaces sem correspondência inequívoca permanece `BLOCKED`.

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
- a interface alvo é comprovada por MAC exato, interface única vazia ou criação protegida da interface ausente;
- Tenant/Site permanecem válidos;
- a VM não possui outro primary IPv4.

Se qualquer condição falhar:

```text
BLOCKED
REPAIR_SAFE_NOT_ELIGIBLE
nenhum DELETE é executado
```

A VM nunca é removida.

## Ordem segura

```text
PREFLIGHT GLOBAL
→ IMPORT normal
→ MAC RECONCILE de Devices
→ revalidação live do reparo
→ criar interface da VM, quando elegível
→ criar/atribuir MAC e primary MAC
→ mover IP para a VM
→ definir primary IPv4 se vazio
→ remover somente o Device duplicado do produto
→ AUDIT FINALIZE
```

Se o IMPORT normal ou o MAC RECONCILE falhar, nenhum Device duplicado é removido.

## Recuperação parcial

```text
interface criada sem MAC
→ próxima execução usa fallback de interface única

interface + MAC criados, IP ainda no Device
→ próxima execução conclui REPAIR_SAFE

IP já movido, Device ainda existe
→ RECOVERY_AFTER_IP_MOVE
```

Nenhuma etapa de recuperação remove a VM.

## MAC ownership de Devices

```text
MAC ausente ou sem vínculo → permitido
MAC na interface esperada → permitido
MAC duplicado             → bloqueado
MAC em outra interface    → bloqueado
MAC em VM/outro objeto    → bloqueado
```

Após o IMPORT normal, `MAC RECONCILE` pode criar ou atribuir o objeto MAC somente quando o IP resolve uma única `dcim.interface` do Device esperado.

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

Histórico VMware não autoriza reparo sozinho. Ele precisa passar pelos gates de VM única, MAC VMware único e ownership integral do produto. `connUnitId=000...000` não é identidade.

## Auditoria 1.10.17

O audit combinado confirma:

- convergência dos READY normais;
- MACs de Devices nas interfaces corretas;
- interface criada na VM correta, quando aplicável;
- MAC da VM único e configurado como primary MAC;
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
