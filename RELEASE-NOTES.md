## V1.11.33 — Documentação operacional de instalação limpa

A documentação principal foi sincronizada com o procedimento real de instalação de uma unidade nova.

Comando oficial para instalação do zero, ativação do scheduler Network e primeira descoberta imediata:

```bash
curl -fsSL https://raw.githubusercontent.com/bkpcloud-app/netbox-discovery/stable/install-from-github.sh -o /tmp/netbox-discovery-install.sh && bash /tmp/netbox-discovery-install.sh && netbox-discovery init && netbox-discovery check && netbox-discovery scheduler enable && netbox-discovery run --apply
```

Foram atualizados:

```text
README.md
docs/MANUAL.md
docs/COMANDOS-RAPIDOS.md
docs/NOVA-UNIDADE-DOIS-PASSOS.md
RELEASE-NOTES.md
```

A documentação agora diferencia explicitamente:

```text
Modo direto:
  automation.enabled=true
  automation.apply=true
  primeira coleta imediata com run --apply
  próximas execuções agendadas podem escrever READY

Modo controlado:
  PLAN revisado antes da escrita
  go-live
  scheduler habilitado com APPLY=NÃO
```

O endpoint oficial documentado é `https://inventory.bkpcloud.app.br`, sem `:8080`.

---

## V1.11.32 — Updater sem falso ATUALIZADO por cache

O updater passou a evitar resposta antiga de `stable/VERSION` via cache do GitHub Raw usando cache-bust e headers no-cache.

---

## V1.11.31 — Configurador alinhado ao HTTPS/443

O assistente `netbox-discovery configure/init` deixou de regravar o endpoint legado com `:8080` e passou a usar `https://inventory.bkpcloud.app.br`.

---

## V1.11.30 — VMware replica identity refresh

VMs VMware cujo nome termina exatamente em `_replica`, com nome único no NetBox, podem atualizar a identidade UUID e herdar o contexto autoritativo do vCenter sem relaxar conflitos de outros objetos.

---

## V1.11.29 — Stable REVIEW global preflight

REVIEWs estáveis já conhecidos deixam de bloquear alterações READY seguras no Hypervisor. REVIEW novo/alterado e BLOCKED continuam fail-closed.

---

## V1.11.28 — NetBox HTTPS/443 endpoint lock

O lock central do endpoint foi alinhado para `https://inventory.bkpcloud.app.br`.

---

## V1.11.27 — Migração NetBox HTTPS/443

Configurações legadas com `https://inventory.bkpcloud.app.br:8080` passam por migração para o endpoint oficial sem porta explícita.

---

## V1.11.23 — Native GO-LIVE

Adicionado o comando operacional padrão:

```bash
netbox-discovery go-live
```

O comando executa de forma nativa:

```text
IMPORT --apply
→ AUDIT
→ novo PLAN e summary
→ validação de convergência
→ configuração segura com automation.apply=false
→ habilitação do scheduler Network
→ verificação final de enabled=true e apply=false
→ status
```

A interface pública passa por um wrapper instalado em `/usr/local/bin/netbox-discovery`. Todos os comandos existentes continuam delegados ao core original; somente `go-live` usa o novo orquestrador.

O fluxo falha fechado. Mudanças `READY/CREATE`, `READY/UPDATE_SAFE` ou `READY/REPAIR_SAFE_VM_DUPLICATE` ainda pendentes bloqueiam a habilitação do scheduler. Se o estado final estiver inseguro, o scheduler é desabilitado antes do erro.

---

## V1.11.22 — Runtime MAC interface reuse

Antes de criar ou localizar interface por nome, o Importer resolve a MAC global, valida ownership e reutiliza a interface live quando ela pertence ao mesmo Device.

---

## V1.11.21 — Legacy MAC owner preflight recovery

O preflight legado passou a usar o proprietário real da interface e aceitar recuperação de APPLY parcial quando a MAC já pertence ao mesmo Device reconciliado.

---

## V1.11.20 — Global MAC ownership preflight

O Planner V11 e Importer V12 passaram a validar ownership global de MAC antes da primeira escrita.

---

## V1.11.19 — Final stable identity guard

Novo `READY/CREATE` com `discovery_uid WEAK` passa a `REVIEW/NOOP`, independentemente de role ou classe.

---

## V1.11.18 — Small-site bootstrap write guard

Sites com menos de 50 Devices adiam apenas a regra percentual. Limites absolutos permanecem obrigatórios.

---

## V1.11.17 — Final write guard ordering

O write guard passa a ser calculado uma única vez após todas as políticas finais do Planner.

---

## V1.11.16 — Native PLAN reports and run-scoped status

Foram adicionados relatórios nativos somente leitura:

```text
netbox-discovery plan summary
netbox-discovery plan blocked
netbox-discovery plan review
netbox-discovery plan ready
netbox-discovery plan delegated
netbox-discovery plan all
```

---

## V1.11.15 — Update preflight before every scheduled collection

Network e Hypervisor executam o updater imediatamente antes de cada coleta agendada.

---

## V1.11.14 — Scheduler guarantees auto-update and documentation parity

- timer de update garantido;
- desabilitar coleta não desabilita update;
- documentação principal sincronizada.

---

## V1.11.13 — Discovery V6 entrypoints

- comando direto `discover` alinhado ao Discovery V6;
- `check` atualizado para V6;
- self-test exige o componente V6.

---

## V1.11.12 — Large-CIDR discovery

- prefixos grandes divididos em lotes `/24`;
- paralelismo controlado;
- suporte ao cenário DCM com `/16`.

---

## V1.11.11 — Scheduler migration

- bloco `automation` seguro;
- scheduler inicia desabilitado;
- `apply` permanece falso por padrão.

---

## V1.11.10 — Import and audit idempotency

- Device Type aplicado e verificado;
- aliases corrigidos;
- auditoria idempotente;
- piloto FBA concluído sem FAIL.

---

## V1.11.0–1.11.9 — Identity and safety consolidation

- identidade e proveniência;
- virtualização centralizada;
- Printer-MIB, Windows, industrial e CFTV;
- proteção de nomes;
- write guard, preflight e auditoria final.
