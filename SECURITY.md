# Segurança do repositório

O `netbox-discovery` é distribuído em repositório público.

O código e a documentação podem ser públicos; **dados operacionais de clientes não podem**.

Nunca faça commit de:

- `/opt/netbox-discovery/config.yml` real;
- token do NetBox;
- community SNMP real;
- senha ou segredo;
- chave SSH privada;
- chave `.pem`;
- `.env` com credenciais;
- relatórios de discovery/import/audit de clientes;
- logs de clientes;
- backups de configuração de clientes.

O `.gitignore` deve permanecer alinhado com essa política.

## Comportamento seguro do produto

- `netbox-discovery run` é read-only em relação ao NetBox.
- Escrita manual exige `--apply`.
- `REVIEW` não é importado automaticamente.
- `BLOCKED` nunca é importado automaticamente.
- `AUDIT` é somente leitura.
- O instalador não habilita scheduler automaticamente.

## V1.8.0 — Hypervisor e endpoint

- o endpoint NetBox do produto é fixo em `https://inventory.bkpcloud.app.br:8080`;
- uma URL diferente no `config.yml` é recusada;
- `/etc/netbox-discovery/hypervisors.json` contém credenciais e deve permanecer `0600`, root-only;
- relatórios mascaram o campo de segredo das sources;
- dependências Python de VMware/Hyper-V ficam isoladas em `/opt/netbox-discovery/vendor`;
- `hypervisor run` é read-only; escrita exige `--apply`;
- o pipeline Hypervisor não executa exclusão automática;
- nunca versionar `hypervisors.json` nem cópias das credenciais.
