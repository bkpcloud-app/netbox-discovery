# netbox-discovery

Produto BKPCLOUD para descoberta, classificação, reconciliação e inventário seguro de infraestrutura no NetBox.

**Versão atual:** 1.11.16 — PRODUCT V1  
**Distribuição:** `bkpcloud-app/netbox-discovery`  
**Canal de produção:** `stable`

## Pipeline atual

```text
DISCOVER V6 / 4.6-product
→ CLASSIFY V8 / 5.6-product
→ RECONCILE V5 / 3.3-product
→ PLAN V11 / 5.3-product
→ IMPORT V12 / 6.1-product
→ AUDIT V11 / 6.9-product
```

`netbox-discovery run` é read-only. Escrita no NetBox só ocorre com `netbox-discovery run --apply` e permanece protegida por PLAN, write guard, preflight, identidade e auditoria.

## Relatório nativo do PLAN

A 1.11.16 elimina comandos Python improvisados para analisar relatórios. O último PLAN do site configurado pode ser consultado diretamente:

```bash
netbox-discovery plan summary
netbox-discovery plan blocked
netbox-discovery plan review
netbox-discovery plan ready
netbox-discovery plan delegated
```

Esses comandos são somente leitura e mostram Run ID, status, escrita no NetBox, decisões, ações, motivos, IP, nome e role. `--json` fornece saída estruturada.

O `status` também deixa de misturar IMPORT/AUDIT históricos com um dry-run atual. Quando o último RUN não solicitou APPLY, informa explicitamente que IMPORT e AUDIT não foram executados naquele RUN.

## Instalação e atualização

```bash
netbox-discovery update run
netbox-discovery version
netbox-discovery check
netbox-discovery status
```

O updater:

- consulta o canal `stable`;
- valida a versão remota;
- executa self-test do pacote candidato;
- cria backup da instalação atual;
- instala preservando configuração e credenciais;
- testa novamente;
- executa rollback em caso de falha;
- mantém versões com falha em quarentena.

## Auto-update

O timer `netbox-discovery-update.timer` fica habilitado por padrão e verifica atualizações diariamente com atraso aleatório de até 30 minutos.

Cada execução automática Network ou Hypervisor segue:

```text
UPDATE PREFLIGHT
→ instalar atualização validada, quando existir
→ validar instalação
→ executar coleta automática
```

Se o GitHub estiver temporariamente indisponível, o erro de update é registrado e a coleta continua usando a versão instalada. O preflight automático não modifica `automation.apply` e não autoriza escrita no NetBox.

## Schedulers

```bash
netbox-discovery scheduler enable
netbox-discovery scheduler disable
netbox-discovery scheduler status
```

```bash
netbox-discovery hypervisor scheduler enable
netbox-discovery hypervisor scheduler disable
netbox-discovery hypervisor scheduler status
```

Habilitar um scheduler também garante que o timer de update esteja ativo. Desabilitar a coleta não desabilita o auto-update.

## Redes grandes

O Discovery V6 divide prefixos grandes, como `/16`, em lotes `/24`, elimina sobreposição duplicada, aplica paralelismo controlado e apresenta erro explícito por lote. A execução automática e manual pode ser acompanhada pelo `journalctl` sem depender da sessão SSH.

## Segurança

- nenhuma exclusão automática de Device;
- nenhum PATCH automático de nome;
- nome existente no NetBox é preservado;
- VM confirmada permanece delegada ao inventário de virtualização;
- serial conflitante não é gravado;
- `REVIEW`, `DELEGATED` e `BLOCKED` nunca escrevem;
- `READY/CREATE` e `READY/UPDATE_SAFE` escrevem somente com `--apply`;
- atualização automática não altera a política de APPLY;
- comandos de relatório do PLAN são somente leitura.

## Documentação

- `docs/MANUAL.md`: operação completa;
- `docs/COMANDOS-RAPIDOS.md`: comandos de campo;
- `docs/HOMOLOGACAO.md`: estado CI/LIVE;
- `RELEASE-NOTES.md`: histórico de releases;
- `SECURITY.md`: política de segurança;
- `docs/PATCH-1.11.16.md`: detalhes desta versão.

A release é bloqueada no CI quando os documentos obrigatórios não carregam a versão exata do `VERSION`.
