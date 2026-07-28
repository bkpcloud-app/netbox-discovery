# Segurança do repositório

**Versão da política:** 1.10.18

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

## Preflight global

Antes da primeira escrita:

1. recalcular o PLAN V7;
2. validar READY normais e todos os REPAIR_SAFE;
3. reler Device, VM, interfaces, IPs, MACs e relacionamentos;
4. bloquear qualquer drift ou consulta incompleta;
5. criar journal read-only;
6. somente então permitir escrita.

## Regra de primary IP da 1.10.18

O NetBox não permite reatribuir um IP enquanto ele está configurado como primary/oob do objeto pai atual.

Para um reparo em modo `FULL`:

```text
primary_ip4/primary_ip6/oob_ip vazio
→ pode continuar

primary_ip4/primary_ip6/oob_ip apontando para o IP alvo
→ limpar antes do reassignment

qualquer campo apontando para outro IP
→ BLOCKED antes do IP move e antes do DELETE
```

Ordem obrigatória:

```text
revalidar ownership
→ limpar primary/oob do Device
→ mover IP para virtualization.vminterface
→ definir primary IPv4 da VM
→ remover somente o Device duplicado criado pelo produto
```

## Reparo de interface VM

Caminhos aceitos:

```text
MAC VMware corresponde exatamente a uma interface live
VM única + uma interface sem MAC + MAC VMware forte
VM única + zero interfaces + MAC VMware forte → criar MGMT
```

MAC duplicado, MAC pertencente a outro objeto ou interface ambígua bloqueiam.

## DELETE restrito

Não existe DELETE genérico no Network.

A única remoção automática é um Device duplicado de VM quando:

- Device, interfaces e IP comprovam ownership do produto;
- não existe serial, rack, location, cluster, cabo ou objeto relacionado;
- existe exatamente um IP observado;
- existe uma única VM correspondente;
- a interface alvo é inequívoca;
- a VM não possui outro primary IPv4;
- primary/oob do Device está vazio ou aponta somente para o IP alvo.

A VM nunca é removida.

## Recuperação parcial

```text
interface criada sem MAC
→ fallback de interface única

interface + MAC criados, IP ainda no Device
→ limpar primary do Device e concluir REPAIR_SAFE

IP já movido, Device ainda existe
→ RECOVERY_AFTER_IP_MOVE
```

## Concorrência e retry

Network, Hypervisor, Compare e Update compartilham lock global.

- POST/PATCH/DELETE não recebem retry cego;
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
