# netbox-discovery 1.11.20

## Global MAC ownership preflight

### Problema observado ao vivo

No primeiro APPLY do DCM, executado com a 1.11.19, o PLAN continha 14 novos equipamentos estáveis e o write guard estava em `PASS`.

O Importer iniciou o primeiro READY:

```text
SW-CORE-AE
MAC E8:B5:D0:72:9D:FC
```

E terminou com:

```text
MAC E8:B5:D0:72:9D:FC já pertence a dcim.interface ID 543
```

A falha ocorreu depois de:

```text
PREFLIGHT GLOBAL FINALIZE: OK
PREFLIGHT: OK
```

Portanto, o ciclo deve ser tratado como possível escrita parcial do primeiro equipamento.

### Causa

A proteção global de IP já era executada antes da primeira escrita. A proteção de MAC existia somente:

- durante a correspondência do Planner, quando o MAC havia chegado ao asset reconciliado;
- dentro de `ensure_mac`, depois da criação ou correspondência do Device e da interface.

Um management MAC presente apenas na interface final do PLAN podia escapar do primeiro caso e ser detectado tarde no segundo.

## Correção no Planner V11

A camada final verifica toda MAC presente em `row.interfaces` contra `state.macs` e `state.interfaces`.

```text
MAC sem objeto ou sem atribuição
→ segue normalmente

MAC na interface do mesmo existing_device_id
→ preservada

MAC em interface de outro Device
→ BLOCKED/NOOP

MAC em VM ou outro objeto
→ BLOCKED/NOOP

MAC duplicada globalmente
→ BLOCKED/NOOP

interface sem owner resolvido
→ BLOCKED/NOOP
```

O conflito é registrado em:

```text
mac_ownership_conflicts
identity_policy = GLOBAL_MAC_OWNERSHIP_CONFLICT
```

Interfaces, intenções de IP, diffs e reparos são removidos do registro bloqueado antes do write guard.

## Correção no Importer V12

Antes do primeiro POST/PATCH, o Importer consulta:

```text
dcim/mac-addresses
dcim/interfaces
```

E valida todos os MACs dos registros READY.

O preflight é aplicado aos dois objetos de módulo mantidos pela cadeia legada:

```text
modules.importers.importer
importer
```

Isso garante que a função realmente usada pelo loop principal receba a mesma proteção.

Se a consulta global falhar:

```text
GLOBAL_MAC_PREFLIGHT_UNAVAILABLE
→ APPLY bloqueado
→ nenhuma nova escrita iniciada
```

## Cenário DCM esperado

Após atualizar e recalcular o PLAN contra o estado atual:

```text
SW-CORE-AE
→ BLOCKED/NOOP
→ motivo referencia MAC, Device owner e interface ID 543
```

Os demais candidatos sem conflito continuam sujeitos às políticas normais. No cenário de regressão:

```text
1 conflito parcial isolado
13 novos candidatos seguros
WRITE GUARD: PASS
eligible_total: 13
```

A versão não transfere a MAC, não remove o Device owner e não apaga automaticamente um possível Device parcial criado no APPLY anterior.

## Operação após falha parcial

```text
1. Não repetir APPLY imediatamente.
2. Manter scheduler desabilitado.
3. Atualizar para 1.11.20.
4. Executar netbox-discovery plan.
5. Revisar plan summary e plan blocked.
6. Somente então decidir sobre nova tentativa de escrita.
```

## Regressões

- novo Device com MAC pertencente a outro Device;
- Device existente com MAC na própria interface;
- MAC vinculada a VM/outro objeto;
- MAC global duplicada;
- preflight do Importer antes da escrita;
- fail-closed quando a consulta global não está disponível;
- cenário DCM com interface ID 543 e 13 candidatos restantes;
- ordem MAC guard antes do write guard.
