## V1.10.3 — Rede de gerenciamento autoritativa VMware

Correção do resolver multi-contexto após a homologação real mostrar que um ESXi pode expor vários vmkernel com o serviço VMware `management` habilitado, embora apenas uma rede seja adequada para posicionar o Host em Tenant/Site.

### Problema observado ao vivo

Na source VMware `10.1.1.20`, quatro Hosts do Datacenter `DCM` apresentaram 11 redes marcadas como `management`:

```text
10.1.1.0/24
192.168.140.0/24
192.168.141.0/24
192.168.142.0/24
192.168.143.0/24
192.168.160.0/24
192.168.161.0/24
192.168.180.0/24
192.168.181.0/24
192.168.190.0/24
192.168.191.0/24
```

A rede de gestão conhecida dos Hosts é `10.1.1.0/24`. Portanto, transformar todas as interfaces `management=True` em mappings Tenant/Site era incorreto.

### Resolver 1.10.3

Para VMware, o produto passa a selecionar uma rede de gerenciamento autoritativa por Host:

1. IP de vmkernel que corresponde à resolução do FQDN/nome do ESXi;
2. `vmk0` marcada como management;
3. única rede management candidata;
4. múltiplas candidatas sem evidência forte → sem resolução automática / REVIEW.

Interfaces auxiliares continuam no inventário, mas não decidem Site/Tenant.

### Regressões

- reproduz o caso real `vmk0=10.1.1.x` + múltiplas `192.168.x` marcadas management;
- confirma que somente `10.1.1.0/24` participa do grouping/mapping;
- testa FQDN apontando para um vmkernel diferente de `vmk0`;
- testa ambiguidade sem DNS/vmk0, que deve permanecer sem resolução;
- mantém regressões de multi-Site/multi-Tenant e identidade global.

### Segurança e documentação

- nenhuma mudança na política de APPLY/DELETE;
- não move objetos existentes automaticamente;
- README, Manual, Comandos Rápidos, Security, Release Notes e Matriz de Homologação acompanham a versão;
- CI PASS não equivale a LIVE PASS: a seleção 1.10.3 só vira LIVE PASS depois de repetida no DCM.

---

## V1.10.2 — Agrupamento de redes VMware por Datacenter

Correção de UX e segurança identificada durante a primeira homologação real do modo `multi_tenant` no DCM.

### Problema observado ao vivo

Na source VMware `10.1.1.20`, o vCenter retornou 4 Hosts do Datacenter `DCM`, porém 11 CIDRs associados a vmkernel com o serviço VMware `management` habilitado. A 1.10.1 perguntaria Tenant/Site 11 vezes, embora várias dessas redes pertençam ao mesmo conjunto de Hosts/Datacenter.

A configuração foi interrompida antes de salvar qualquer mapping novo ou provisionar estrutura incorreta.

### Wizard 1.10.2

- redes de management que pertencem inequivocamente a um único VMware Datacenter são agrupadas;
- o wizard pergunta Tenant/Site uma vez por grupo de Datacenter;
- todos os CIDRs do grupo recebem mappings equivalentes por baixo;
- o usuário pode responder que o Datacenter não representa um único Site e abrir revisão por rede;
- rede sem Datacenter único ou compartilhada entre Datacenters continua individual;
- mappings existentes divergentes não são consolidados silenciosamente;
- para um Datacenter cujo nome coincide com o Site base atual, o Tenant/Site atual pode ser sugerido como default confirmável, sem hardcode de cliente.

### Runtime

O resolver continua baseado nos mappings de CIDR. A 1.10.2 altera o modo de construir os mappings no configurador; não muda a política de escrita, não adiciona DELETE e não move objetos existentes automaticamente.

### Testes e documentação

- adiciona regressões para múltiplas redes management no mesmo Datacenter;
- valida separação de Datacenters distintos;
- valida que rede ambígua compartilhada não é agrupada;
- README, Manual, Comandos Rápidos, Security, Release Notes e Matriz de Homologação acompanham a versão.

**Estado na publicação:** CI PASS; agrupamento 1.10.2 ainda precisa ser repetido ao vivo no DCM para virar LIVE PASS.

---

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
- solicita Tenant Group/Tenant/Site;
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

### Auto-update stable

- instalação oficial passa a usar o canal `stable` por padrão;
- auto-update é habilitado automaticamente na instalação;
- Network e Hypervisor schedulers continuam desabilitados por padrão;
- valida candidato antes de substituir o produto;
- mantém backup da versão anterior e executa rollback se a nova versão falhar;
- bloqueia downgrade automático;
- versão que falha entra em quarentena.

### Hardening operacional

- Network, Hypervisor e Update compartilham lock global;
- retry/backoff apenas para GETs seguros da API NetBox;
- POST/PATCH/DELETE não recebem retry cego;
- Hypervisor registra journal de writes;
- adiciona status consolidado do produto, updater e pipelines.

---

## V1.8.0 — Hypervisor integrado e endpoint BKPCLOUD

- fixa o NetBox em `https://inventory.bkpcloud.app.br:8080`;
- adiciona conectores VMware, Proxmox e Hyper-V;
- adiciona pipeline Hypervisor independente;
- cria/reconcilia Prefixes explícitos, Clusters, hosts, VMs/containers, interfaces, MACs e IPs;
- dry-run por padrão, preflight antes de escrita e sem DELETE automático;
- credenciais Hypervisor protegidas em `/etc/netbox-discovery/hypervisors.json`.

---

## V1.7.0 — Estabilização de classificação e inventário

- melhora classificação de equipamentos industriais/CFTV;
- prioriza identidade física;
- ignora nomes/seriais genéricos;
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
- corrige instalação de arquivos do produto;
- preserva configuração operacional existente durante upgrade.

## V1.5.1 — Correção de DNS reverso

- instala `dig` automaticamente quando necessário;
- reverse DNS vira enriquecimento não fatal;
- ausência de PTR não interrompe DISCOVER.

## V1.5.0 — PRODUCT V1

Consolidação inicial do pipeline público distribuído por GitHub com instalação/bootstrap, configuração preservada em upgrade e scheduler desabilitado até ação explícita.
