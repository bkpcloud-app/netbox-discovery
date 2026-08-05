# Segurança do repositório

**Versão da política:** 1.11.16

O `netbox-discovery` é distribuído em repositório público. Código e documentação podem ser públicos; dados operacionais e credenciais de clientes não podem.

## Nunca versionar

- configuração real de cliente;
- tokens, communities e senhas;
- credenciais NetBox, VMware, Proxmox, Hyper-V, ONVIF ou iDRAC;
- chaves privadas;
- relatórios, journals, logs e backups reais;
- listas privadas de IPs e redes de clientes.

## Atualização automática

A atualização usa o canal `stable`, valida o candidato, cria backup, preserva configuração, executa self-test/check e faz rollback/quarentena quando necessário.

Antes da coleta automática:

```text
ExecStartPre=-/usr/local/bin/netbox-discovery update scheduled
```

Indisponibilidade temporária do GitHub fica registrada e não cancela a coleta com a versão instalada válida.

## Separação entre update e APPLY

O updater não pode:

- alterar `automation.apply`;
- habilitar escrita no NetBox;
- executar `run --apply`;
- alterar redes, exclusões ou communities;
- substituir token ou configuração do cliente.

## Relatórios nativos do PLAN

Os comandos abaixo são estritamente somente leitura:

```text
netbox-discovery plan summary
netbox-discovery plan blocked
netbox-discovery plan review
netbox-discovery plan ready
netbox-discovery plan delegated
netbox-discovery plan all
```

Eles apenas leem JSON já existente em `/opt/netbox-discovery/reports`. Não chamam Importer, não usam `--apply`, não fazem PATCH/POST/DELETE e não modificam o NetBox.

A saída pode conter informações operacionais do cliente. Não deve ser versionada no repositório público.

## Status vinculado ao último RUN

Quando o último RUN é dry-run, `status` deve declarar IMPORT/AUDIT como não executados naquele RUN. É proibido apresentar relatório histórico de APPLY como se pertencesse ao dry-run atual.

## Decisões Network

```text
READY/CREATE       → somente com --apply
READY/UPDATE_SAFE  → somente com --apply
READY/NOOP         → não altera
DELEGATED          → não escreve
REVIEW             → não escreve
BLOCKED            → não escreve
```

## Autoridade dos dados

```text
Nome existente no NetBox → preservado
PATCH automático de name → proibido
Serial conflitante       → não gravado
VM confirmada            → delegada à virtualização
Device manual            → protegido
```

## Lock global

Network, Hypervisor e Updater compartilham:

```text
/var/lock/netbox-discovery-global.lock
```

## Documentação obrigatória

O CI exige que README, Manual, Comandos Rápidos, Homologação, Release Notes, Security e nota de patch carreguem a versão exata do `VERSION`.
