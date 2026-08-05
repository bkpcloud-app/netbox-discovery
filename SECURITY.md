# Segurança do repositório

**Versão da política:** 1.11.15

O `netbox-discovery` é distribuído em repositório público. Código e documentação podem ser públicos; dados operacionais e credenciais de clientes não podem.

## Nunca versionar

- configuração real de cliente;
- tokens, communities e senhas;
- credenciais NetBox, VMware, Proxmox, Hyper-V, ONVIF ou iDRAC;
- chaves privadas;
- relatórios, journals, logs e backups reais;
- listas privadas de IPs e redes de clientes.

## Atualização automática

A atualização usa exclusivamente o canal `stable`.

Antes da instalação:

- valida a versão remota;
- clona o pacote candidato;
- compara versões raiz e pacote;
- executa self-test;
- cria backup da versão instalada.

Depois da instalação:

- executa self-test;
- executa `check` quando existe configuração;
- grava estado do updater;
- executa rollback em falha;
- coloca a versão defeituosa em quarentena.

## Preflight antes da coleta automática

Na 1.11.15, Network e Hypervisor executam:

```text
ExecStartPre=-/usr/local/bin/netbox-discovery update scheduled
```

O prefixo de tolerância existe para impedir que uma indisponibilidade externa do GitHub interrompa o inventário. Isso não ignora falha silenciosamente: o erro permanece no journal e em `update-state.json`.

A coleta só continua com:

- a nova versão validada; ou
- a versão anterior preservada/recuperada.

## Separação entre update e APPLY

O updater não pode:

- alterar `automation.apply`;
- habilitar escrita no NetBox;
- executar `run --apply`;
- alterar redes, exclusões ou communities;
- substituir token ou configuração do cliente.

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

Isso impede atualização e inventário concorrentes sobre a mesma instalação.

## Documentação obrigatória

O CI exige que README, Manual, Comandos Rápidos, Homologação, Release Notes, Security e nota de patch carreguem a versão exata do `VERSION`.
