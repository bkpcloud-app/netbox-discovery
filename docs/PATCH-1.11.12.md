# netbox-discovery 1.11.12

## Correção

Corrige o discovery Network em redes grandes, especialmente prefixos como `/16`.

O erro observado no site DCM era:

```text
RuntimeError: Falha no nmap discovery:
```

A causa real era o timeout fixo de 900 segundos no discovery primário. A rede `10.19.0.0/16`, somada a três redes `/24`, possui mais de 66 mil endereços candidatos e não concluía dentro do limite antigo.

## Discovery V6

O pipeline padrão agora usa `network_v6.py` e Runner `3.4-product`.

Quando o conjunto possui mais de 4096 endereços candidatos, o produto ativa automaticamente o modo `LARGE-CIDR`:

- consolida redes sobrepostas;
- divide prefixos grandes em lotes de até `/24`;
- executa até quatro lotes em paralelo;
- mostra progresso a cada 16 lotes;
- aplica timeout individual por lote;
- repete somente os lotes que falharam;
- falha com a lista exata dos lotes problemáticos se o retry também falhar;
- inclui portas de infraestrutura, impressão, servidores e OT/industrial no discovery primário;
- evita repetir um connect scan exaustivo e redundante sobre dezenas de milhares de IPs ausentes;
- mantém rescue SNMP escalável e com progresso visível.

## Portas importantes incorporadas

Além das portas já utilizadas, o discovery LARGE-CIDR inclui provas TCP para equipamentos que podem não responder ICMP, incluindo:

```text
102, 502, 902, 9100, 8291, 8006, 34567, 37777, 44818
```

Isso cobre, entre outros, equipamentos industriais, impressoras, virtualização, Mikrotik e CFTV.

## Segurança

- não altera a configuração de redes escolhida pelo usuário;
- não habilita scheduler;
- não habilita APPLY;
- não executa IMPORT automaticamente;
- nenhuma escrita no NetBox ocorre em `netbox-discovery run` sem `--apply`;
- redes pequenas continuam usando o fluxo legado já homologado no FBA.

## Execução recomendada para redes grandes

Como a coleta pode ser longa, execute pelo `systemd`, para que continue mesmo se a sessão SSH cair:

```bash
systemctl start netbox-discovery.service
```

Acompanhe por:

```bash
journalctl -fu netbox-discovery.service
```

O serviço continua em modo somente leitura quando `automation.apply` está `false` e o comando iniciado é o `scheduled-run` padrão.

## Regressões

A regressão `tests/test_network_1_11_12.py` valida:

- divisão de `/16` em lotes `/24`;
- eliminação de sobreposição entre redes;
- preservação do fluxo antigo para redes pequenas;
- acionamento automático do modo LARGE-CIDR;
- mensagem explícita de timeout;
- inclusão de portas OT e SNMP;
- uso efetivo do Discovery V6 pelo Runner;
- sincronização da versão 1.11.12.
