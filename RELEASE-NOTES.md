# netbox-discovery 1.5.0 — PRODUCT V1

Consolida Evidence V4 + CLASSIFY + RECONCILE + PLAN + IMPORT 4.1 + AUDIT 5.1 e corrige a última inconsistência de identidade/contagem encontrada na homologação FBA.

Esta release substitui o fluxo de instalação por stages.

Para upgrade em um proxy já configurado, `install.sh` preserva `config.yml`, `config/sites`, relatórios e histórico. O scheduler é instalado, porém fica desabilitado até ação explícita.
