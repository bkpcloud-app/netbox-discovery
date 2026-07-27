## V1.10.1 — Documentação como parte obrigatória da release

Release de hardening documental. Não altera a lógica de inventário multi-contexto criada na 1.10.0.

### Documentação

- atualiza `README.md` para a arquitetura 1.10;
- reescreve `docs/MANUAL.md` para o produto atual;
- atualiza `docs/COMANDOS-RAPIDOS.md`;
- atualiza `SECURITY.md`;
- adiciona `docs/HOMOLOGACAO.md` separando CI de validação real;
- remove documentação antiga que tratava `MIZU → POLIMIX` como regra conhecida/hardcoded;
- documenta explicitamente que Tenant Group é configuração genérica.

### Trava de release

- `self-test` passa a validar que a documentação obrigatória corresponde ao `VERSION`;
- CI valida a mesma regra;
- uma release não deve entrar em `stable` com manual/README/release notes de versão anterior.

### Transparência de homologação

- `CI PASS` e `LIVE PASS` passam a ser estados diferentes na documentação;
- Hypervisor multi-Tenant/multi-Site da linha 1.10 permanece `CI PASS / NOT LIVE` até homologação real no DCM;
- persistência MAC V2 do pipeline de rede continua marcada como não homologada ao vivo.

---

## V1.10.0 — Hypervisor multi-Tenant / multi-Site

Evolução arquitetural do Hypervisor para managers centrais que atendem vários Sites ou vários Tenants.

### Modos de source

```text
single_site
multi_site
multi_tenant
```

- sources antigas permanecem `single_site` por compatibilidade até serem editadas;
- `multi_site` atende vários Sites do Tenant principal;
- `multi_tenant` permite mapping para vários Tenants/Sites.

### Wizard de mapping

- coleta hosts do hypervisor;
- agrupa por rede de gerenciamento;
- mostra Hosts/Datacenters/Clusters como evidência;
- solicita Tenant Group/Tenant/Site por rede;
- cria ou reutiliza a estrutura NetBox quando autorizado;
- salva os mappings na source.

### Resolver V3

- Host é resolvido por rede de gerenciamento;
- VM herda o contexto do Host onde está rodando;
- IP da VM é fallback;
- sem resolução confiável → `REVIEW`;
- inventário é dividido em contextos Tenant/Site e processado pelo PLAN/APPLY/AUDIT por contexto.

### Proteção global

- serial/UUID já existente fora do contexto alvo impede CREATE duplicado;
- registro vira `REVIEW` para reclassificação/migração segura;
- nenhuma rotina automática de DELETE/movimentação foi adicionada.

### Testes

- regressões antigas continuam no CI;
- testes novos cobrem grouping por rede de gerenciamento, herança de Site pela VM, host sem mapping, multi-site, multi-tenant e guarda contra duplicação global.

**Estado na publicação inicial:** CI PASS; homologação real multi-contexto ainda pendente.

---

## V1.9.8 — Diagnóstico visível de resíduos

- dry-run Hypervisor passa a listar `REVIEW/BLOCKED` no terminal;
- lista também `READY/UPDATE_SAFE` residuais;
- mostra nome, tipo, ação, motivo e campos pendentes;
- AUDIT passa a expor WARN/FAIL sem exigir leitura manual de JSON.

---

## V1.9.7 — Consistência V2 entre dry-run, preflight e audit

- corrige APPLY que recompunha preflight usando planner antigo;
- preflight e audit passam a usar a mesma política V2 do dry-run;
- preserva o cliente NetBox rastreado pelo runner e journal das escritas;
- validado ao vivo em import real de dois vCenters, porém o pós-audit revelou resíduos e o desenho single-site mostrou-se inadequado para managers multi-Site.

---

## V1.9.6 — Política de IP autoritativo de VM

- mantém todos os IPs no discovery para auditoria;
- PLAN usa IP primário e/ou IP pertencente às redes relevantes como identidade/vínculo autoritativo;
- IP secundário interno fora dessas redes não bloqueia VM;
- elimina falso conflito observado com bridge/container IP repetido `172.18.0.1` sem criar exceção específica para esse endereço.

