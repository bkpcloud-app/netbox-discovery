# netbox-discovery 1.11.33 — Comandos rápidos

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

O NetBox oficial é:

```text
https://inventory.bkpcloud.app.br
```

Não usar `:8080`.

Esse fluxo instala, configura, valida, habilita o scheduler e executa a primeira descoberta imediatamente. Não é necessário esperar a madrugada.

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

## Primeira coleta sem escrita

```bash
netbox-discovery run
```

## Primeira coleta com escrita

```bash
netbox-discovery run --apply
```

## Analisar o último PLAN

```bash
netbox-discovery plan summary
netbox-discovery plan blocked
netbox-discovery plan review
netbox-discovery plan ready
netbox-discovery plan delegated
```

Todos são somente leitura.

## Fluxo controlado com revisão antes da escrita

Depois da aprovação do PLAN:

```bash
netbox-discovery go-live
```

O `go-live` executa IMPORT, AUDIT, novo PLAN, valida convergência e habilita o scheduler Network com `APPLY=NÃO`.

Resultado esperado:

```text
GO-LIVE: PASS
SCHEDULER NETWORK: ENABLED
APPLY AUTOMÁTICO: NÃO
```

## Identidade para novos Devices

```text
Discovery UID SERIAL ou MGMT-MAC → pode permanecer READY
Discovery UID WEAK               → REVIEW/NOOP
```

## Propriedade global de MAC

```text
MAC sem vínculo                          → permitido
MAC no mesmo Device existente           → reutiliza a interface live
MAC em outro Device/VM/objeto            → BLOCKED/NOOP
nome da interface live diferente        → MAC tem precedência, sem nova interface
mesma MAC repetida no mesmo registro     → preserva a mesma interface
consulta global indisponível             → APPLY bloqueado
```

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
netbox-discovery hypervisor scheduler status
```

Network e Hypervisor possuem schedulers independentes.

## Segurança

```text
run               = sem escrita
run --apply       = pipeline completo com escrita READY + AUDIT
go-live           = escrita READY + AUDIT + convergência + scheduler APPLY=NÃO
import --apply     = estágio de importação manual
WEAK new Device   = REVIEW/NOOP
MAC conflict      = BLOCKED/NOOP
same owner MAC    = reutiliza interface
REVIEW            = não escreve
DELEGATED         = não escreve
BLOCKED           = não escreve
```
