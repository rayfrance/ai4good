# Handoff · Luzia 2 (feixes, lúmens e rota) · 12/11/2026

- Worktree `C:\Repositorio\ai4good-sem2`, branch `feature/luzia-acoes` (base: tag `sem2`, intocada).
- **Desenho da experiência:** [docs/luzia-ux.md](../luzia-ux.md) (decidido com a Rayane): feixes valem lúmens; lúmens enchem degraus por skill; degraus formam a rota até Plena, sem datas; luz própria × luz refletida.
- **Feito:**
  - Pacote `code/luzia` (antes `code/leadroid`); skills `luzia-mentor` e `luzia-observador`; hooks `PostToolUse` e `UserPromptSubmit` em `~/.claude/settings.json` apontam para `code/luzia/observer.py`; comandos em `~/.claude/commands/luzia/`.
  - `jogo.py`: catálogo persistente de feixes (estados, histórico, descarte com motivo, restauração, revisita), livro de lúmens, degraus confirmados pela pessoa (150 lm, mínimo 40% de luz própria), rota, calibragem de ritmo pelo prazo e dossiê de evidências.
  - Observador: +10 lm de luz refletida quando o agente aplica um conceito; +20 lm de luz própria quando o conceito aparece no prompt da pessoa; até +30 lm ao explicar o porquê. Fila de feixes enviados do painel, oferecida na próxima mensagem.
  - Integração pelo harness: `/luzia:fazer` abre sessão nova (Claude Code Desktop) ou conduz aqui; subagente só prepara material. Regras para Codex, Cursor e Antigravity em `code/luzia/harness/REGRAS.md`.
  - Painel próprio (`server.py` + `painel/`): telas Hoje, Rota, Feixes, Luz própria e Ajustes; paleta roxo/lilás/laranja/terrosos; ícones SVG próprios; escala de nível; modelo configurável.
  - `modelo.py`: provedor (Gemini, Anthropic, compatível com OpenAI), modelo e chave configuráveis pelo painel; chave só no `.env`; aviso quando o modelo escolhido falha e o reserva responde. Em uso: `gemini-3.5-flash-lite` (o `gemini-4-argon` tem cota zero no plano gratuito da chave atual).
- **Verificações:** ciclo do jogo testado ponta a ponta sobre cópia da pasta privada (restaurada depois); hook testado com evento real; painel conferido no navegador; teste real do modelo (2,1 s).
- **Limites:** observador automático só no Claude Code; SDKs `anthropic`/`openai` não instalados (instalar só se a pessoa escolher esses provedores).
- **Pendente:** a Rayane declarar o nível em Ajustes (a rota parte dele); nova triagem e medições na versão commitada para o sem3; teste do ciclo num agente diferente do Claude Code; polimento com plugin de design, se instalado.
