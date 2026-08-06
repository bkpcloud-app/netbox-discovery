# netbox-discovery 1.11.22

## Runtime MAC interface reuse

### Falha observada no DCM

Na 1.11.21, o PLAN e os preflights estavam corretos:

```text
SW-CORE-AE: READY/NOOP
PREFLIGHT GLOBAL FINALIZE: OK
PREFLIGHT: OK
```

Mesmo assim, o runtime terminou com:

```text
MAC E8:B5:D0:72:9D:FC já pertence a dcim.interface ID 543
```

### Causa

O Importer V2 executava a ordem:

```text
procurar interface pelo nome do spec
→ criar ou preservar essa interface
→ validar/garantir a MAC
```

A interface live `543` já possuía a MAC e pertencia ao próprio `SW-CORE-AE`, mas seu nome podia divergir do nome atual do `spec`. Assim, a busca por nome não encontrava a interface correta e o runtime podia criar outra interface antes de detectar o vínculo global da MAC.

### Correção

A 1.11.22 executa:

```text
normalizar MAC
→ consultar dcim/mac-addresses
→ resolver assigned_object_id
→ buscar dcim.interface
→ validar interface.device.id
```

Se o owner for o mesmo Device:

```text
retornar a interface live
registrar PRESERVED_BY_MAC
não executar criação por nome
ensure_mac preservar o objeto existente
```

Se o owner for diferente, não resolvido ou de outro tipo, o runtime bloqueia antes da criação.

Se a MAC não existir ou estiver sem atribuição, o fluxo normal de interface continua.

### Cenário DCM

```text
Device reconciliado: SW-CORE-AE
existing_device_id: 900 no teste de regressão
MAC: E8:B5:D0:72:9D:FC
interface live: ID 543
nome live: MGMT-10.19.1.30
nome do spec: MGMT
resultado esperado: reutilizar interface 543
POST de interface: zero
```

### Possível escrita parcial da tentativa 1.11.21

Como a falha ocorreu depois de `PREFLIGHT: OK` e dentro de `ensure_mac`, a tentativa deve ser tratada como possível criação de uma interface adicional vazia no `SW-CORE-AE`. A versão não exclui automaticamente interfaces existentes.

### Regressões

- mesmo Device, mesma MAC, nome de interface diferente;
- mesma MAC repetida em dois specs;
- owner em outro Device;
- owner em `virtualization.vminterface`;
- MAC sem atribuição;
- ordem de resolução por MAC antes de `ORIG_ENSURE_INTERFACE`;
- ausência de POST de interface no cenário parcial.
