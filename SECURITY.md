# Segurança do repositório

**Versão da política:** 1.11.19

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

## Identidade estável para novos Devices

Nenhum novo Device pode permanecer `READY/CREATE` quando sua identidade final é fraca.

```text
existing_device_id ausente
+ READY/CREATE
+ discovery_uid WEAK
→ REVIEW/NOOP
```

A regra é aplicada na camada final do Planner, independentemente de role ou `asset_class`, antes do write guard.

Ao rebaixar o candidato, o Planner deve:

- remover interfaces;
- remover intenções de IP;
- remover diffs e reparos;
- registrar `NEW_DEVICE_REQUIRES_STABLE_IDENTITY`;
- impedir que o candidato entre em `eligible_total`.

Identidades estáveis esperadas para novos Devices incluem serial validado ou management MAC. Nomes DNS, certificados TLS, serviços, fingerprints genéricos e hashes `WEAK` não bastam para criação automática.

Devices existentes não são rebaixados por essa regra; continuam protegidos pela reconciliação, autoridade dos dados existentes e políticas de atualização segura.

## Write guard final

O guard avalia apenas mudanças efetivas do PLAN final:

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
BLOCKED por identidade ou política
```

## Bootstrap de site pequeno

Bases com menos de 50 Devices usam:

```text
SMALL_SITE_BOOTSTRAP_ABSOLUTE_ONLY
```

A política adia somente a regra percentual. Permanecem obrigatórios:

```text
CREATE <= 25
UPDATE_SAFE <= 50
REPAIR_SAFE_VM_DUPLICATE <= 20
TOTAL <= 75
```

Ao alcançar 50 Devices, a política muda para:

```text
ABSOLUTE_AND_PERCENT
PERCENT <= 20%
```

O bootstrap não reduz exigências de identidade e não libera:

- `discovery_uid WEAK` para novo Device;
- `DUPLICATE_DESIRED_NAME`;
- conflitos de serial ou identidade;
- `REVIEW`;
- `DELEGATED`;
- registros já `BLOCKED`;
- qualquer escrita sem `--apply`.

## Relatórios nativos do PLAN

```text
netbox-discovery plan summary
netbox-discovery plan blocked
netbox-discovery plan review
netbox-discovery plan ready
netbox-discovery plan delegated
```

São somente leitura e não chamam Importer nem modificam o NetBox.

## Autoridade dos dados

```text
Nome existente no NetBox → preservado
PATCH automático de name → proibido
Serial conflitante       → não gravado
VM confirmada            → delegada à virtualização
Device manual            → protegido
```

## Lock global

Network, Hypervisor e Updater compartilham:

```text
/var/lock/netbox-discovery-global.lock
```

## Documentação obrigatória

O CI exige que README, Manual, Comandos Rápidos, Homologação, Release Notes, Security e nota de patch carreguem a versão exata do `VERSION`.
