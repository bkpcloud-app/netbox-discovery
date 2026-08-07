# netbox-discovery

Produto BKPCLOUD para descoberta, classificação, reconciliação e inventário seguro de infraestrutura no NetBox.

**Versão atual:** 1.11.33 — PRODUCT V1  
**Distribuição:** `bkpcloud-app/netbox-discovery`  
**Canal de produção:** `stable`

## Instalação do zero — unidade nova

Para uma unidade nova, com ativação imediata e primeira descoberta no mesmo procedimento, executar como `root`:

```bash
curl -fsSL https://raw.githubusercontent.com/bkpcloud-app/netbox-discovery/stable/install-from-github.sh -o /tmp/netbox-discovery-install.sh && bash /tmp/netbox-discovery-install.sh && netbox-discovery init && netbox-discovery check && netbox-discovery scheduler enable && netbox-discovery run --apply
```

Durante `netbox-discovery init`, informar Tenant, Tenant Group quando aplicável, Site, token, redes, exclusões e communities.

Para a unidade trabalhar automaticamente depois da instalação:

```text
Habilitar execução automática: SIM
Agenda systemd OnCalendar: daily
Permitir IMPORT automático: SIM
Salvar configuração: SIM
Testar conexão com o NetBox: SIM
```

Endpoint oficial:

```text
https://inventory.bkpcloud.app.br
```

Não usar `:8080`.

O comando instala o produto, executa o assistente, valida a configuração, habilita o scheduler Network e executa imediatamente o pipeline com `--apply`. A primeira coleta não depende da madrugada.

Para ambientes que exigem revisão humana antes da primeira escrita, usar `docs/NOVA-UNIDADE-DOIS-PASSOS.md`.

## Pipeline atual

```text
DISCOVER V6 / 4.6-product
→ CLASSIFY V8 / 5.6-product
→ RECONCILE V5 / 3.3-product
→ PLAN V11 / 5.3-product
→ IMPORT V12 / 6.1-product
→ AUDIT V11 / 6.9-product
```

`netbox-discovery run` é read-only. `netbox-discovery run --apply` executa o pipeline completo com escrita dos registros `READY` e auditoria, protegido por PLAN, write guard, preflight, identidade e auditoria.

## Modos operacionais

### Ativação direta

Usada quando a unidade já pode operar com escrita automática:

```text
init com automation.enabled=true e automation.apply=true
→ scheduler enable
→ run --apply
→ próximas execuções agendadas podem aplicar READY automaticamente
```

### GO-LIVE controlado

Para ambientes em que o PLAN precisa ser revisado antes da primeira escrita:

```bash
netbox-discovery go-live
```

Ele executa:

```text
IMPORT --apply
→ AUDIT
→ novo PLAN
→ validação de convergência
→ força automation.apply=false
→ habilita o scheduler Network
→ valida o estado final
```

Nesse modo o resultado aprovado termina com scheduler habilitado e `APPLY=NÃO`.

## Preflight global de MAC

A 1.11.20 passou a verificar todos os MACs finais do PLAN contra a tabela global `dcim/mac-addresses` antes da primeira escrita.

```text
MAC livre ou sem vínculo
→ elegível conforme as demais políticas

MAC já vinculada à interface do mesmo Device existente
→ preservada

MAC vinculada a outro Device, VM ou objeto
→ BLOCKED/NOOP no PLAN
→ bloqueada novamente pelo preflight do IMPORT
```

A 1.11.21 corrigiu o preflight legado para usar o proprietário real da interface e não bloquear um `READY/NOOP` já reconciliado.

A 1.11.22 corrige também o runtime final. Antes de criar ou localizar interface por nome, o Importer resolve a MAC global:

```text
MAC já vinculada à interface do mesmo Device
→ reutiliza a interface existente
→ não cria interface duplicada
→ ensure_mac preserva o vínculo

MAC vinculada a outro Device, VM ou objeto
→ bloqueia antes de qualquer criação

MAC ausente ou sem vínculo
→ segue o fluxo normal de interface
```

## Identidade estável obrigatória para novos Devices

Novo `READY/CREATE` com `discovery_uid WEAK` vira `REVIEW/NOOP`.

Novos Devices precisam chegar ao PLAN com identidade estável, normalmente:

```text
SERIAL:<fabricante>:<serial>
MGMT-MAC:<mac>
```

## Write guard final e bootstrap de sites pequenos

O write guard é calculado depois das políticas finais do Planner.

Sites com menos de 50 Devices usam:

```text
SMALL_SITE_BOOTSTRAP_ABSOLUTE_ONLY
```

Os limites absolutos continuam obrigatórios; apenas o percentual fica adiado até a base mínima.

## Relatório nativo do PLAN

```bash
netbox-discovery plan summary
netbox-discovery plan blocked
netbox-discovery plan review
netbox-discovery plan ready
netbox-discovery plan delegated
```

Todos são somente leitura.

## Instalação e atualização

```bash
netbox-discovery update run
netbox-discovery version
netbox-discovery check
netbox-discovery status
```

## Auto-update e scheduler Network

```bash
netbox-discovery scheduler enable
netbox-discovery scheduler disable
netbox-discovery scheduler status
```

```text
automation.apply=false → execução automática sem escrita
automation.apply=true  → execução automática com IMPORT/AUDIT dos READY
```

O serviço agendado executa o updater `stable` antes da coleta.

## Hypervisor

```bash
netbox-discovery hypervisor check
netbox-discovery hypervisor run
netbox-discovery hypervisor run --apply
netbox-discovery hypervisor scheduler status
```

Network e Hypervisor possuem schedulers independentes.

## Segurança

- nenhuma exclusão automática de Device;
- nenhum PATCH automático de nome;
- nome existente no NetBox é preservado;
- identidade `WEAK` nunca cria novo Device;
- MAC vinculada a outro objeto nunca é reassociada automaticamente;
- MAC já pertencente ao mesmo Device reutiliza a interface live;
- interface não é criada antes de resolver ownership de MAC;
- `REVIEW`, `DELEGATED` e `BLOCKED` nunca escrevem;
- limites absolutos permanecem ativos durante bootstrap.

## Documentação

- `docs/MANUAL.md` — manual operacional completo;
- `docs/COMANDOS-RAPIDOS.md` — referência de comandos;
- `docs/NOVA-UNIDADE-DOIS-PASSOS.md` — instalação direta e fluxo controlado;
- `docs/HOMOLOGACAO.md` — homologação;
- `RELEASE-NOTES.md` — histórico de versões;
- `SECURITY.md` — políticas de segurança;
- `docs/PATCH-1.11.33.md` — documentação desta atualização.
