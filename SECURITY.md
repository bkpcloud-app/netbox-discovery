# Segurança do repositório

**Versão da política:** 1.10.12

O `netbox-discovery` é distribuído em repositório público. Código e documentação podem ser públicos; dados operacionais e credenciais de clientes não podem.

## Nunca versionar

- configuração real de cliente;
- token NetBox;
- community SNMP real;
- senhas VMware/Proxmox/Hyper-V;
- chaves privadas;
- relatórios/logs/backups reais de clientes.

## Decisões Network

```text
READY       → elegível para escrita somente com --apply
DELEGATED   → ownership externo; nunca escreve no Network
REVIEW      → não escreve
BLOCKED     → não escreve
```

## Anti-flap de identidade — 1.10.12

Uma ausência de evidência em uma coleta não prova que a identidade anterior deixou de ser válida.

O produto pode reter por até 48 horas, no mesmo Site/IP, somente evidência forte já observada:

- `VIRTUAL_MACHINE_CANDIDATE` respaldado por OUI VMware;
- storage respaldado por serial válido e/ou `connUnitId` válido.

Regras obrigatórias:

- identidade física forte atual vence histórico VMware;
- serial atual diferente do histórico → conflito;
- `connUnitId` atual diferente do histórico → conflito;
- `connUnitId=000...000` não é identidade;
- MAC VMware histórico não pode ser usado para criar/alterar MAC de interface;
- histórico serve para decisão/ownership, não para inventar dados atuais;
- ausência transitória de MAC/FA-MIB não pode transformar uma VM/storage conhecido em Device genérico READY.

## Ownership Hypervisor por nome único — 1.10.12

Para um asset com identidade VMware, o planner consulta VMs do mesmo Tenant/Site.

```text
VM candidate + uma única VM com mesmo nome
→ DELEGATED/NOOP
```

Se já existir Device físico:

```text
BLOCKED/CONFLICT
PHYSICAL_DEVICE_CONFLICT_WITH_HYPERVISOR_VM:<id>
```

Nenhuma remoção automática é permitida por essa regra.

## Storage identity — 1.10.11+

Storages com múltiplas controladoras/IPs de gerenciamento não podem ser unidos apenas por nome, fabricante ou modelo.

Quando disponível, a identidade de array usa FCMGMT/FibreAlliance:

```text
connUnitType = storage-subsystem(11)
connUnitId   = identidade forte quando válido
connUnitSn   = serial forte quando válido
```

Regras:

- mesmo serial/`connUnitId` válido pode permitir merge de registros STORAGE;
- identidade diferente impede merge;
- nome repetido sozinho nunca autoriza merge;
- MACs diferentes de controladoras não impedem merge quando a identidade de array é a mesma;
- SNMP EngineID não é identidade do array;
- até três tentativas FA-MIB são permitidas porque são somente leitura;
- sem evidência forte, manter REVIEW/BLOCKED.

## Ownership Hypervisor por IP — 1.10.10+

Quando todos os IPs observados já estão atribuídos a `virtualization.vminterface`:

```text
DELEGATED
NOOP
OWNED_BY_HYPERVISOR_VM
```

Não criar `dcim.device`, não mover IP e não alterar VM.

## VM candidata sem match

```text
REVIEW
VIRTUAL_MACHINE_CANDIDATE_NO_VM_MATCH
```

Nunca converter automaticamente em equipamento físico apenas porque a correlação Hypervisor ainda não ocorreu.

## Classificação física

Fingerprint de sistema operacional/SSH não pode superar identidade explícita de hardware.

Modelos Dell Networking reconhecidos por hardware/ENTITY-MIB são classificados antes de regras genéricas Linux/Web/SNMP.

## APPLY Network

- `run` é dry-run;
- `run --apply` exige autorização explícita;
- apenas `READY` entra no importer;
- importer 1.10.12 recalcula com `planner_v3.py` antes da escrita;
- primeiro erro inesperado interrompe o lote;
- não fazer correções em massa manuais para contornar o PLAN;
- conflito conhecido não é apagado automaticamente.

## AUDIT

AUDIT é read-only e usa o planner atual para idempotência.

A 1.10.12 imprime WARN/FAIL detalhados no terminal, além dos JSON/CSV.

## Hypervisor

- `hypervisor run` é dry-run;
- `hypervisor run --compare` é read-only;
- `hypervisor run --apply` usa preflight global;
- Cluster/Site e VM/Parent possuem preflight específico;
- não existe DELETE automático.

## Concorrência

Network, Hypervisor, Compare e Update compartilham:

```text
/var/lock/netbox-discovery-global.lock
```

POST/PATCH não recebem retry cego. Retries FA-MIB são apenas leituras SNMP.

## Credenciais Hypervisor

```text
/etc/netbox-discovery/hypervisors.json
```

Permissão esperada: `0600`.

## Update

O canal `stable` usa backup, validação, preservação da configuração e rollback de candidato inválido.

## Homologação

`CI PASS` não significa `LIVE PASS`.

```text
docs/HOMOLOGACAO.md
```

Funcionalidade `NOT LIVE` não deve receber APPLY automático.
