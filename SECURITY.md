# Segurança do repositório

**Versão da política:** 1.10.19

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

1. recalcular o PLAN V8;
2. validar READY normais e todos os REPAIR_SAFE;
3. reler Device, VM, interfaces, IPs, MACs e relacionamentos;
4. bloquear qualquer drift ou consulta incompleta;
5. criar journal read-only;
6. somente então permitir escrita.

## Printer-MIB

A coleta é exclusivamente read-only. O produto consulta OIDs de identidade e não executa SET SNMP.

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
- o importer revalida todas essas condições imediatamente antes do PATCH.

Device manual, Device Type específico, confiança baixa ou mudança concorrente bloqueiam. Não existe substituição genérica de catálogo.

## Preservação de identidade live

Quando uma observação fica fraca, mas a identidade forte aponta para Device existente com tipo específico, o PLAN preserva os campos live em `READY/NOOP`. Esse caminho não escreve.

## Colisão de nomes

Um `sysName` repetido só é desambiguado automaticamente quando todos os objetos são físicos, `HIGH`, novos e possuem serial/MAC únicos. Conflito de IP, identidade fraca ou objeto existente mantêm `REVIEW/BLOCKED`.

## Regra de primary IP da 1.10.18

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

Não existe DELETE genérico no Network. A VM nunca é removida.

A única remoção automática é um Device duplicado de VM quando existe ownership integral do produto e ausência de vínculos manuais.

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
