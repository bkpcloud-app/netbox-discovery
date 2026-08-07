# netbox-discovery 1.11.33

## Documentação de instalação do zero sincronizada

Esta versão não altera a lógica de descoberta. Ela corrige a documentação operacional para refletir o fluxo real usado em produção para uma unidade nova.

Comando oficial documentado:

```bash
curl -fsSL https://raw.githubusercontent.com/bkpcloud-app/netbox-discovery/stable/install-from-github.sh -o /tmp/netbox-discovery-install.sh && bash /tmp/netbox-discovery-install.sh && netbox-discovery init && netbox-discovery check && netbox-discovery scheduler enable && netbox-discovery run --apply
```

O fluxo documentado deixa explícito que, durante o `init`, uma unidade destinada a operar com escrita automática deve usar:

```text
automation.enabled=true
automation.apply=true
schedule=daily, salvo exceção
```

Também fica documentado que a primeira coleta é executada imediatamente por `netbox-discovery run --apply`; não é necessário aguardar a execução agendada.

O endpoint oficial é:

```text
https://inventory.bkpcloud.app.br
```

Sem `:8080`.

Arquivos sincronizados:

- `README.md`
- `docs/MANUAL.md`
- `docs/COMANDOS-RAPIDOS.md`
- `docs/NOVA-UNIDADE-DOIS-PASSOS.md`
- `RELEASE-NOTES.md`

A CI inclui uma regressão de documentação para impedir que o comando oficial de instalação ou o endpoint 443 desapareçam dessas referências principais.