---

## V1.9.5 — Pendências Hypervisor no terminal

- `hypervisor run` passa a exibir automaticamente cada `REVIEW/BLOCKED`;
- mostra nome, tipo, ação e motivo;
- evita exigir scripts manuais para abrir o JSON do PLAN.

---

## V1.9.4 — Dependência VMware visível na mesma execução

- remove import prematuro do collector no configurador;
- adiciona carregamento tardio após criação do `vendor`;
- corrige falha em que pyVmomi era instalado, mas não ficava visível no mesmo processo;
- configuração/conexão/save VMware validada ao vivo no DCM.

---

## V1.9.3 — Dependências VMware isoladas

- VMware deixa de instalar dependências Hyper-V desnecessárias;
- conjunto top-level VMware compatível com Python 3.6: `six==1.16.0` e `pyvmomi==7.0.3`;
- remove do caminho VMware a dependência acidental de cryptography/Rust;
- isolamento validado ao vivo no DCM.

---

## V1.9.2 — Tenant Group genérico

- remove qualquer hardcode de cliente/Tenant Group;
- Tenant Group passa a ser explícito/opcional;
- troca de Tenant não herda grupo antigo implicitamente;
- estrutura `Tenant Group → Tenant → Site` validada ao vivo no DCM.

---

## V1.9.1 — Provisionamento da estrutura base

- `init` passa a garantir Tenant Group opcional, Tenant e Site no NetBox;
- criação/reuso é idempotente;
- vínculos conflitantes são bloqueados em vez de sobrescritos silenciosamente.

---

## V1.9.0 — Identidade física, auto-update e hardening operacional

Release de consolidação do produto para operação em escala, preservando a política de dry-run, preflight, idempotência e ausência de DELETE automático.

### Identidade física de rede

- adiciona `management_mac` derivado preferencialmente por IP → SNMP ifIndex → MAC;
- usa o MAC observado diretamente em L2 como fallback;
- MACs secundários/interface continuam como evidência, mas não fundem Devices sozinhos;
- persiste MAC de gerenciamento no NetBox e o vincula à interface correspondente;
- PLAN consulta os MACs existentes no NetBox e pode reencontrar o mesmo Device pelo MAC após mudança de IP;
- conflito entre serial, MAC e IP continua bloqueando escrita automática;
- AUDIT valida a persistência e a associação correta do MAC.

### Impressoras e controle de acesso

- melhora normalização de fabricantes de impressora, incluindo HP, Epson, Canon, Kyocera, Ricoh, Lexmark, Xerox, Zebra e OKI, preservando regras existentes;
- mantém classificação conservadora: uma porta genérica isolada não deve inventar fabricante/modelo;
- adiciona evidência Topdata/Inner sem usar OUI sozinho para adivinhar função;
- TCP 3570 pode compor evidência de `ACCESS_CONTROL` quando combinado com identidade Topdata/Inner;
- TCP 51000 pode compor evidência de `TIME_ATTENDANCE` quando combinado com identidade Topdata/Inner;
- evidência explícita de catraca pode classificar `TURNSTILE`;
- adiciona roles NetBox `TIME ATTENDANCE`, `ACCESS CONTROL` e `TURNSTILE` quando necessários.

### Auto-update stable

- instalação oficial passa a usar o canal `stable` por padrão;
- auto-update é habilitado automaticamente na instalação;
- Network e Hypervisor schedulers continuam desabilitados por padrão;
- valida candidato antes de substituir o produto;
- mantém backup da versão anterior e executa rollback se a nova versão falhar no self-test/check;
- bloqueia downgrade automático;
- versão que falha entra em quarentena e não é tentada novamente automaticamente até surgir outra versão ou execução manual com retry;
- timer diário usa `RandomizedDelaySec=30m` para evitar atualização simultânea de todos os proxies;
- retenção conserva os últimos cinco backups de update e remove reports locais antigos.

### Hardening operacional

