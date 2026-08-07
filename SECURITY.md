# Segurança do repositório

**Versão da política:** 1.11.34

O `netbox-discovery` é distribuído em repositório público. Código e documentação podem ser públicos; dados operacionais e credenciais de clientes não podem.

## Nunca versionar

- configuração real de cliente;
- tokens, communities e senhas;
- credenciais NetBox, VMware, Proxmox, Hyper-V, ONVIF, Zabbix ou iDRAC;
- chaves privadas;
- relatórios, journals, logs e backups reais;
- listas privadas de IPs e redes de clientes.

## Atualização e APPLY

O updater usa o canal `stable`, valida o candidato, cria backup, preserva configuração, executa self-test/check e faz rollback/quarentena em falha.

O updater **não altera `automation.apply`**. Também não pode executar `run --apply` por conta própria nem modificar redes, exclusões, communities e credenciais.

A escrita automática de inventário só ocorre quando a configuração da unidade já contém `automation.apply=true` e o `scheduled-run` é disparado pelo scheduler Network.

## Instalação direta de unidade nova

A instalação direta pode habilitar escrita automática, mas isso é uma decisão explícita durante o `init`:

```text
Habilitar execução automática: SIM
Permitir IMPORT automático: SIM
```

O comando oficial termina com:

```bash
netbox-discovery run --apply
```

Esse modo não remove as proteções de PLAN, identidade, ownership global de MAC, write guard, preflight e auditoria.

## GO-LIVE seguro

O modo controlado continua disponível:

```bash
netbox-discovery go-live
```

Ele executa IMPORT, AUDIT, novo PLAN e validação de convergência antes de habilitar o scheduler e termina com `automation.apply=false`.

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

O Planner e os preflights validam ownership antes da escrita. Nome de interface não é identidade e não pode prevalecer sobre uma MAC global já vinculada ao mesmo Device.

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

## Falha de APPLY

Uma falha depois de `PREFLIGHT: OK` deve ser tratada como possível escrita parcial.

```text
não repetir imediatamente
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

Toda release precisa atualizar a versão exata em README, Manual, Comandos Rápidos, Homologação, Release Notes, Security e nota de patch. O CI não aceita mais apenas a família `1.11.x` como evidência de sincronismo.

O `docs/MANUAL.md` mantém o **Ponto de retomada** do projeto. Não registrar tokens, IPs privados de clientes ou outras credenciais nessa seção.

## Higiene

Artefatos obsoletos não devem permanecer no pacote. Arquivos históricos só ficam quando ainda são usados/importados, exigidos por compatibilidade/migração, executados pelo CI ou necessários para regressão documentada.

`main` e `stable` devem terminar sincronizados após cada promoção. `stable` continua sendo o canal consumido pelos agentes.
