# Índice — Dell PowerVault no Zabbix

Documentação da implantação de monitoramento das storages Dell PowerVault no ambiente BKPCLOUD.

## Documentos

- [Procedimento completo](./STORAGES-DELL-POWERVAULT.md)
- [Comandos rápidos](./STORAGES-DELL-POWERVAULT-COMANDOS-RAPIDOS.md)
- [Changelog da implantação](./STORAGES-DELL-POWERVAULT-CHANGELOG.md)

## Equipamentos documentados

- Dell PowerVault ME4024;
- Dell PowerVault MD3200.

## Padrão operacional

- Zabbix Proxy: `SNOC-AGL-DCM`;
- coleta da linha ME por API HTTPS;
- coleta da MD3200 por MDSM/SMcli;
- cache local serializado via systemd para evitar timeout;
- sem credenciais reais armazenadas no GitHub.
