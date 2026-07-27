# netbox-discovery

Produto BKPCLOUD para descoberta, reconciliação e inventário seguro de infraestrutura no NetBox.

**Versão atual:** 1.10.1 — PRODUCT V1  
**Distribuição:** repositório público oficial `bkpcloud-app/netbox-discovery`  
**Canal padrão:** `stable`  
**NetBox BKPCLOUD:** `https://inventory.bkpcloud.app.br:8080`

> A documentação faz parte da release. A partir da 1.10.1 o self-test e o CI bloqueiam publicação quando a versão dos documentos obrigatórios diverge do `VERSION`.

## Pipelines independentes

### Rede

```text
netbox-discovery run
DISCOVER → CLASSIFY → RECONCILE → PLAN
```

Com escrita explícita:

```text
netbox-discovery run --apply
DISCOVER → CLASSIFY → RECONCILE → PLAN → IMPORT → AUDIT
```

Principais características:

- dry-run por padrão;
- identidade física por serial/MAC/IP e outras evidências;
- `management_mac` preferencialmente por IP → SNMP ifIndex → MAC;
- MACs secundários são evidência, não identidade forte isolada;
- classificação conservadora de impressoras, Topdata/Inner e outros ativos;
- `READY` pode escrever; `REVIEW` e `BLOCKED` não escrevem;
- preflight antes da primeira escrita;
- sem DELETE automático.

### Hypervisor

```text
netbox-discovery hypervisor configure
netbox-discovery hypervisor check
netbox-discovery hypervisor run
netbox-discovery hypervisor run --apply
netbox-discovery hypervisor status
```

Conectores:

- VMware vCenter ou ESXi standalone;
- Proxmox VE;
- Microsoft Hyper-V via WinRM/NTLM.

Desde a 1.10.0 cada source possui um **modo de inventário**:

```text
1 - single_site
    Todos os hosts/VMs pertencem ao Tenant/Site principal desta instalação.

2 - multi_site
    O hypervisor atende vários Sites do mesmo Tenant.

3 - multi_tenant
    O hypervisor atende vários Tenants e Sites.
```

Nos modos `multi_site` e `multi_tenant`, o configurador:

1. conecta no hypervisor;
2. coleta os hosts;
3. agrupa hosts pela rede de gerenciamento;
4. pede o mapeamento da rede para Tenant/Site;
5. cria ou reutiliza Tenant Group, Tenant e Site no NetBox quando autorizado;
6. salva o mapeamento na source.

No runtime:

- o Host é resolvido pela rede de gerenciamento;
- a VM herda o contexto Tenant/Site do Host onde está rodando;
- IP da VM é somente fallback quando o Host não resolve o contexto;
- sem mapeamento confiável o objeto vira `REVIEW`;
- serial/UUID já existente fora do contexto alvo vira `REVIEW` para reclassificação/migração, nunca CREATE duplicado;
- o pipeline Hypervisor não executa DELETE automático.

Sources criadas antes da 1.10 permanecem em `single_site` por compatibilidade até serem editadas no configurador.

## Estrutura Tenant/Site

O produto é genérico. **Não existe hardcode de cliente como `MIZU → POLIMIX`.**

No `init`, a relação é a informada na configuração:

```text
Tenant Group [opcional]
└── Tenant
    └── Site
```

No modo Hypervisor multi-contexto, os mapeamentos podem apontar para vários Tenants/Sites e o produto cria/reutiliza a estrutura de forma idempotente. Vínculos conflitantes são bloqueados; não são sobrescritos silenciosamente.

## Segurança operacional

```text
run sem --apply             = leitura/PLAN, sem escrita de inventário
hypervisor run sem --apply  = leitura/PLAN, sem escrita de inventário
--apply                      = escrita somente de READY
REVIEW                       = não escreve
BLOCKED                      = não escreve
```

Outras proteções:

- Network, Hypervisor e Update compartilham lock global;
- GETs podem receber retry seguro; POST/PATCH não recebem retry cego;
- APPLY Hypervisor mantém journal das escritas concluídas;
- credenciais Hypervisor ficam em arquivo root-only `0600`;
- scheduler de Network e Hypervisor é opt-in;
- auto-update `stable` é habilitado por padrão com backup, validação e rollback;
- nenhuma rotina Hypervisor executa DELETE automático.

## Instalação em Proxy novo

Como `root`:

```bash
bash -lc '
set -euo pipefail
if ! command -v curl >/dev/null 2>&1; then
    if command -v dnf >/dev/null 2>&1; then dnf install -y curl ca-certificates
    elif command -v yum >/dev/null 2>&1; then yum install -y curl ca-certificates
    elif command -v apt-get >/dev/null 2>&1; then apt-get update && apt-get install -y curl ca-certificates
    else echo "ERRO: não encontrei dnf, yum ou apt-get"; exit 1
    fi
fi
curl -fsSL https://raw.githubusercontent.com/bkpcloud-app/netbox-discovery/stable/install-from-github.sh | bash
'
```

O instalador preserva a configuração existente durante upgrades e não habilita os schedulers Network/Hypervisor.

## Primeiro uso

```bash
netbox-discovery init
netbox-discovery check
```

Quando existir virtualização:

```bash
netbox-discovery hypervisor configure
netbox-discovery hypervisor check
netbox-discovery hypervisor run
# revisar PLAN antes de qualquer escrita
netbox-discovery hypervisor run --apply
```

Depois, se desejado, execute o pipeline de rede:

```bash
netbox-discovery run
# revisar PLAN
netbox-discovery run --apply
```

Não existe `full-run`. Os pipelines são deliberadamente separados.

## Operação

```bash
netbox-discovery version
netbox-discovery status
netbox-discovery self-test
netbox-discovery health
netbox-discovery health --json

netbox-discovery update status
netbox-discovery update check
netbox-discovery update run
netbox-discovery update scheduler status

netbox-discovery hypervisor check
netbox-discovery hypervisor run
netbox-discovery hypervisor status
```

## Caminhos

```text
Aplicação:              /opt/netbox-discovery
Configuração principal: /opt/netbox-discovery/config.yml
Config Hypervisor:      /etc/netbox-discovery/hypervisors.json
Dependências isoladas:  /opt/netbox-discovery/vendor
Config por Site:        /opt/netbox-discovery/config/sites/
Relatórios:             /opt/netbox-discovery/reports
Backups:                /opt/netbox-discovery/backups
```

## Estado de homologação

**CI verde não significa automaticamente homologação ao vivo.**

A matriz oficial do que foi realmente testado em produção/laboratório está em:

- `docs/HOMOLOGACAO.md`

No momento da release 1.10.1, o runtime multi-Tenant/multi-Site da 1.10 passou CI/regressões, mas ainda precisa ser homologado ao vivo no DCM antes de habilitar APPLY multi-contexto.

## Documentação obrigatória

- `README.md`
- `docs/MANUAL.md`
- `docs/COMANDOS-RAPIDOS.md`
- `docs/HOMOLOGACAO.md`
- `RELEASE-NOTES.md`
- `SECURITY.md`
