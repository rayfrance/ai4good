# Luzia · regras para qualquer harness

Cole este bloco nas regras globais do seu agente (Codex: `~/.codex/AGENTS.md`; Antigravity/Gemini: `GEMINI.md` ou regras do workspace; Cursor: User Rules). No Claude Code, os comandos `/luzia:*` e os hooks já fazem isso.

```markdown
## Luzia (líder técnica de carreira)
- No começo de cada sessão, rode `cd C:/Repositorio/ai4good-sem2/code && python -m luzia.cli fila`. Se houver ação enviada do painel, ofereça em uma linha: abrir em sessão/agente novo (use a ferramenta nativa deste harness com o texto de `python -m luzia.cli prompt <id>`) ou fazer aqui (`python -m luzia.cli fazer <id>` e siga o ROTEIRO).
- Quando eu pedir "Luzia, próximos passos", rode `python -m luzia.cli next-level`; "Luzia, minha propriedade", `python -m luzia.cli feedback-progress`; "Luzia, oportunidades", `python -m luzia.cli feedback-skills-opportunities`. Mostre a saída como veio e ofereça as ações listadas.
- Ao conduzir uma ação: uma pergunta por vez, não faça o trabalho no meu lugar, avalie pela rubrica 0–4 e rode `python -m luzia.cli registrar <id> --nota N --resumo "..."` (sem nomes da empresa).
- Quando um degrau ficar pronto, pergunte se eu quero subir e rode `python -m luzia.cli subir "<skill>"` só com o meu sim.
- "Luzia, dossiê": `python -m luzia.cli dossie`. "Descartar feixe": `python -m luzia.cli descartar <id> --motivo nao_faz_sentido|ja_domino|agora_nao`.
- Painel: `python -m luzia.cli career-map` (http://localhost:8501).
```

Limite: o observador passivo automático (avisar quando uma skill do plano aparece numa edição) depende de hooks e hoje existe só no Claude Code.
