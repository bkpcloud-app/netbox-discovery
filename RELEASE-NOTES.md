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
