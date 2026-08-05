# Segurança do repositório

**Versão da política:** 1.11.14

O `netbox-discovery` é distribuído em repositório público. Código e documentação podem ser públicos; dados operacionais e credenciais de clientes não podem.

## Nunca versionar

- configuração real de cliente;
- tokens, communities e senhas;
- credenciais VMware, Proxmox, Hyper-V, ONVIF, NetBox ou iDRAC;
- chaves privadas;
- relatórios, journals, logs e backups reais.

## Política de atualização

O timer `netbox-discovery-update.timer` usa o canal `stable`, executa diariamente, é persistente e possui atraso aleatório.

A instalação e os schedulers Network/Hypervisor garantem que esse timer esteja ativo. A atualização:

- não habilita `automation.apply`;
- não inicia APPLY;
- preserva token e configuração do cliente;
- valida a release antes e depois;
- executa rollback em falha;
- mantém backup da versão anterior.

Os timers de coleta usam dependência `Wants`, não `Also=`. Portanto, desabilitar coleta não desabilita atualizações.

## Decisões Network

```text
READY/CREATE                    → escreve somente com --apply
READY/UPDATE_SAFE               → escreve somente com --apply
READY/REPAIR_SAFE_VM_DUPLICATE  → escreve após write guard e preflight
READY/NOOP                      → não altera
DELEGATED                       → não escreve
REVIEW                          → não escreve
BLOCKED                         → não escreve
```

## Autoridade e nomes

```text
Nome de Device existente → autoridade do NetBox
Nome SNMP/ONVIF/DNS      → observação separada
PATCH automático de name → proibido no importer
```

## Serial

O serial só é gravado quando a evidência é suficiente e não existe conflito forte.

São proibidos:

- placeholders e sequências de teste;
- IP ou MAC usados como serial;
- serial igual a modelo ou hostname;
- escrita com `serial_confidence` LOW/NONE/CONFLICT;
- escolha automática quando fontes fortes equivalentes divergem.

## Windows Server e Workstation

Troca automática de role exige simultaneamente:

1. Device criado pelo produto;
2. match forte por serial, MAC ou IP;
3. confiança HIGH;
4. fonte SMB/CPE/fingerprint forte;
5. role atual dentro da família Windows;
6. PLAN explícito;
7. revalidação imediatamente antes do PATCH.

Device manual é preservado.

## LARGE-CIDR

O Discovery V6 divide prefixos grandes em lotes. Essa mudança altera apenas a estratégia de coleta:

- não muda política de escrita;
- não cria Device sem `--apply`;
- não habilita scheduler;
- não habilita APPLY;
- falha com identificação dos lotes problemáticos.

## Hypervisor

Ações de reclassificação, mudança de site, cluster e reparo de VM exigem preflight. O inventário Network não cria Device físico quando a identidade pertence a VM centralizada.

## Write guard

Limites padrão:

```text
CREATE: 25
UPDATE_SAFE: 50
REPAIR_SAFE: 20
TOTAL: 75
PERCENT: 20%
```

Ultrapassar um limite bloqueia ações elegíveis antes da primeira escrita.

## Documentação como controle de release

A versão exata deve constar em:

```text
README.md
docs/MANUAL.md
docs/COMANDOS-RAPIDOS.md
docs/HOMOLOGACAO.md
RELEASE-NOTES.md
SECURITY.md
docs/PATCH-<VERSÃO>.md
```

O CI bloqueia publicação quando qualquer documento obrigatório permanece em versão anterior.
