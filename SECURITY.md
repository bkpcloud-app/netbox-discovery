# Segurança do repositório

**Versão da política:** 1.10.4

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

Dependências Python ficam isoladas em:

```text
/opt/netbox-discovery/vendor
```

## Multi-Tenant / multi-Site — 1.10+

- Host é resolvido por mappings de rede de gerenciamento autoritativa;
- VM herda o contexto do Host como primeira escolha;
- sem mapping confiável o objeto vira `REVIEW`;
- o produto não deve adivinhar Tenant/Site pelo nome da VM;
- criação/reuso de Tenant Group/Tenant/Site durante o wizard é estrutural e explícita; não equivale a importar Hosts/VMs.

### VMware — rede autoritativa 1.10.3

Um ESXi pode ter vários vmkernel com o serviço VMware `management` habilitado. A presença desse serviço é **evidência de interface**, não autorização para transformar todas essas redes em mappings de Site.

Para posicionamento Tenant/Site, a seleção é conservadora:

1. IP de vmkernel que corresponde à resolução do FQDN/nome do ESXi;
2. `vmk0` marcada como management;
3. única rede management candidata;
4. múltiplas candidatas sem evidência forte → sem resolução automática / `REVIEW`.

Regras:

- redes auxiliares continuam disponíveis no inventário, mas não decidem Site;
- mappings não são criados para todas as interfaces somente porque `management=True`;
- mappings existentes divergentes não são consolidados silenciosamente;
- Tenant/Site continua sendo confirmação explícita;
- o configurador não executa IMPORT de Hosts/VMs;
- qualquer incerteza termina em revisão, não em inferência silenciosa.

## Reclassificação segura — 1.10.4

A ação `RECLASSIFY_SAFE` existe para corrigir um objeto que já está no NetBox sob Tenant/Site incorreto sem criar uma duplicata.

Ela só pode ficar `READY` quando a identidade global é inequívoca por uma ou mais evidências fortes:

- serial/UUID único;
- IP já vinculado ao mesmo objeto;
- MAC já vinculado ao mesmo objeto.

Proteções obrigatórias:

- nome sozinho nunca autoriza migração;
- serial/UUID duplicado globalmente → `REVIEW`;
- mais de um dono de IP/MAC → `REVIEW`;
- serial e IP/MAC apontando para objetos diferentes → `REVIEW`;
- `RECLASSIFY_SAFE` não escreve sem `--apply`;
- o mesmo ID do objeto é preservado;
- IPs vinculados ao objeto podem ter o Tenant ajustado para acompanhar o objeto;
- Cluster/Prefix só são reclassificados quando existe uma única correspondência global segura;
- nenhuma reclassificação executa DELETE.

Até a homologação ao vivo da 1.10.4, manter APPLY automático Hypervisor desabilitado.

## Delta de inventário — 1.10.4

A ausência de uma VM entre o snapshot anterior e o discovery atual é tratada como evidência de mudança, não como autorização de exclusão.

```text
VM ausente → REVIEW / NOOP
DELETE automático → NÃO
```

Isso protege contra exclusões causadas por indisponibilidade temporária, mudança de visibilidade do manager ou remoção ainda não revisada.

## Dados de cliente em mappings

`hypervisors.json` pode conter nomes de Tenant/Site e evidências de hosts/Datacenters/Clusters, além de credenciais. Trate o arquivo inteiro como sensível.

## Atualização

O updater stable:

- faz backup antes da troca;
- valida candidato;
- preserva configuração;
- executa rollback quando a validação pós-instalação falha;
- bloqueia downgrade;
- usa quarentena para versão quebrada.

Desde a 1.10.1, documentação obrigatória entra na validação de release. Uma versão cujo manual/documentação não corresponda ao `VERSION` deve falhar no self-test/CI.

## Homologação

`CI PASS` não significa `LIVE PASS`.

A matriz oficial fica em:

```text
docs/HOMOLOGACAO.md
```

Não habilitar APPLY automático para funcionalidade marcada como `NOT LIVE` até a homologação real correspondente.
