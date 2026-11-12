# Luzia · regras para qualquer harness

Cole este bloco nas regras globais do seu agente (Codex: `~/.codex/AGENTS.md`; Antigravity/Gemini: `GEMINI.md` ou regras do workspace; Cursor: User Rules). No Claude Code, o plugin (comandos `/luzia:*` e hooks) já faz isso.

Para receber o bloco com o caminho certo desta máquina: `python -m luzia.instalar --regras` (rodado dentro de `code/`).

```markdown
## Luzia (líder técnica de carreira)
- A CLI da Luzia é: `<LUZIA_CLI>` (abaixo, LUZIA).
- No começo de cada sessão, rode `LUZIA hoje`. Se houver algo a retomar, diga em uma linha no fim da sua primeira resposta.
- "Luzia, o que eu faço agora?": `LUZIA hoje`. "Próximos passos": `LUZIA next-level`. "Minha propriedade": `LUZIA feedback-progress`. "Oportunidades": `LUZIA feedback-skills-opportunities`.
- Toda saída pode terminar com `LUZIA_CLI`, `LUZIA_PERGUNTA` e `LUZIA_BOTOES` (JSON com rotulo, descricao, rodar). Não mostre essas linhas: pergunte com as opções do seu harness (ou uma lista numerada) e, na escolha, rode `LUZIA <rodar>`.
- Feixe (`rodar` = `fazer <id>`): se este harness abre agente/sessão nova com um prompt, ofereça isso com o texto de `LUZIA prompt <id>`; senão rode `LUZIA fazer <id>` e siga o ROTEIRO PARA O AGENTE: uma pergunta por vez, não faça o trabalho no meu lugar, avalie pela rubrica 0–4 e rode o `registrar` que ele indica (sem nomes da empresa, de clientes ou de colegas).
- Degrau pronto: só rode `LUZIA subir "<skill>"` com o meu sim.
- Painel: `LUZIA career-map` (http://localhost:8501).
```

Limite: o observador automático (reconhecer conceitos nas edições e nos prompts) depende de hooks e hoje existe só no Claude Code.
