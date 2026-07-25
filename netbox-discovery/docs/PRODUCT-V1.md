# netbox-discovery Product V1

Versão consolidada do produto. Não é um pacote de Stage/hotfix.

## Pipeline

DISCOVER -> CLASSIFY -> RECONCILE -> PLAN -> IMPORT -> AUDIT

## Comandos principais

- `netbox-discovery init`: configuração inicial; nunca inicia scan.
- `netbox-discovery configure`: altera a configuração; nunca inicia scan.
- `netbox-discovery check`: valida produto/config/dependências.
- `netbox-discovery run`: pipeline até PLAN, sem escrita.
- `netbox-discovery run --apply`: pipeline completo com escrita somente READY e AUDIT.
- `netbox-discovery status`: resumo operacional do último ciclo.
- `netbox-discovery scheduler enable`: habilita timer systemd de acordo com `automation.schedule`.
- `netbox-discovery scheduler disable`: desabilita timer.

## Política de segurança

- IMPORT exige `--apply` ou `automation.apply: true` em execução agendada.
- REVIEW não é importado automaticamente.
- BLOCKED nunca é importado.
- O PLAN consulta IPs globais antes da escrita.
- Import é idempotente e replaneja antes de escrever.
- AUDIT é read-only.
- Installer não habilita scheduler.
- `init`/`configure` não iniciam discovery.

## Correções consolidadas

- Preflight global de IP para evitar POST duplicado.
- Retomada idempotente após falha parcial.
- Preservação conservadora de inventário preexistente.
- Primary IPv4 preexistente preservado gera WARN, não falso FAIL.
- IDs de assets sem serial/MAC não colidem por nomes SNMP genéricos repetidos.
- Contagem de AUDIT usa registros READY reais e não agrupa assets distintos pelo mesmo nome genérico.
- Idempotency preview usa chave composta por asset/name/IP, inclusive para relatórios legados.
