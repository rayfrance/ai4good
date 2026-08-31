# AI4Good — Harness de Backup para Gemini CLI

> Configuração de contexto para o Gemini CLI, usado quando o Codex atingir o limite.
> O Gemini CLI lê este arquivo ao trabalhar neste projeto.

## Identidade do Projeto

- **Nome:** AI4Good — Workspace da Disciplina de Tópicos Avançados em IA
- **Instituição:** UFRPE (Universidade Federal Rural de Pernambuco)
- **Disciplina:** Tópicos Avançados em Inteligência Artificial
- **Objetivo:** Produzir código de pesquisa e um artigo científico como produto final
- **Referência:** Workspace do professor disponível em https://github.com/lsfcin/workspace

## Estrutura de Pastas

```
ai4good/
├── code/        → experimentos Python, notebooks Jupyter
├── papers/      → artigos científicos lidos e anotados
└── article/     → artigo LaTeX (sincronizado com Overleaf)
```

## Regras de Operação

Leia [`AGENTS.md`](AGENTS.md) para o conjunto completo de regras. Resumo crítico:

1. **Leia `CONTEXT.md` de qualquer pasta antes de criar/modificar arquivos nela.**
2. **Nunca commite diretamente em `main` ou `develop`.** Mostre o diff e aguarde aprovação.
3. **Segredos ficam em `.env` (gitignored).** Nunca no código ou no chat.
4. **GitFlow:** `feature/*` → `develop` → `main`.
5. **Dúvida? Pergunte.** Não assuma a intenção da usuária.

## Contexto da Usuária

- **Nome:** Rayane France
- **Papel:** Estudante de graduação (Licenciatura em Computação — UFRPE)
- **Nível de familiaridade com workspace:** Iniciante — prefira explicações simples e diretas.

## Overleaf

- **Projeto:** BRACIS Paper Prototype 1
- **URL do projeto:** https://overleaf.com/project/6a920a859c5f584768569a70
- **Pasta local:** `article/` (versionada pelo repositório principal)
- **Credenciais:** Armazenadas em `.env` (nunca no código)

## Convenções

- Commits em inglês, formato Conventional Commits (`feat:`, `docs:`, `fix:`, `chore:`)
- Nomes de arquivo em `kebab-case` para documentação, `snake_case` para Python
- Notebooks com prefixo numérico: `01-exploracao.ipynb`, `02-modelo.ipynb`

## Harness de Backup

Quando o Codex atingir o limite, abra esta mesma pasta no Gemini CLI. Antes de continuar:
1. Leia `AGENTS.md` para as regras
2. Leia o `CONTEXT.md` da pasta onde está trabalhando
3. Leia `README.md` para o contexto geral do projeto
