# Segurança do repositório

**Versão da política:** 1.10.8

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
- `netbox-discovery hypervisor run` é dry-run por padrão;
- `netbox-discovery hypervisor run --compare` é somente leitura;
- escrita manual exige `--apply`;
- somente `READY` escreve;
- `REVIEW` não escreve;
- `BLOCKED` não escreve;
- AUDIT é read-only;
- Hypervisor não executa DELETE automático;
- Network, Hypervisor, Compare e Update compartilham lock global;
- retry automático é reservado a GETs seguros;
- POST/PATCH não recebem retry cego;
- falha parcial de APPLY mantém journal;
- schedulers Network/Hypervisor são opt-in.

## Recuperação após APPLY parcial

Uma falha depois de algumas escritas não autoriza rollback cego nem repetição imediata do `--apply`.

```text
1. preservar estado e journal
2. confirmar que processo/lock terminou
3. não corrigir objetos em massa manualmente
4. executar compare read-only
5. executar dry-run se necessário
6. revisar divergências
7. somente depois considerar novo APPLY
```

Comando:

```bash
netbox-discovery hypervisor run --compare
```

O compare não executa POST/PATCH.

## Preflight global — 1.10.6+

Antes da primeira escrita Hypervisor:

1. reconstruir PLAN contra o estado atual do NetBox;
2. abortar se surgir `REVIEW`/`BLOCKED`;
3. confirmar conjunto `RECLASSIFY_SAFE` inalterado;
4. confirmar `existing_id`, Tenant e Site alvo;
5. revalidar identidade forte imediatamente antes da reclassificação;
6. somente então permitir POST/PATCH.

Qualquer drift bloqueia a escrita correspondente.

## Migração coordenada de Cluster/Site — 1.10.7

Quando Cluster scoped e Devices-host precisam mudar juntos de Site:

```text
RECLASSIFY PREFLIGHT
→ validar membros
→ remover temporariamente scope do Cluster
→ mover Devices-host
→ reaplicar Tenant/scope do Cluster no Site alvo
→ continuar VMs
```

Travas:

- todos os hosts membros fora do Site alvo precisam ter `HOST / RECLASSIFY_SAFE` no mesmo contexto;
- Cluster deve permanecer único;
- identidade dos Hosts deve continuar forte;
- rack/location bloqueia mudança automática de Site;
- composição inesperada do Cluster aborta o contexto;
- sem DELETE automático.

## VM vinculada acompanha Parent — 1.10.8

Uma VM herda Tenant/Site do Host/Cluster autoritativo. Reclassificar apenas o Tenant enquanto o Device já mudou de Site produz um estado inválido no NetBox.

A sequência segura é:

```text
Host/Cluster já migrado
→ revalidar identidade da VM
→ reler Device/Cluster atual
→ confirmar Parent no Site alvo
→ PATCH VM tenant + site atomicamente
→ ajustar Tenant dos IPs vinculados
```

Travas:

- Device associado precisa estar no Site alvo;
- Cluster associado não pode estar scoped em outro Site;
- identidade da VM é revalidada após a migração do Parent;
- `existing_id` deve permanecer igual;
- se o Parent estiver fora do alvo, nenhuma VM daquele contexto é reclassificada;
- sem DELETE automático.

A lógica é genérica e não depende de cliente, Site ou IP específico.

## Transparência do PLAN

O dry-run deve mostrar no terminal:

- todos os `READY/CREATE`;
- todos os `READY/UPDATE_SAFE`;
- todos os `READY/RECLASSIFY_SAFE`;
- todos os `REVIEW`;
- todos os `BLOCKED`;
- resumo explícito com `NetBox write: NÃO`.

JSON é evidência/auditoria, não requisito para descobrir ações do PLAN.

## Multi-Tenant / multi-Site

- Host é resolvido por rede de gerenciamento autoritativa;
- VM herda contexto do Host como primeira escolha;
- sem mapping confiável o objeto vira `REVIEW`;
- nome da VM sozinho nunca decide Tenant/Site.

## Reclassificação segura

`RECLASSIFY_SAFE` exige identidade inequívoca por:

- serial/UUID único;
- IP vinculado ao mesmo objeto;
- MAC vinculado ao mesmo objeto.

Proteções:

- nome sozinho nunca autoriza migração;
- serial/UUID duplicado → `REVIEW`;
- múltiplos donos de IP/MAC → `REVIEW`;
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
- nunca publicar o arquivo real.

## Atualização

O updater `stable`:

- cria backup;
- valida candidato;
- preserva configuração;
- executa rollback quando a validação pós-instalação falha;
- bloqueia downgrade;
- usa quarentena para versão quebrada.

## Homologação

`CI PASS` não significa `LIVE PASS`.

```text
docs/HOMOLOGACAO.md
```

Não habilitar APPLY automático para funcionalidade marcada como `NOT LIVE`.
