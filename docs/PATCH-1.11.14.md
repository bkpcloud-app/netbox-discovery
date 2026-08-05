# netbox-discovery 1.11.14

## Objetivo

Garantir que clientes com scheduler de coleta habilitado permaneçam automaticamente na versão mais recente do canal `stable` e impedir publicação de releases com manual desatualizado.

## Auto-update associado aos schedulers

Os timers abaixo passam a declarar dependência do timer de atualização:

```text
netbox-discovery.timer
netbox-discovery-hypervisor.timer
```

Dependência aplicada:

```ini
Wants=netbox-discovery-update.timer
After=netbox-discovery-update.timer
```

Com isso:

- habilitar scheduler Network inicia o auto-update;
- habilitar scheduler Hypervisor inicia o auto-update;
- instalações antigas também entram no fluxo de upgrade;
- a coleta continua independente da atualização;
- desabilitar a coleta não desabilita o auto-update;
- `automation.apply` não é alterado.

A implementação não usa `Also=`, porque essa opção faria o disable do scheduler de coleta também desabilitar o timer de atualização.

## Política de atualização preservada

```text
Canal: stable
Frequência: diária
Persistent: true
RandomizedDelaySec: 30m
Self-test antes e depois
Rollback automático em falha
```

## Documentação corrigida

Os documentos principais estavam em 1.11.2 enquanto o produto já estava em 1.11.13. A release 1.11.14 atualiza:

```text
README.md
docs/MANUAL.md
docs/COMANDOS-RAPIDOS.md
docs/HOMOLOGACAO.md
RELEASE-NOTES.md
SECURITY.md
```

## Novo bloqueio de CI

O CI passa a exigir a versão exata `1.11.14` em todos os documentos obrigatórios. Verificar apenas a família `1.11` não é mais aceito.

## Segurança

- nenhuma descoberta é iniciada pela atualização;
- nenhum APPLY é habilitado;
- nenhuma escrita no NetBox é executada;
- configuração e credenciais são preservadas;
- scheduler Network e Hypervisor continuam opt-in;
- auto-update permanece habilitado por padrão e com rollback.
