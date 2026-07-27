# netbox-discovery

Produto BKPCLOUD para inventário de infraestrutura no NetBox.

**Versão atual:** 1.9.0 — PRODUCT V1  
**Distribuição:** repositório público oficial `bkpcloud-app/netbox-discovery`  
**Canal padrão:** `stable`

## Dois pipelines independentes

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

A V1.9.0 adiciona identidade física por MAC de gerenciamento. Quando possível, o produto correlaciona IP → SNMP ifIndex → MAC; o MAC observado diretamente em L2 é fallback. MACs secundários continuam como evidência e não são usados sozinhos para fundir Devices.

O pipeline de rede persiste o MAC de gerenciamento no NetBox e pode reencontrar o mesmo Device pelo MAC quando o IP muda, mantendo as proteções de conflito antes da escrita.

A classificação também melhora impressoras e adiciona reconhecimento conservador de equipamentos Topdata/Inner. OUI/fabricante sozinho não determina a função. Evidência adicional pode classificar `TIME_ATTENDANCE`, `ACCESS_CONTROL` ou `TURNSTILE`.

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
- Proxmox VE (API Token preferencial ou usuário/senha);
- Microsoft Hyper-V via WinRM/NTLM.

O pipeline Hypervisor é independente do discovery de rede. Não existe `full-run`. A recomendação operacional é executar Hypervisor primeiro e Rede depois, em agendas separadas.

## NetBox fixo BKPCLOUD

O produto usa somente:

```text
https://inventory.bkpcloud.app.br:8080
```

`init`/`configure` não perguntam a URL. Uma URL diferente no `config.yml` é rejeitada em runtime.

## Instalação em Proxy zerado

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

O instalador valida o pacote antes de substituir o produto e preserva a configuração existente.

Política padrão após instalação:

```text
Auto-update stable: ENABLED
Network scheduler: DISABLED
Hypervisor scheduler: DISABLED
```

O auto-update verifica o canal `stable`, bloqueia downgrade, não roda junto com Network/Hypervisor, valida a nova versão antes e depois da troca e executa rollback em caso de falha. Uma versão que falhou fica em quarentena para não ser reinstalada automaticamente todos os dias.

## Primeiro uso de um site

```bash
netbox-discovery init
netbox-discovery check
```

Para ambientes virtualizados, prepare primeiro a base de virtualização:

```bash
netbox-discovery hypervisor configure
netbox-discovery hypervisor check
netbox-discovery hypervisor run
# revisar PLAN
netbox-discovery hypervisor run --apply
```

Depois execute o inventário de rede:

```bash
netbox-discovery run
# revisar PLAN
netbox-discovery run --apply
```

## Operação e saúde

```bash
netbox-discovery status
netbox-discovery self-test
netbox-discovery health
netbox-discovery health --json

netbox-discovery update status
netbox-discovery update check
netbox-discovery update run
netbox-discovery update scheduler status
```

`health --json` foi criado para integração simples com monitoramento, inclusive Zabbix.

## Segurança operacional

- `run` e `hypervisor run` sem `--apply` não gravam no NetBox;
- `REVIEW` e `BLOCKED` não entram na escrita automática;
- os pipelines replanejam antes da primeira escrita;
- IPs e MACs conflitantes são protegidos;
- reexecução é idempotente e o AUDIT V1.9.0 também valida o MAC persistido;
- nomes existentes de Devices/VMs e interfaces vinculadas são preservados;
- o pipeline Hypervisor nunca executa DELETE automático;
- Network, Hypervisor e Update compartilham lock global e não executam simultaneamente;
- retry automático é aplicado somente a leituras GET seguras da API NetBox;
- falha parcial de APPLY Hypervisor gera journal das escritas concluídas;
- Network e Hypervisor schedulers continuam opt-in;
- auto-update `stable` é habilitado por padrão.

## Credenciais

Configuração principal:

```text
/opt/netbox-discovery/config.yml
```

Credenciais/sources Hypervisor:

```text
/etc/netbox-discovery/hypervisors.json
```

O arquivo Hypervisor é exigido com permissão `0600` e proprietário `root` quando executado como root. Segredos nunca devem ser versionados.

## Documentação

- `docs/MANUAL.md`
- `docs/COMANDOS-RAPIDOS.md`
- `RELEASE-NOTES.md`
- `SECURITY.md`
