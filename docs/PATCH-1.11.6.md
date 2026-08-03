# netbox-discovery 1.11.6

## Correções

- impede que o hostname de impressoras Samsung, como `SEC30CDA7FFE27C`, seja usado como modelo e gere Device Type falso;
- corrige a validação de serial para não transformar seriais alfanuméricos em MAC após remover letras não hexadecimais;
- aceita o serial Brother `U64189M8N960565` coletado pelo Printer-MIB;
- elimina rejeições duplicadas do mesmo serial no diagnóstico;
- mantém a separação Windows Server/Workstation, mas envia para REVIEW qualquer novo Windows sem serial ou MAC estável;
- preserva atualizações seguras de equipamentos existentes e novos Windows com identidade física forte.

## Segurança operacional

A patch não habilita schedulers e não altera a configuração existente. O comando `netbox-discovery inventory` permanece em dry-run e não escreve no NetBox.

## Validação

A regressão cobre os dados reais encontrados no FBA: Samsung `SEC30CDA7FFE27C`, Brother `U64189M8N960565` e Windows `SRV-RXBA01` identificado somente por SMB com UID fraco.
