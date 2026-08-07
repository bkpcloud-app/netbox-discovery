# netbox-discovery 1.11.25

## Correção

Corrige o planejamento de reclassificação de VMs já existentes no NetBox quando a VM possui Host/Device ou Cluster associado e o Site explícito da VM diverge do contexto autoritativo resolvido pelo vCenter.

## Regra

- VM herda o Site do Host/Cluster autoritativo;
- Cluster continua opcional;
- Host standalone é válido e suas VMs devem permanecer no mesmo Site do Host;
- identidade global forte continua obrigatória para reclassificação automática;
- o motor continua usando `RECLASSIFY_SAFE`, nunca CREATE duplicado para a mesma identidade;
- antes da escrita, o preflight confirma que o Device/Cluster pai está no Site alvo;
- a escrita da VM mantém atualização atômica de Tenant + Site;
- REVIEW/BLOCKED permanecem sem escrita automática.

## Caso corrigido

Exemplo: Host `10.5.1.21` em `MIZU/FAB`, sem Cluster, com VMs anteriormente gravadas em `DCM`. O planner agora reconhece a identidade existente e gera `RECLASSIFY_SAFE` para mover o Site explícito das VMs para `FAB`, desde que o parent preflight confirme o Host em FAB.

## Segurança

Nenhuma rotina de delete foi adicionada. A correção não infere Site pelo nome da VM; utiliza somente o contexto Tenant/Site resolvido pelo inventário do hypervisor e validado contra o parent real no NetBox.
