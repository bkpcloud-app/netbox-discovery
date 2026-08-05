# netbox-discovery 1.11.15

## Objetivo

Garantir que toda execução automática use a versão estável mais recente disponível antes de iniciar a coleta.

## Comportamento anterior

Na 1.11.14, habilitar o scheduler também garantia que o timer diário de atualização estivesse ativo. Porém, o timer de update e a coleta eram independentes: uma coleta podia começar antes da próxima verificação diária.

## Correção

Os serviços systemd Network e Hypervisor agora executam:

```text
ExecStartPre=-/usr/local/bin/netbox-discovery update scheduled
```

Depois do preflight:

```text
Network    → /usr/local/bin/netbox-discovery scheduled-run
Hypervisor → /usr/local/bin/netbox-discovery hypervisor scheduled-run
```

## Sequência efetiva

```text
consultar stable
→ sem atualização: continuar
→ com atualização: validar candidato
→ criar backup
→ instalar preservando configuração
→ self-test/check
→ sucesso: continuar na nova versão
→ falha: rollback + quarentena
→ iniciar coleta
```

## Indisponibilidade do GitHub

A falha de consulta ou download é registrada no journal e no estado do updater. A coleta não é cancelada e usa a versão instalada.

Essa tolerância não afeta segurança de dados:

- nenhum APPLY é ativado;
- `automation.apply` não é modificado;
- nenhuma rede, exclusão, community ou credencial é alterada;
- o updater e os coletores continuam usando o lock global.

## Validação

A regressão 1.11.15 verifica:

- `ExecStartPre` presente nos dois serviços;
- preflight anterior ao `ExecStart`;
- chamada ao canal `stable` pelo updater;
- fallback sem cancelamento da coleta;
- separação entre update e APPLY;
- documentação na versão exata;
- compatibilidade dos testes históricos por versão mínima.
