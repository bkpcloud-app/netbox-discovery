# netbox-discovery 1.11.21

## Legacy MAC owner preflight recovery

### Problema observado ao vivo

Depois do primeiro APPLY parcial, o PLAN reconciliou corretamente:

```text
10.19.1.30 | SW-CORE-AE
DECISION=READY
ACTION=NOOP
MOTIVOS=SERIAL+MAC+IP+NAME
```

O Device já existia no NetBox e a MAC `E8:B5:D0:72:9D:FC` estava vinculada à interface ID `543` do próprio equipamento.

Na tentativa seguinte, já com a 1.11.20, o preflight bloqueou antes da escrita:

```text
SW-CORE-AE: MAC E8:B5:D0:72:9D:FC pertence a dcim.interface ID 543,
esperado interface ainda não existente
```

A mensagem apareceu duas vezes. Nenhuma nova escrita foi iniciada nessa tentativa.

## Causa

O preflight V5 legado:

1. tentava obter a interface esperada exclusivamente pelo IP presente no `spec`;
2. quando o formato do `spec` não permitia essa inferência, retornava `None`;
3. tratava qualquer MAC já atribuída como conflito, mesmo quando a interface pertencia ao próprio Device reconciliado;
4. percorria dois `specs` com a mesma MAC sem deduplicação.

A proteção global da 1.11.20 estava correta. O falso bloqueio vinha da camada legada executada no `PREFLIGHT GLOBAL FINALIZE`.

## Correção

O Importer V5 agora consulta:

```text
dcim/mac-addresses
dcim/interfaces
```

Para cada MAC final:

```text
rematch do registro
→ resolve o Device alvo
→ lê a dcim.interface atribuída à MAC
→ compara interface.device.id com o Device alvo
```

Contrato:

```text
owner real = Device reconciliado
→ PASS

owner real diferente do Device reconciliado
→ BLOQUEADO

owner não resolvido
→ BLOQUEADO

MAC atribuída a VM/outro objeto
→ BLOQUEADO

mesma MAC em vários specs do registro
→ avaliada uma única vez
```

A inferência da interface pelo IP continua disponível apenas como diagnóstico; ela não é mais a autoridade para decidir propriedade.

## Segurança preservada

A versão não:

- transfere MAC entre objetos;
- reassocia interface;
- ignora owner diferente;
- libera MAC de VM;
- reduz o preflight global da 1.11.20;
- habilita scheduler ou APPLY automático.

## Cenário DCM esperado

Após atualizar para 1.11.21:

```text
SW-CORE-AE READY/NOOP
+ interface ID 543 pertence ao mesmo Device
→ PREFLIGHT PASS

13 READY/CREATE restantes
→ seguem para o Importer somente depois de todos os preflights
```

## Regressões

- interface ID 543 pertence ao Device alvo e spec não informa IP utilizável;
- mesma MAC repetida em dois specs sem erro duplicado;
- interface pertencente a outro Device permanece bloqueada;
- novo Device não reutiliza MAC existente;
- MAC em `virtualization.vminterface` permanece bloqueada;
- MAC global duplicada gera um único bloqueio;
- documentação e versões sincronizadas.
