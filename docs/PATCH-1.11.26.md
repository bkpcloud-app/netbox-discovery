# netbox-discovery 1.11.26

## Correção

Corrige o caso real observado em FAB no qual uma VM já existente e fortemente correlacionada chegava ao planner como `READY/NOOP`, mas permanecia com Site antigo (`DCM`) mesmo estando vinculada a um Host físico no Site correto (`FAB`).

## Causa

A 1.11.25 adicionou a regra de herança de Site por Host/Cluster, porém o novo planner examinava apenas registros com ação intermediária `CREATE` ou `UPDATE_SAFE`.

No ambiente real, VMs já existentes como `SRV-AB01`, `SRV-AB02`, `SNOC-MZAB` e `SRV-BKP-AB` foram corretamente encontradas e correlacionadas, portanto chegaram ao planner como:

```text
READY/NOOP
```

Como `NOOP` não era examinado, nenhuma delas virava `RECLASSIFY_SAFE`.

## Regra corrigida

- `READY/NOOP` de VM também é inspecionado para divergência de Site;
- a VM precisa possuir correspondência global forte;
- a VM precisa estar vinculada a Device/Host ou Cluster;
- se o Site atual divergir do contexto autoritativo do vCenter, o plano passa para `RECLASSIFY_SAFE`;
- `REVIEW/NOOP` não é promovido automaticamente;
- Cluster continua opcional;
- Host standalone continua válido;
- nenhuma inferência é feita pelo nome da VM;
- nenhuma rotina de delete foi adicionada.

## Caso FAB

```text
Host 10.5.1.21 -> Site FAB
VM SRV-AB01    -> Site DCM (estado antigo)
VM SRV-AB02    -> Site DCM (estado antigo)
SNOC-MZAB      -> Site DCM (estado antigo)
SRV-BKP-AB     -> Site DCM (estado antigo)
```

Resultado esperado no dry-run da 1.11.26:

```text
READY | VM | SRV-AB01   | RECLASSIFY_SAFE | alvo=MIZU/FAB
READY | VM | SRV-AB02   | RECLASSIFY_SAFE | alvo=MIZU/FAB
READY | VM | SNOC-MZAB  | RECLASSIFY_SAFE | alvo=MIZU/FAB
READY | VM | SRV-BKP-AB | RECLASSIFY_SAFE | alvo=MIZU/FAB
```

A escrita continua exigindo `--apply` e permanece protegida pelo preflight do parent real no NetBox.
