# netbox-discovery

Produto BKPCLOUD para inventário de infraestrutura no NetBox.

**Versão atual:** 1.8.0 — PRODUCT V1
**Distribuição:** repositório público oficial `bkpcloud-app/netbox-discovery`

## Dois pipelines independentes

### Rede — comando original

```text
netbox-discovery run
DISCOVER → CLASSIFY → RECONCILE → PLAN
```

Com escrita explícita:

```text
netbox-discovery run --apply
DISCOVER → CLASSIFY → RECONCILE → PLAN → IMPORT → AUDIT
```

### Hypervisor — V1.8.0

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

O pipeline Hypervisor é independente do discovery de rede. Não existe `full-run`.
A recomendação operacional é executar Hypervisor primeiro e Rede depois, em agendas separadas.

## NetBox fixo BKPCLOUD

O produto V1.8.0 usa somente:

```text
https://inventory.bkpcloud.app.br:8080
```

`init`/`configure` não perguntam mais a URL. Uma URL diferente no `config.yml` é rejeitada em runtime.
Essa trava evita uso acidental do produto contra outro NetBox; como o código é público, não é um mecanismo de licenciamento criptográfico.

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
curl -fsSL https://raw.githubusercontent.com/bkpcloud-app/netbox-discovery/main/install-from-github.sh | bash
'
```

O instalador preserva configurações existentes e não habilita scheduler.
Dependências de VMware/Hyper-V são instaladas juntas sob `/opt/netbox-discovery/vendor` somente no primeiro uso de um desses conectores; Proxmox usa a biblioteca padrão do Python.

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
```

Revise o PLAN Hypervisor. Somente depois:

```bash
netbox-discovery hypervisor run --apply
```

Depois execute o inventário de rede normal:

```bash
netbox-discovery run
# revisar PLAN
netbox-discovery run --apply
```

## Segurança operacional

- `run` e `hypervisor run` sem `--apply` não gravam no NetBox;
- `REVIEW` e `BLOCKED` não entram na escrita automática;
- os pipelines replanejam antes da primeira escrita;
- IPs e MACs conflitantes são protegidos;
- reexecução é idempotente;
- nomes existentes de Devices/VMs e interfaces vinculadas são preservados;
- o pipeline Hypervisor nunca apaga objetos automaticamente;
- instalador nunca habilita os timers;
- schedulers de rede e Hypervisor são independentes.

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
