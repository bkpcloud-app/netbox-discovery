# Segurança do repositório

**Versão da política:** 1.10.11

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

## Storage identity — 1.10.11

Storages com múltiplas controladoras/IPs de gerenciamento não podem ser unidos apenas por nome, fabricante ou modelo.

Quando disponível, a identidade de array pode usar FCMGMT/FibreAlliance:

```text
connUnitType = storage-subsystem(11)
connUnitId   = identidade forte do array
connUnitSn   = serial preferencial quando válido
```

Regras obrigatórias:

- mesmo `connUnitId` válido pode permitir merge de registros STORAGE;
- `connUnitId` diferente impede merge por essa regra;
- nome repetido sozinho nunca autoriza merge;
- MACs diferentes de controladoras não impedem merge quando a identidade FA do array é a mesma;
- SNMP EngineID não é usado como identidade do array;
- sem evidência FA suficiente, manter comportamento conservador;
- falha na coleta FA-MIB não deve transformar REVIEW/BLOCKED em READY.

## Ownership Hypervisor — 1.10.10

Quando todos os IPs observados de um asset Network já estão atribuídos no NetBox a `virtualization.vminterface`:

```text
DELEGATED
NOOP
OWNED_BY_HYPERVISOR_VM
```

Requisitos:

- não criar `dcim.device`;
- não mover/reatribuir o IP;
- não alterar a VM;
- não consumir o registro no IMPORT Network.

## VM candidata sem match

```text
REVIEW
VIRTUAL_MACHINE_CANDIDATE_NO_VM_MATCH
```

Nunca converter automaticamente em equipamento físico apenas porque o Hypervisor ainda não correlacionou a VM.

## Classificação física

Fingerprint de sistema operacional/SSH não pode superar identidade explícita de hardware quando esta define a função do equipamento.

Modelos Dell Networking reconhecidos por hardware/ENTITY-MIB são classificados como `NETWORK_SWITCH` antes das regras genéricas Linux/Web/SNMP.

## Identidade Network

- serial válido é forte;
- MAC de gerenciamento autoritativo é forte;
- `connUnitId` válido é forte para storage FibreAlliance;
- MAC secundário não funde asset sozinho;
- LLDP chassis ID válido pode ser forte;
- nome sozinho não é identidade global;
- IP de VM pertencente a `virtualization.vminterface` não é apropriado pelo Network.

## APPLY Network

- `run` é dry-run;
- `run --apply` exige autorização explícita;
- apenas `READY` entra no importer;
- planner é recalculado antes do IMPORT;
- primeiro erro inesperado em APPLY interrompe o lote;
- não fazer correções em massa manuais para contornar o PLAN.

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

POST/PATCH não recebem retry cego.

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
