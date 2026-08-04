# netbox-discovery 1.11.8

## Correção pós-APPLY do FBA

Esta versão corrige as inconsistências encontradas na auditoria do APPLY de 4 de agosto de 2026 e, principalmente, aumenta o número da versão para garantir que o atualizador substitua integralmente os módulos instalados. Correções anteriores publicadas ainda sob `1.11.7` não eram reinstaladas em servidores que já exibiam esse mesmo número de versão.

## Planner V10 — 5.2-product

- usa `planner_v10.py` no pipeline oficial;
- reconhece novamente Devices criados com nome de colisão segura, como `SW-BA17-LB43JZ` e `SW-BA17-KPC2C1`, por serial e IP;
- valida nome com sufixo, Device Type, role, plataforma e ownership antes de converter o registro para `READY/NOOP`;
- preserva bloqueio quando qualquer evidência divergir;
- considera `WINDOWS_WORKSTATION` e `WORKSTATION-WINDOWS` aliases equivalentes em Devices existentes, sem gerar escrita desnecessária;
- novos Windows continuam usando os nomes canônicos `SERVER-WINDOWS` e `WORKSTATION-WINDOWS`;
- grava identidade estável de idempotência sem depender do nome exibido.

## Importer V11 — 6.0-product

- aplica explicitamente `device_type:SET` em Device existente criado pelo produto;
- cria ou reutiliza Manufacturer e Device Type exatos antes do PATCH;
- exige `READY/UPDATE_SAFE`, confiança HIGH, política de upgrade genérico e ownership do `netbox-discovery`;
- bloqueia Device manual, destino genérico, múltiplos diffs e divergência entre PLAN e payload;
- não escreve quando o Device Type já está correto;
- continua proibindo alteração automática de nome existente.

## Auditor V10 — 6.8-product

- troca a chave antiga `asset_id + desired_name + primary_ip` por correspondência estável sem o nome;
- tenta, em ordem segura, `asset_id + primary_ip`, serial único, asset ID único e IP primário único;
- elimina falsos `IDEMPOTENCY_ASSET_MISSING` causados pela preservação de nome em VMware e impressoras;
- continua falhando quando existe escrita real pendente, como Device Type não aplicado;
- trata os aliases Windows legados como equivalentes na auditoria direta;
- usa obrigatoriamente o Planner V10 para o preview de idempotência.

## Runner e self-test

O runner agora registra e executa explicitamente:

```text
Planner:  planner_v10.py
Importer: importer_v11.py
Auditor:  auditor_v10.py
```

O self-test executa os três entrypoints diretamente, sem `PYTHONPATH`, e valida as versões efetivas dos componentes. Assim, um wrapper antigo ou uma versão apenas nominal passa a bloquear a atualização.

## Casos reais cobertos

- VMware `VM-BA02`, `VM-iBA01` e `VM-iBA02` com nome preservado;
- Kyocera `ECOSYS-10-2-2-88` com nome diferente do observado;
- switches `SW-BA17-LB43JZ` e `SW-BA17-KPC2C1` após criação por colisão segura;
- nove impressoras com atualização exata de Device Type;
- `SRV-RXBA01` com alias legado de role Windows;
- manutenção do bloqueio quando serial, IP, tipo, role ou plataforma não conferem.

## Operação segura

Após a publicação no canal `stable`:

```bash
netbox-discovery update run
```

Depois execute somente o inventário em dry-run:

```bash
netbox-discovery inventory
```

Não usar `--apply` até revisar o novo PLAN. O esperado no FBA é ausência dos falsos bloqueios e apenas as atualizações reais de Device Type ainda pendentes.
