# netbox-discovery 1.11.34 — Repository hygiene e continuidade operacional

## Objetivo

Garantir que o repositório seja suficiente para retomar o projeto sem depender do histórico de conversa e remover artefatos comprovadamente obsoletos.

## Documentação

O Manual passa a conter uma seção **Ponto de retomada** com:

```text
estado técnico atual;
decisões operacionais vigentes;
evidência live já confirmada;
limites do que ainda não foi revalidado ao vivo;
próxima etapa funcional: NetBox → Zabbix;
regra de promoção stable → main.
```

Toda release precisa atualizar a versão exata de README, Manual, Comandos Rápidos, Homologação, Release Notes, Security e nota de patch.

## Higiene

Removidos por estarem obsoletos, não serem usados pelo runtime/CI e conterem informação antiga:

```text
SHA256SUMS
netbox-discovery/docs/PRODUCT-V1.md
netbox-discovery/workflow.yml
```

`netbox-discovery/config.yml.example` foi corrigido para:

```text
https://inventory.bkpcloud.app.br
```

sem `:8080`.

## O que não foi removido

Módulos históricos versionados continuam presentes quando são importados pelas camadas atuais ou exercitados pela suíte de regressão. Eles não devem ser apagados sem refatoração explícita e CI completo.

## Proteção contra regressão

`tests/test_product_1_11_34.py` exige:

```text
versões raiz/pacote sincronizadas;
documentos na versão exata;
Ponto de retomada no Manual;
endpoint correto no config.yml.example;
artefatos obsoletos ausentes;
installer sem referência ao workflow.yml removido.
```

O workflow CI também valida a versão exata dos documentos obrigatórios.