- Network, Hypervisor e Update compartilham `/var/lock/netbox-discovery-global.lock`;
- adiciona retry/backoff apenas para GETs seguros da API NetBox em erros transitórios;
- POST/PATCH/DELETE não recebem retry cego;
- Hypervisor registra journal de writes quando um APPLY falha depois de alterações parciais;
- dependências VMware/Hyper-V passam a usar fingerprint SHA256 do conjunto de pacotes para decidir quando reconstruir o vendor;
- configuração de scheduler e estado do systemd passam a ser sincronizados pelos configuradores;
- adiciona status consolidado do produto, updater e pipelines.

### Saúde e validação

Novos comandos:

```text
netbox-discovery self-test
netbox-discovery health
netbox-discovery health --json
netbox-discovery update status
netbox-discovery update check
netbox-discovery update run
netbox-discovery update scheduler {enable|disable|status}
```

- `self-test` não depende de `config.yml`, permitindo validar instalação nova e candidato de upgrade;
- `health --json` fornece saída simples para Zabbix e outras ferramentas;
- CI valida sincronismo dos arquivos VERSION, sintaxe shell, compilação Python, self-test e regressões de identidade física.

---

## V1.8.0 — Hypervisor integrado e endpoint BKPCLOUD

Release de produto que adiciona inventário de virtualização sem alterar o pipeline de rede existente.

### Endpoint

- fixa o NetBox em `https://inventory.bkpcloud.app.br:8080`;
- `init`/`configure` deixam de pedir a URL;
- runtime recusa `config.yml` apontando para outro NetBox.

### Hypervisor

- adiciona `netbox-discovery hypervisor`;
- conectores VMware vCenter/ESXi, Proxmox VE e Hyper-V WinRM/NTLM;
- comandos `configure`, `check`, `run`, `run --apply`, `status` e `scheduler`;
- scheduler independente do pipeline de rede;
- não existe `full-run`;
- cria/reconcilia Prefixes explícitos, Clusters, hosts, VMs/containers, interfaces, MACs e IPs;
- Proxmox usa UUID quando disponível e identidade estável baseada em source/VMID como fallback;
- disco de VM é convertido para MB no modelo NetBox.

### Segurança e idempotência

- dry-run por padrão;
- replanejamento/preflight antes da primeira escrita;
- conflitos de IP, MAC, identidade, Role e Cluster Type viram REVIEW/bloqueio antes da escrita;
- preserva nomes manuais de Devices, VMs e interfaces já vinculadas;
- atualiza pinning de VM migrada quando comprovado pela API;
- não executa DELETE;
- credenciais Hypervisor ficam em `/etc/netbox-discovery/hypervisors.json` com proteção root-only.

---

## V1.7.0 — Estabilização de classificação e inventário

- reconhece WEG SRW01-ETH, Siemens PAC3220/SCALANCE e outros footprints observados;
- melhora classificação CFTV conservadora;
- prioriza identidade física sobre banners de aplicação/TLS;
- ignora nomes/seriais genéricos;
- adiciona probes CFTV direcionados e padroniza timestamps;
- mantém as proteções de escrita da linha 1.6.

---

## V1.6.0 — Reconciliação segura e descoberta CFTV

- MAC broadcast, zerado e multicast não são usados como identidade;
- seriais genéricos são ignorados;
- LLDP chassis-id válido pode ser evidência forte;
- endereços de rede/broadcast e exclusões são respeitados;
- amplia fingerprints/probes CFTV sem autenticação forçada;
- discovery permanece read-only até `--apply`.

---

## V1.5.2 — Correção do instalador e sincronização de versão

- sincroniza `VERSION` da raiz e do pacote;
- corrige instalação de `config.yml`, `bin`, `lib` e `modules`;
- preserva configuração operacional existente durante upgrade.

## V1.5.1 — Correção de DNS reverso

- instala `dig` automaticamente quando necessário;
- reverse DNS vira enriquecimento não fatal;
- ausência de PTR não interrompe DISCOVER.

## V1.5.0 — PRODUCT V1

Consolidação inicial do pipeline público distribuído por GitHub com instalação/bootstrap, configuração preservada em upgrade e scheduler desabilitado até ação explícita.
