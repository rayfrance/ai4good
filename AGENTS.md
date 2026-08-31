# AI4Good — Regras para Agentes de IA

> Leia este arquivo antes de qualquer tarefa neste workspace.
> Baseado em [lsfcin/workspace/AGENTS.md](https://github.com/lsfcin/workspace/blob/main/AGENTS.md).

<!-- norms:start -->

## Navegação

- **Leia `CONTEXT.md` antes de tocar em qualquer pasta.** Cada diretório tem um `CONTEXT.md` que
  explica o que existe ali. Navegue pela cadeia antes de criar ou modificar arquivos.
- **O sistema de arquivos é a fonte da verdade.** Nada que importa fica apenas em memória de chat.
  Se é real, é um arquivo. Se é um arquivo, está versionado.

## Segredos

- **Segredos ficam fora do git.** Tokens, senhas, chaves de API vão em `.env` (gitignored).
  O arquivo versionado é `.env.example`, que lista apenas os *nomes* das variáveis, nunca os valores.
- Se precisar de um segredo para executar uma tarefa, pergunte à usuária e escreva você mesmo o
  arquivo `.env`. **Nunca peça para ela colar o segredo diretamente no chat.**

## Git e Commits

- **GitFlow:** trabalho acontece em `feature/*`, vai para `develop`, depois `main` via PR.
- **Nunca faça commit diretamente em `main` ou `develop`** sem permissão explícita.
- **Mostre `git diff` antes de commitar.** Espere aprovação antes do `git commit`.
- Mensagens de commit em inglês, formato Conventional Commits:
  - `feat: adiciona experimento de clustering`
  - `docs: atualiza seção de metodologia`
  - `fix: corrige normalização dos dados`

## Estrutura

- **`code/`** → código Python, notebooks Jupyter, scripts de experimento.
- **`papers/`** → PDFs e anotações de artigos lidos.
- **`article/`** → artigo LaTeX (espelho do Overleaf). Não edite `.tex` aqui sem sincronizar.
- **`core/`** → fluxos e templates reutilizáveis para pesquisa e escrita.
- **`tools/`** → verificações do workspace e compilação local do artigo.

## Edição vs. Criação

- **Prefira editar a criar.** Melhorar um arquivo existente é melhor que criar um novo.
  Proliferação de arquivos é um problema, não uma solução.
- Se precisar criar, crie no lugar certo (veja `CONTEXT.md` da pasta).

## Dúvidas

- **Não assuma. Entreviste.** Se a intenção da usuária não está clara, pergunte antes de agir.
  Uma pergunta no início vale mais que refazer o trabalho depois.

<!-- norms:end -->

## Onde as coisas estão

| Arquivo / Pasta | O que é |
|---|---|
| `README.md` | Visão geral do projeto (leia primeiro) |
| `AGENTS.md` | Este arquivo — regras para o agente |
| `GEMINI.md` | Configuração do Gemini CLI como harness de backup |
| `CONTEXT.md` | Roteamento e fluxo principal do workspace |
| `workspace.code-workspace` | Atalho para abrir a raiz no VS Code |
| `code/` | Código e experimentos |
| `papers/` | Referências e anotações de leitura |
| `article/` | Artigo científico em LaTeX (Overleaf) |
| `.env` | Segredos locais (NÃO versionado) |
| `core/` | Fluxos e templates reutilizáveis |
| `tools/` | Verificações e compilação local |
| `.env.example` | Template de segredos (versionado, sem valores) |
