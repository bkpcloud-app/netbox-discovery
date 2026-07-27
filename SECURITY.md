# Segurança do repositório

**Versão da política:** 1.10.5

O `netbox-discovery` é distribuído em repositório público. Código e documentação podem ser públicos; **dados operacionais e credenciais de clientes não podem**.

## Nunca versionar

- `/opt/netbox-discovery/config.yml` real;
- `/etc/netbox-discovery/hypervisors.json` real;
- token do NetBox;
- community SNMP real;
- senha/segredo VMware, Proxmox ou Hyper-V;
- chave SSH privada;
- `.env` com credenciais;
- relatórios de discovery/plan/import/audit de clientes;
- logs de clientes;
- backups de configuração de clientes.

## Comportamento seguro

- `netbox-discovery run` é dry-run por padrão;
- `netbox-discovery hypervisor run` é dry-run por padrão;
- escrita manual exige `--apply`;
- somente `READY` é elegível para escrita;
- `REVIEW` não escreve;
- `BLOCKED` não escreve;
- AUDIT é read-only;
- Hypervisor não executa DELETE automático;
- Network, Hypervisor e Update compartilham lock global;
- retry automático é reservado a GETs seguros;
- POST/PATCH não recebem retry cego;
- falha parcial de APPLY Hypervisor mantém journal das escritas;
- schedulers Network/Hypervisor são opt-in.

## Transparência do PLAN — 1.10.5

A segurança não deve depender de comandos ad-hoc executados pelo operador.

O próprio dry-run Hypervisor deve mostrar no terminal:

- todos os `READY/CREATE`;
- todos os `READY/UPDATE_SAFE`;
- todos os `READY/RECLASSIFY_SAFE`;
- todos os `REVIEW`;
- todos os `BLOCKED`;
- resumo explícito com `NetBox write: NÃO`.

O JSON continua sendo evidência/auditoria, mas não deve ser necessário para descobrir objetos que seriam criados.

## Multi-Tenant / multi-Site

- Host é resolvido por rede de gerenciamento autoritativa;
- VM herda o contexto do Host como primeira escolha;
- sem mapping confiável o objeto vira `REVIEW`;
- o produto não adivinha Tenant/Site pelo nome da VM.

## Reclassificação segura — 1.10.4+

`RECLASSIFY_SAFE` só pode ficar `READY` quando a identidade global é inequívoca por evidência forte:

- serial/UUID único;
- IP já vinculado ao mesmo objeto;
- MAC já vinculado ao mesmo objeto.

Proteções:

- nome sozinho nunca autoriza migração;
- serial/UUID duplicado globalmente → `REVIEW`;
- mais de um dono de IP/MAC → `REVIEW`;
- serial e IP/MAC apontando para objetos diferentes → `REVIEW`;
- o mesmo ID é preservado;
- nenhuma reclassificação executa DELETE.

## Delta de inventário

VM ausente entre snapshots:

```text
REVIEW / NOOP
DELETE automático: NÃO
```

Ausência não autoriza exclusão.

## Endpoint NetBox

```text
https://inventory.bkpcloud.app.br:8080
```

## Credenciais Hypervisor

```text
/etc/netbox-discovery/hypervisors.json
```

Requisitos:

- permissão `0600`;
- proprietário root quando executado como root;
- segredos mascarados em saídas públicas;
- nunca publicar esse arquivo.

## Atualização

O updater `stable`:

- faz backup antes da troca;
- valida candidato;
- preserva configuração;
- executa rollback quando a validação pós-instalação falha;
- bloqueia downgrade;
- usa quarentena para versão quebrada.

## Homologação

`CI PASS` não significa `LIVE PASS`.

Matriz oficial:

```text
docs/HOMOLOGACAO.md
```

Não habilitar APPLY automático para funcionalidade marcada como `NOT LIVE`.
