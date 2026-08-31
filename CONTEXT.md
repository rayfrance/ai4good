# AI4Good — Contexto da Raiz
> Integra código, pesquisa bibliográfica e artigo científico em um único workspace.

Leia `AGENTS.md` primeiro. Depois leia o `CONTEXT.md` da pasta onde vai trabalhar.

## Fluxo recomendado

1. Registre as decisões do trabalho em `article/PROJECT.md`.
2. Consulte e anote referências em `papers/`.
3. Desenvolva experimentos em `code/` e registre os resultados.
4. Escreva o artigo em `article/`, relacionando afirmações a fontes ou evidências.
5. Rode `python tools/workspace_check.py` antes de cada entrega.
6. Compile com `python tools/compile_article.py` quando precisar revisar o PDF.

## Roteamento

| Caminho | Conteúdo |
| --- | --- |
| `code/` | Código, notebooks e experimentos |
| `papers/` | PDFs, referências e anotações de leitura |
| `article/` | Artigo LaTeX sincronizado com o Overleaf |
| `core/` | Fluxos e templates reutilizáveis |
| `tools/` | Verificações e comandos auxiliares |
