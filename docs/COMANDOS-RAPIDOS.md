# netbox-discovery 1.11.34 — Comandos rápidos

## Instalação do zero — unidade nova com ativação imediata

Executar como `root`:

```bash
curl -fsSL https://raw.githubusercontent.com/bkpcloud-app/netbox-discovery/stable/install-from-github.sh -o /tmp/netbox-discovery-install.sh && bash /tmp/netbox-discovery-install.sh && netbox-discovery init && netbox-discovery check && netbox-discovery scheduler enable && netbox-discovery run --apply
```

No `init`, para uma unidade que deve trabalhar automaticamente:

```text
Habilitar execução automática: SIM
Agenda: daily
Permitir IMPORT automático: SIM
Salvar: SIM
Testar NetBox: SIM
```

NetBox oficial:

```text
https://inventory.bkpcloud.app.br
```

Não usar `:8080`.

Esse fluxo instala, configura, valida, habilita o scheduler e executa a primeira descoberta imediatamente. Não precisa `go-live` depois quando o `run --apply` termina corretamente.

## Validar instalação

```bash
netbox-discovery version
netbox-discovery check
netbox-discovery status
netbox-discovery scheduler status
```

## Atualizar e validar

```bash
netbox-discovery update run
netbox-discovery version
netbox-discovery check
netbox-discovery status
```

## Coleta Network

```bash
netbox-discovery run          # dry-run
netbox-discovery run --apply  # pipeline completo + escrita READY + AUDIT
```

## Analisar o último PLAN

```bash
netbox-discovery plan summary
netbox-discovery plan blocked
netbox-discovery plan review
netbox-discovery plan ready
netbox-discovery plan delegated
```

Todos os comandos de relatório são somente leitura.

## Fluxo controlado

Depois da aprovação do PLAN:

```bash
netbox-discovery go-live
```

O `go-live` executa IMPORT, AUDIT, novo PLAN, valida convergência e habilita o scheduler Network com `APPLY=NÃO`.

## Scheduler Network

```bash
netbox-discovery scheduler enable
netbox-discovery scheduler disable
netbox-discovery scheduler status
```

```text
automation.apply=false → execução automática sem escrita
automation.apply=true  → execução automática com IMPORT/AUDIT dos READY
```

## Hypervisor

```bash
netbox-discovery hypervisor check
netbox-discovery hypervisor run
netbox-discovery hypervisor run --apply
netbox-discovery hypervisor run --compare
netbox-discovery hypervisor scheduler status
```

Network e Hypervisor possuem schedulers independentes.

## Segurança

```text
WEAK new Device   = REVIEW/NOOP
MAC conflict      = BLOCKED/NOOP
same owner MAC    = reutiliza interface
REVIEW            = não escreve
DELEGATED         = não escreve
BLOCKED           = não escreve
DELETE automático = não existe
```

## Retomar o projeto

Para continuar o trabalho em uma conversa futura, ler primeiro `docs/MANUAL.md`, seção **Ponto de retomada**. O próximo eixo funcional registrado é **NetBox → Zabbix**.
