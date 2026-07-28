# Segurança do repositório

**Versão da política:** 1.10.14

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

## Preflight global 1.10.14

Antes da primeira escrita da finalização:

1. recalcular o PLAN V4;
2. validar o estado global de todos os READY normais;
3. reler Device, VM, VM interface, IP, interfaces físicas e MACs;
4. consultar relações de inventário, console, energia, front/rear ports e bays;
5. bloquear se qualquer consulta falhar ou qualquer relação inesperada existir;
6. criar `REPAIR_JOURNAL` read-only;
7. somente então permitir escrita.

Uma consulta indisponível nunca é interpretada como coleção vazia.

## DELETE restrito

Não existe DELETE genérico no Network.

A única remoção automática da 1.10.14 é um Device duplicado de VM quando todas as condições forem verdadeiras:

- descrição do Device exatamente indica criação pelo produto;
- interfaces e IP mantêm descrições de ownership do produto;
- Device sem serial, rack, location, cluster, virtual chassis ou device bay;
- sem inventory items, console, power, front/rear ports, device bays ou module bays;
- sem cabo ou conexão manual;
- um único IP observado;
- uma única VM por nome;
- uma única VM interface pelo MAC VMware;
- mesmo Tenant/Site;
- VM sem outro primary IPv4.

Se qualquer condição falhar:

```text
BLOCKED
REPAIR_SAFE_NOT_ELIGIBLE
NetBox write: NÃO para o reparo
```

A VM nunca é removida.

## Ordem segura

O IMPORT normal é executado antes do reparo destrutivo. Se o import normal falhar, nenhum Device duplicado é removido.

Cada reparo recebe nova verificação live imediatamente antes da ação.

## Recuperação parcial

Se o IP já tiver sido movido para a VM, mas o Device duplicado ainda existir:

```text
RECOVERY_AFTER_IP_MOVE
```

A próxima execução pode concluir somente a limpeza restante, desde que todas as proteções continuem válidas.

## MD32xx

A união automática de controladoras exige:

```text
sysObjectID exato
mesmo sysName não genérico
exatamente dois endpoints
STORAGE/HIGH
IPs consecutivos
sem serial conflitante
```

Nome igual sozinho nunca autoriza merge.

## Ownership Hypervisor

```text
IP em virtualization.vminterface → DELEGATED/NOOP
```

A ponte por nome só acrescenta ownership quando o IP não o prova. Nunca rebaixa um `DELEGATED` já autoritativo.

## Identidade anti-flap

Identidade VMware e storage forte podem ser preservadas por até 48 horas no mesmo Site/IP. Histórico não injeta MAC antigo em interface e não vence identidade física forte atual.

`connUnitId=000...000` não é identidade.

## Auditoria 1.10.14

O audit combinado confirma:

- convergência dos READY normais;
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
