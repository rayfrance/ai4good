---
name: luzia-observador
description: Observador passivo da Luzia no Claude Code. Um hook PostToolUse (code/luzia/observer.py, registrado em ~/.claude/settings.json) roda a cada edição de arquivo ou git commit, compara a atividade com as lacunas do plano de carreira e intervém em uma linha ou só registra, conforme o modo.
---

# Luzia · observador de sessão

**Como funciona (real, no Claude Code):**
- O hook `PostToolUse` (matcher `Edit|Write|MultiEdit|Bash`) roda `code/luzia/observer.py` localmente, sem chamar o modelo.
- Ele só age nos repositórios listados em `code/luzia/private/observer.json` (`autorizados`).
- Compara o nome do arquivo e o trecho editado com as `palavras_chave` das skills que ainda têm lacuna (autoavaliação < alvo) no plano salvo.
- Grava em `private/sessao.jsonl` só o evento mascarado (horário, skill, extensão, ferramenta). Nunca grava caminho nem código.

**Modos** (`python -m luzia.cli modo <modo>` ou o seletor do painel):
- `ativo`: na 1ª vez que uma skill aparece na sessão, a Luzia avisa em uma linha no chat (`systemMessage` + `additionalContext`).
- `passivo`: só registra; os eventos aparecem no feed "Ao vivo" do painel.
- `sob_demanda`: não observa; a Luzia só responde aos comandos `/luzia:*`.

**Quando você (Claude) receber o contexto `[Luzia · observador]`:** termine a resposta com uma única linha começando com "✨ Luzia:", ligando o conceito à mudança atual, e ofereça `/luzia:feedback-skills-opportunities`. Não interrompa a tarefa nem mostre código da empresa.

**Limite:** isto vale para o Claude Code. Codex, Cursor e Antigravity ainda não têm o observador.
