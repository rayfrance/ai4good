# article/ — Artigo Científico (Overleaf)

> Leia este arquivo antes de criar ou modificar qualquer coisa nesta pasta.

## O que é esta pasta

Esta pasta contém o artigo do Overleaf dentro do **repositório principal AI4Good**. Isso significa:

- O código LaTeX aqui é o **mesmo** que você vê no Overleaf
- As mudanças feitas no Overleaf precisam ser **puxadas** com `git subtree pull`
- As mudanças feitas aqui precisam ser **enviadas** com `git subtree push` para aparecer no Overleaf

## Projeto Overleaf

- **Nome:** BRACIS Paper Prototype 1
- **URL:** https://overleaf.com/project/6a920a859c5f584768569a70

## Como sincronizar

```bash
# Execute na raiz do AI4Good.

# Baixar mudanças do Overleaf para article/
git subtree pull --prefix article overleaf main --squash

# Depois de revisar e commitar mudanças no artigo, enviar ao Overleaf
git subtree push --prefix article overleaf main
```

> ⚠️ **Atenção:** o Overleaf usa a branch `main`. O GitHub é `origin`; o Overleaf é o remoto `overleaf`.

## Estrutura esperada

```
article/
├── CONTEXT.md           ← orientação da pasta
├── PROJECT.md           ← decisões do trabalho
├── ROADMAP.md           ← próximas etapas
├── samplepaper.tex      ← arquivo LaTeX principal
├── llncs.cls            ← classe LNCS/Springer
└── splncs04.bst         ← estilo bibliográfico LNCS
```

## Credenciais

O token de acesso ao Overleaf está em `.env` na raiz do projeto (nunca aqui).

## O que NÃO fazer

- ❌ Não edite arquivos `.tex` aqui E no Overleaf ao mesmo tempo (causa conflito)
- ❌ Não commite PDFs compilados aqui (o Overleaf compila online)
- ❌ Não crie outro `.git/` dentro desta pasta
