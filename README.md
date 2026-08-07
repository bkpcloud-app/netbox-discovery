# netbox-discovery

Produto BKPCLOUD para descoberta, classificação, reconciliação e inventário seguro de infraestrutura no NetBox.

**Versão atual:** 1.11.34 — PRODUCT V1  
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

Todos os MACs finais do PLAN são verificados contra `dcim/mac-addresses` antes da escrita.

```text
MAC livre ou sem vínculo                  → elegível conforme as demais políticas
MAC no mesmo Device existente            → preservada/reutilizada
MAC em outro Device, VM ou objeto         → BLOCKED/NOOP
MAC duplicada ou owner não resolvido      → BLOCKED/NOOP
```

## Identidade estável obrigatória para novos Devices

Novo `READY/CREATE` com `discovery_uid WEAK` vira `REVIEW/NOOP`.

Identidades normalmente aceitas:

```text
SERIAL:<fabricante>:<serial>
MGMT-MAC:<mac>
```

## Write guard e bootstrap

Sites novos e pequenos usam limites absolutos de segurança; sites estabelecidos usam também guarda percentual. `REVIEW`, `DELEGATED` e `BLOCKED` nunca são escritos.

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
netbox-discovery hypervisor run --compare
netbox-discovery hypervisor scheduler status
```

Network e Hypervisor possuem schedulers independentes. Não existe exclusão automática de VMs/Devices.

## Continuidade e disciplina de release

O arquivo de referência para retomar o projeto é `docs/MANUAL.md`, especialmente a seção **Ponto de retomada**. Ela deve registrar o estado técnico atual, decisões vigentes, o último resultado comprovado e o próximo passo do projeto.

Toda release deve atualizar, no mesmo PR, `VERSION`, `netbox-discovery/VERSION`, README, Manual, Comandos Rápidos, Homologação, Release Notes, Security e a nota `docs/PATCH-<versão>.md`. O CI exige agora a **versão exata**, não apenas a família `1.11.x`.

`stable` é o canal consumido pelos agentes. `main` é a página padrão do GitHub e deve ser sincronizado com `stable` após a promoção, para nunca exibir documentação antiga.

## Higiene do repositório

Arquivos comprovadamente obsoletos e não utilizados não devem permanecer no repositório. Código histórico só permanece quando ainda é importado pelo runtime, exigido por regressão/compatibilidade ou necessário para uma migração suportada. Histórico de mudanças fica em `RELEASE-NOTES.md` e nas notas de patch que ainda são verificadas pelas regressões.

## Segurança

- nenhuma exclusão automática de Device;
- nenhum PATCH automático de nome;
- nome existente no NetBox é preservado;
- identidade `WEAK` nunca cria novo Device;
- MAC vinculada a outro objeto nunca é reassociada automaticamente;
- MAC já pertencente ao mesmo Device reutiliza a interface live;
- `REVIEW`, `DELEGATED` e `BLOCKED` nunca escrevem;
- limites de write guard permanecem ativos.

## Documentação

- `docs/MANUAL.md` — manual operacional completo e ponto de retomada;
- `docs/COMANDOS-RAPIDOS.md` — referência de comandos;
- `docs/NOVA-UNIDADE-DOIS-PASSOS.md` — instalação direta e fluxo controlado;
- `docs/HOMOLOGACAO.md` — estado de homologação;
- `RELEASE-NOTES.md` — histórico consolidado;
- `SECURITY.md` — políticas de segurança;
- `docs/PATCH-1.11.34.md` — documentação desta atualização.
