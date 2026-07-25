## V1.5.2 — Correção do instalador e sincronização de versão

Correções identificadas durante a homologação de upgrade em proxy:

- sincroniza `VERSION` da raiz e `netbox-discovery/VERSION`;
- corrige o loop do `install.sh`: `config.ymbin` passa a ser `config.yml bin`;
- o código novo em `bin`, `lib` e `modules` volta a ser instalado corretamente;
- corrige a detecção de `/opt/netbox-discovery/config.yml` no `bootstrap.sh`;
- mantém a configuração operacional existente durante upgrade;
- preserva a correção de DNS reverso da V1.5.1.

## V1.5.1 — Correção de DNS reverso

Homologação em um proxy novo identificou uma dependência de DNS reverso
não tratada pelo produto.

Correções:

- `dig` passa a ser instalado automaticamente pelo bootstrap;
- RHEL/CentOS utiliza `bind-utils`;
- Debian/Ubuntu utiliza `dnsutils`;
- reverse DNS passa a ser enriquecimento não fatal;
- ausência de PTR, timeout ou falha de resolução não interrompe `DISCOVER`;
- upgrades preservam a configuração existente.

Erro que originou a correção:

```text
FileNotFoundError: [Errno 2] No such file or directory: 'dig'
```

# netbox-discovery 1.5.0 — PRODUCT V1

Consolida Evidence V4 + CLASSIFY + RECONCILE + PLAN + IMPORT 4.1 + AUDIT 5.1 e corrige a última inconsistência de identidade/contagem encontrada na homologação FBA.

Esta release substitui o fluxo de instalação por stages.

## Distribuição oficial

A versão 1.5.0 passa a ser distribuída pelo repositório público:

```text
bkpcloud-app/netbox-discovery
```

Foi validada instalação real em Proxy zerado, onde `git`, Python, Nmap e utilitários SNMP não estavam previamente disponíveis.

O fluxo oficial agora:

```text
GitHub público
→ install-from-github.sh
→ instala Git quando necessário
→ clone HTTPS
→ bootstrap
→ dependências
→ produto
→ init
```

O `bootstrap.sh` também foi ajustado para não apresentar `CONFIG: ERRO` como se fosse falha em uma instalação nova. Antes do `init`, a ausência de `config.yml` é comportamento esperado.

Para upgrade em um Proxy já configurado, o instalador preserva a configuração operacional existente. O scheduler é instalado, porém fica desabilitado até ação explícita.
