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
