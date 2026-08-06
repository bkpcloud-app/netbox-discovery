# Segurança do repositório

**Versão da política:** 1.11.23

O `netbox-discovery` é distribuído em repositório público. Código e documentação podem ser públicos; dados operacionais e credenciais de clientes não podem.

## Nunca versionar

- configuração real de cliente;
- tokens, communities e senhas;
- credenciais NetBox, VMware, Proxmox, Hyper-V, ONVIF ou iDRAC;
- chaves privadas;
- relatórios, journals, logs e backups reais;
- listas privadas de IPs e redes de clientes.

## Atualização e APPLY

O updater usa o canal `stable`, valida o candidato, cria backup, preserva configuração, executa self-test/check e faz rollback/quarentena em falha.

O updater não pode alterar `automation.apply`, executar `run --apply` ou modificar redes, exclusões, communities e credenciais.

## GO-LIVE seguro

A 1.11.23 adiciona o comando padrão:

```bash
netbox-discovery go-live
```

Ele executa IMPORT, AUDIT, novo PLAN e validação de convergência antes de habilitar o scheduler.

Antes da habilitação final, preserva os dados operacionais existentes e força:

```text
automation.enabled=false
automation.apply=false
```

Depois habilita o scheduler e verifica obrigatoriamente:

```text
automation.enabled=true
automation.apply=false
```

Se a verificação falhar, o próprio fluxo desabilita o scheduler e encerra com erro.

O GO-LIVE nunca escreve registros `REVIEW`, `DELEGATED` ou `BLOCKED`.

## Propriedade global de MAC

MACs pertencem à tabela global `dcim/mac-addresses`. O produto não pode reassociar automaticamente uma MAC já vinculada.

```text
MAC sem vínculo                          → segue as demais políticas
MAC na interface do mesmo Device         → preservada
MAC em outro Device                      → BLOCKED/NOOP
MAC em VM ou outro tipo de objeto        → BLOCKED/NOOP
MAC duplicada globalmente                → BLOCKED/NOOP
owner da interface não resolvido         → BLOCKED/NOOP
```

O Planner e os preflights validam ownership antes da escrita.

### Runtime de interface

A 1.11.22 exige que o Importer resolva a MAC antes de procurar ou criar uma interface por nome.

```text
MAC → dcim.interface → interface.device.id
```

Se o owner for o mesmo Device reconciliado:

```text
reutilizar a interface live
não criar outra interface
preservar o vínculo da MAC
```

Se o owner for diferente, não resolvido ou de outro tipo:

```text
bloquear antes de qualquer POST/PATCH de interface
```

Nome de interface não é identidade e não pode prevalecer sobre uma MAC global já vinculada ao mesmo Device.

## Identidade estável para novos Devices

```text
existing_device_id ausente
+ READY/CREATE
+ discovery_uid WEAK
→ REVIEW/NOOP
```

## Write guard final

Entram no cálculo:

```text
READY/CREATE
READY/UPDATE_SAFE
READY/REPAIR_SAFE_VM_DUPLICATE
```

Não entram:

```text
READY/NOOP
REVIEW
DELEGATED
BLOCKED
```

## Bootstrap de site pequeno

Bases com menos de 50 Devices adiam somente a regra percentual. Limites absolutos permanecem obrigatórios.

## Falha de APPLY

Uma falha depois de `PREFLIGHT: OK` deve ser tratada como possível escrita parcial, inclusive possível criação de interface.

```text
não repetir imediatamente
manter scheduler desabilitado
recalcular PLAN
revisar Device, interfaces, MACs e IPs do primeiro READY
```

## Autoridade dos dados

```text
Nome existente no NetBox → preservado
PATCH automático de name → proibido
Serial conflitante       → não gravado
MAC de outro objeto      → não transferida
MAC do mesmo Device      → interface live reutilizada
VM confirmada            → delegada
Device manual            → protegido
```

## Lock global

```text
/var/lock/netbox-discovery-global.lock
```

## Documentação obrigatória

O CI exige versão sincronizada em README, Manual, Comandos Rápidos, Homologação, Release Notes, Security e nota de patch.
