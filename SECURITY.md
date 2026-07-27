# Segurança do repositório

**Versão da política:** 1.10.1

O `netbox-discovery` é distribuído em repositório público. Código e documentação podem ser públicos; **dados operacionais e credenciais de clientes não podem**.

## Nunca versionar

- `/opt/netbox-discovery/config.yml` real;
- `/etc/netbox-discovery/hypervisors.json` real;
- token do NetBox;
- community SNMP real;
- senha/segredo VMware, Proxmox ou Hyper-V;
- chave SSH privada;
- chave `.pem`;
- `.env` com credenciais;
- relatórios de discovery/plan/import/audit de clientes;
- logs de clientes;
- backups de configuração de clientes.

O `.gitignore` deve permanecer alinhado com essa política.

## Comportamento seguro do produto

- `netbox-discovery run` é read-only em relação ao inventário NetBox;
- `netbox-discovery hypervisor run` é read-only em relação ao inventário NetBox;
- escrita manual exige `--apply`;
- somente registros `READY` são elegíveis para escrita;
- `REVIEW` não escreve;
- `BLOCKED` não escreve;
- APPLY executa novo PLAN/preflight antes da primeira escrita;
- AUDIT é read-only;
- Hypervisor não executa DELETE automático;
- Network, Hypervisor e Update compartilham lock global;
- retry automático é reservado a leituras GET seguras;
- POST/PATCH não recebem retry cego;
- falha parcial de APPLY Hypervisor mantém journal das escritas concluídas;
- schedulers Network/Hypervisor são opt-in.

## NetBox

Endpoint fixo do produto:

```text
https://inventory.bkpcloud.app.br:8080
```

Uma URL diferente no `config.yml` é rejeitada.

## Credenciais Hypervisor

Arquivo:

```text
/etc/netbox-discovery/hypervisors.json
```

Requisitos:

- permissão `0600`;
- proprietário root quando executado como root;
- segredos mascarados em saídas públicas do config;
- nunca incluir cópia desse arquivo em issue, PR, relatório ou documentação.

Dependências Python de conectores ficam isoladas em:

```text
/opt/netbox-discovery/vendor
```

## Multi-Tenant / multi-Site — 1.10+

O modo multi-contexto adiciona regras específicas:

- Host é resolvido por mapping de rede de gerenciamento;
- VM herda o contexto do Host como primeira escolha;
- sem mapping confiável o objeto vira `REVIEW`;
- o produto não deve adivinhar Tenant/Site pelo nome da VM;
- serial/UUID já existente fora do contexto alvo vira `REVIEW` em vez de CREATE duplicado;
- reclassificação/migração de objeto existente não é feita automaticamente na 1.10.1;
- criação/reuso de Tenant Group/Tenant/Site durante o wizard é estrutural e explícita; não equivale a importar Hosts/VMs.

## Dados de cliente em mappings

`hypervisors.json` pode conter nomes de Tenant/Site e evidências de hosts/Datacenters/Clusters, além de credenciais. Por isso o arquivo inteiro deve ser tratado como sensível mesmo quando o campo `secret` é mascarado em relatório.

## Atualização

O updater stable:

- faz backup antes da troca;
- valida candidato;
- preserva configuração;
- executa rollback quando a validação pós-instalação falha;
- bloqueia downgrade;
- usa quarentena para versão quebrada.

A partir da 1.10.1, documentação obrigatória também entra na validação de release. Uma versão cujo manual/documentação não corresponda ao `VERSION` deve falhar no self-test/CI.

## Homologação

`CI PASS` não significa `LIVE PASS`.

A matriz oficial fica em:

```text
docs/HOMOLOGACAO.md
```

Não habilitar APPLY automático para funcionalidade marcada como `NOT LIVE` até a homologação real correspondente.
