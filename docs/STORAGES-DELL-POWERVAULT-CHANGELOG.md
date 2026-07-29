# Changelog — Monitoramento Dell PowerVault

## 2026-07-29

### Dell PowerVault ME4024

- validação de coleta HTTPS nas controladoras `10.1.1.52` e `10.1.1.53`;
- criação do template `ZBX-DELL-STG-POWERVAULT-ME-API`;
- inclusão de saúde, inventário, controladoras, portas, SFPs, discos, pools, disk groups, volumes e desempenho;
- correção para não criar `SSD life remaining` em discos HDD;
- correção do parâmetro de senha no item mestre de inventário;
- manutenção de triggers com persistência para reduzir flaps.

### Dell PowerVault MD3200

- validação de conectividade ICMP e TCP 2463 nas controladoras `10.1.1.56` e `10.1.1.57`;
- instalação do Dell MDSM/SMcli no Proxy `SNOC-AGL-DCM`;
- instalação limitada ao componente `SMclient`;
- validação de saúde da storage como `optimal`;
- inventário confirmado com 24 discos, 2 volumes, 2 baterias e 2 canais físicos;
- ajuste de ACL em `/var/opt/SM` para execução pelo usuário `zabbix`;
- correção de retorno SMcli 27 causado por falta de acesso aos arquivos locais;
- criação do coletor `dell_md3200.py`;
- identificação de concorrência e timeout quando saúde, inventário e performance eram executados simultaneamente pelo Zabbix;
- mudança de arquitetura para cache local serializado via systemd;
- criação de `health.json`, `performance.json` e `inventory.json`;
- correção do bug Bash `out: variável não associada`;
- validação final com `available=1`, `return_code=0`, `storage_health=optimal` e `cache_stale=0`.
