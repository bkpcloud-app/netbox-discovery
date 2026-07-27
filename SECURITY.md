# Segurança do repositório

**Versão da política:** 1.10.7

O `netbox-discovery` é distribuído em repositório público. Código e documentação podem ser públicos; **dados operacionais e credenciais de clientes não podem**.

## Nunca versionar

- `/opt/netbox-discovery/config.yml` real;
- `/etc/netbox-discovery/hypervisors.json` real;
- token do NetBox;
- community SNMP real;
- senha/segredo VMware, Proxmox ou Hyper-V;
- chave SSH privada;
- `.env` com credenciais;
- relatórios de discovery/plan/import/audit/compare de clientes;
- logs de clientes;
- backups de configuração de clientes.

## Comportamento seguro

- `netbox-discovery run` é dry-run por padrão;
- `netbox-discovery hypervisor run` é dry-run por padrão;
- `netbox-discovery hypervisor run --compare` é somente leitura;
- escrita manual exige `--apply`;
- somente `READY` é elegível para escrita;
- `REVIEW` não escreve;
- `BLOCKED` não escreve;
- AUDIT é read-only;
- Hypervisor não executa DELETE automático;
- Network, Hypervisor, Compare e Update compartilham lock global;
- retry automático é reservado a GETs seguros;
- POST/PATCH não recebem retry cego;
- falha parcial de APPLY Hypervisor mantém journal das escritas;
- schedulers Network/Hypervisor são opt-in.

## Recuperação após APPLY parcial — 1.10.7

Uma falha depois de algumas escritas não autoriza rollback cego nem repetição imediata do `--apply`.

Procedimento seguro:

```text
1. preservar o estado atual e o journal
2. não corrigir objetos em massa manualmente
3. executar compare read-only
4. executar novo dry-run
5. revisar divergências
6. somente depois considerar novo APPLY
```

Comando oficial:

```bash
netbox-discovery hypervisor run --compare
```

O compare:

- reutiliza o planner/identity guard de produção;
- lê estado atual do NetBox e das sources;
- compara Tenant/Site atual e esperado;
- não executa POST/PATCH;
- usa o lock global;
- gera relatório JSON para auditoria.

## Migração coordenada de Cluster/Site — 1.10.7

Quando um Cluster com `scope` de Site e seus Devices-host precisam mudar juntos de Site, existe dependência circular de validação: não é seguro mover o Cluster enquanto hosts continuam no Site antigo, nem mover hosts enquanto o Cluster continua scoped no Site antigo.

A transição permitida pelo produto é:

```text
RECLASSIFY PREFLIGHT
→ validar todos os membros
→ remover temporariamente o scope opcional do Cluster
→ mover Devices-host
→ reaplicar Tenant/scope do Cluster no Site alvo
→ continuar VMs
```

Travas obrigatórias:

- cada Device-host fora do Site alvo deve ter `HOST / RECLASSIFY_SAFE` correspondente no mesmo contexto;
- Cluster deve permanecer correspondência global única;
- identidade dos Hosts deve permanecer forte e apontar para o mesmo ID;
- host com rack/location não muda automaticamente de Site;
- mudança na composição esperada do Cluster deve abortar o contexto;
- nenhuma etapa executa DELETE.

## Preflight antes da primeira escrita — 1.10.6+

Nenhum `RECLASSIFY_SAFE`, `CREATE` ou `UPDATE_SAFE` pode iniciar antes do preflight global multi-contexto.

O APPLY deve obrigatoriamente:

1. reconstruir o PLAN contra o estado atual do NetBox;
2. abortar se surgir qualquer `REVIEW` ou `BLOCKED`;
3. confirmar que o conjunto de `RECLASSIFY_SAFE` permaneceu idêntico;
4. confirmar o mesmo `existing_id`, Tenant alvo e Site alvo;
5. executar uma revalidação de identidade forte imediatamente antes de cada lote de reclassificação;
6. somente então permitir POST/PATCH.

A revalidação de identidade deve confirmar novamente:

- serial/UUID;
- IP/MAC vinculados;
- unicidade do objeto;
- `existing_id` esperado;
- Cluster/Prefix único quando aplicável;
- Tenant/Site alvo existente e único.

Qualquer drift entre PLAN e APPLY aborta antes da escrita correspondente.

## Transparência do PLAN — 1.10.5+

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
