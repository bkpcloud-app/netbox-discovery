# Segurança do repositório

**Versão da política:** 1.11.0

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
READY/REPAIR_SAFE_VM_DUPLICATE  → escreve após write guard e preflight global
READY/NOOP                      → não altera
DELEGATED                       → não escreve
REVIEW                          → não escreve
BLOCKED                         → não escreve
```

## Autoridade e nomes

```text
Nome de Device existente → autoridade do NetBox
Nome SNMP/ONVIF/DNS      → observação separada
PATCH automático de name → proibido no importer V10
```

O schedule não pode desfazer uma alteração manual de nome.

## Write guard

Antes da primeira escrita, o PLAN V9 mede:

- CREATE;
- UPDATE_SAFE;
- REPAIR_SAFE;
- total de mudanças;
- percentual sobre Devices existentes.

Se qualquer limite for excedido, todas as ações elegíveis são convertidas para BLOCKED/NOOP antes do importer.

O importer recalcula o PLAN V9 imediatamente antes da escrita. Não é permitido usar um PLAN antigo para APPLY.

## Preflight global

Antes da primeira escrita:

1. recalcular o PLAN V9;
2. validar write guard, READY normais e REPAIR_SAFE;
3. reler Device, VM, interfaces, IPs, MACs e relacionamentos;
4. bloquear qualquer drift ou consulta incompleta;
5. criar journal;
6. somente então permitir escrita.

## Coleta industrial e CFTV

As consultas são exclusivamente read-only. O produto usa evidências de identidade como:

```text
SNMP GET/WALK
Siemens S7 information
EtherNet/IP CIP Identity
BACnet information
Modbus device identification
ONVIF/WS-Discovery
Printer-MIB
```

Não executa SNMP SET nem comando de controle industrial. Quando não existe prova de modelo/função, o ativo continua genérico e entra em REVIEW.

## Físico versus virtual

Correspondência com `virtualization.vminterface` e inventário central é autoritativa. OUI de VMware, Hyper-V, KVM, Xen ou VirtualBox sozinho é apenas indício.

```text
VIRTUAL_CANDIDATE sem VM central → REVIEW/NOOP
```

Isso impede criação automática de Device físico para uma VM ainda não correlacionada.

## Virtualização centralizada

Filiais podem operar como `network_proxy` com `virtualization.mode=centralized`. Ausência de configuração local de vCenter não é falha nesse modo.

## Printer-MIB

A coleta consulta apenas OIDs de identidade:

```text
prtGeneralPrinterName
prtGeneralSerialNumber
hrDeviceDescr
```

A ausência de resposta não é interpretada como identidade de impressora.

## Upgrade de Device Type genérico

A alteração automática de Device Type é permitida somente quando:

- o Device possui descrição exata `Criado pelo netbox-discovery`;
- o match é forte por SERIAL, MAC ou IP;
- a classificação atual é `HIGH`;
- o tipo atual ainda é reconhecidamente genérico;
- fabricante e modelo destino são explícitos e não genéricos;
- o importer revalida tudo imediatamente antes do PATCH.

Device manual, Device Type específico, confiança baixa ou mudança concorrente bloqueiam.

## Preservação de identidade live

Quando uma observação fica fraca, mas a identidade forte aponta para Device existente com tipo específico, o PLAN preserva os campos live em `READY/NOOP`. Esse caminho não escreve.

## Colisão de nomes

Um `sysName` repetido só é desambiguado automaticamente quando todos os objetos são físicos, `HIGH`, novos e possuem serial/MAC únicos. Conflito de IP, identidade fraca ou objeto existente mantêm REVIEW/BLOCKED.

## Gerenciamento OOB

Um iDRAC com service tag correspondente a servidor físico existente é apresentado como candidato de associação. A criação independente permanece em REVIEW até ser segura.

## Regra de primary IP

Para reparo em modo `FULL`:

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

Não existe DELETE genérico no Network. A VM nunca é removida.

A única remoção automática é um Device duplicado de VM quando existe ownership integral do produto e ausência de vínculos manuais.

## Concorrência e rastreabilidade

Network, Hypervisor, Compare e Update compartilham lock global.

- cada runner recebe `run_id`;
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
