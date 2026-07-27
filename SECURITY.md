# Segurança do repositório

**Versão da política:** 1.10.9

O `netbox-discovery` é distribuído em repositório público. Código e documentação podem ser públicos; **dados operacionais e credenciais de clientes não podem**.

## Nunca versionar

- `/opt/netbox-discovery/config.yml` real;
- `/etc/netbox-discovery/hypervisors.json` real;
- token do NetBox;
- community SNMP real;
- senha/segredo VMware, Proxmox ou Hyper-V;
- chave SSH privada;
- `.env` com credenciais;
- relatórios reais de discovery/plan/import/audit/compare;
- logs e backups de clientes.

## Comportamento seguro

- `netbox-discovery run` é dry-run por padrão;
- `netbox-discovery run --apply` escreve somente `READY` e executa AUDIT;
- `netbox-discovery hypervisor run` é dry-run por padrão;
- `netbox-discovery hypervisor run --compare` é somente leitura;
- escrita exige `--apply`;
- `REVIEW` não escreve;
- `BLOCKED` não escreve;
- AUDIT é read-only;
- não existe DELETE automático no Hypervisor;
- Network, Hypervisor, Compare e Update compartilham lock global;
- retry automático é reservado a GETs seguros;
- POST/PATCH não recebem retry cego;
- schedulers Network/Hypervisor são opt-in.

## Transparência do PLAN Network — 1.10.9

Segurança operacional não deve depender de abrir JSON nem executar Python ad-hoc.

O `netbox-discovery run` deve mostrar:

```text
NETWORK PLAN DIAGNÓSTICO
NETWORK NOVOS OBJETOS READY
NETWORK AJUSTES READY
NETWORK PENDÊNCIAS POR MOTIVO
NETWORK PENDÊNCIAS DETALHADAS
NetBox write: NÃO
```

Para cada `REVIEW`/`BLOCKED`, mostrar pelo menos:

- IP e nome desejado;
- role e confiança;
- motivos;
- match state/reason;
- fabricante/modelo/serial;
- sinais SNMP disponíveis;
- evidência CLASSIFY.

A visibilidade do diagnóstico **não pode alterar automaticamente a decisão** do PLAN.

## Política Network

O PLAN deve permanecer conservador:

- confiança abaixo de HIGH → `REVIEW`;
- role UNKNOWN → `REVIEW`;
- OOB standalone → `REVIEW`;
- conflito de identidade → `BLOCKED`;
- IP pertencente a outro Device → `BLOCKED`;
- IP associado a objeto externo → `REVIEW` até existir regra explícita e testada para esse tipo;
- drift de inventário não vazio não é sobrescrito cegamente.

Somente `READY` é consumido pelo importer.

## Identidade Network

- serial válido é evidência forte;
- MAC de gerenciamento autoritativo é evidência forte;
- MAC secundário/interface não pode fundir assets sozinho;
- LLDP chassis ID válido pode ser evidência forte;
- nome sozinho não é identidade global;
- múltiplos IPs do mesmo equipamento não devem criar múltiplos Devices quando identidade forte prova que é o mesmo asset.

## Recuperação após APPLY parcial

Uma falha depois de escritas não autoriza rollback cego nem repetição imediata do `--apply`.

```text
1. preservar estado/journal/relatórios
2. confirmar processo/lock
3. não corrigir objetos em massa manualmente
4. executar compare ou dry-run apropriado
5. revisar divergências
6. somente depois considerar novo APPLY
```

## Preflight global Hypervisor — 1.10.6+

Antes da primeira escrita Hypervisor:

1. reconstruir PLAN atual;
2. abortar com `REVIEW/BLOCKED`;
3. confirmar `RECLASSIFY_SAFE` inalterado;
4. confirmar `existing_id`, Tenant e Site alvo;
5. revalidar identidade forte;
6. somente então permitir POST/PATCH.

## Cluster/Site — 1.10.7

```text
RECLASSIFY PREFLIGHT
→ remove temporariamente scope do Cluster
→ move Devices-host
→ reaplica scope no Site alvo
→ continua VMs
```

Hosts com rack/location ou composição inesperada bloqueiam migração automática.

## VM/Parent — 1.10.8

```text
Host/Cluster já migrado
→ revalida identidade da VM
→ relê Parent
→ confirma Parent no Site alvo
→ PATCH tenant + site juntos
→ ajusta Tenant dos IPs
```

Se Parent estiver fora do Site alvo, o lote de VMs é bloqueado.

## Delta de inventário

Ausência em snapshot não autoriza DELETE automático.

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
- segredos mascarados;
- nunca publicar arquivo real.

## Atualização

O updater `stable`:

- cria backup;
- valida candidato;
- preserva configuração;
- executa rollback em falha de validação;
- bloqueia downgrade;
- usa quarentena para versão quebrada.

## Homologação

`CI PASS` não significa `LIVE PASS`.

```text
docs/HOMOLOGACAO.md
```

Não habilitar APPLY automático para funcionalidade marcada como `NOT LIVE`.
