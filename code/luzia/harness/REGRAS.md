# Luzia · regras para qualquer harness

Cole este bloco nas regras globais do seu agente (Codex: `~/.codex/AGENTS.md`; Antigravity/Gemini: `GEMINI.md` ou regras do workspace; Cursor: User Rules). No Claude Code, o plugin (comandos `/luzia:*` e hooks) já faz isso.

Para receber o bloco com o caminho certo desta máquina: `python -m luzia.instalar --regras` (rodado dentro de `code/`).

```markdown
## Luzia (líder técnica de carreira)
- A CLI da Luzia é: `<LUZIA_CLI>` (abaixo, `LUZIA`).
- No começo de cada sessão, rode `LUZIA hoje`. Se houver algo a retomar, diga em uma linha no fim da sua primeira resposta.
- Consultas principais:
  - "Luzia, o que eu faço agora?": `LUZIA hoje`
  - "Trajetória / prismas / versões": `LUZIA trajetoria`
  - "Mudar a trajetória (incluir, mudar meta, arquivar ou reativar prisma)": `LUZIA pedido abrir <tipo> "<prisma>" --motivo "<motivo>"` (depois `ajustar`, `aceitar` ou `recusar`)
  - "Avanços" (com filtros opcionais): `LUZIA avancos [--estado E] [--prisma P] [--tipo T]`
  - "Acender novos avanços de um prisma": `LUZIA acender "<prisma>"`
  - "Entregas e propriedade intelectual": `LUZIA entregas [--ampliar DIAS]` e `LUZIA entrega <id>`
  - "Declarar nível de partida (0–5)": `LUZIA nivel "<prisma>" <0-5>`
  - "Plano em horizontes / próximo nível": `LUZIA next-level` · Dossiê formal: `LUZIA dossie`
- Toda saída pode terminar com `LUZIA_CLI`, `LUZIA_PERGUNTA` e `LUZIA_BOTOES` (JSON com `rotulo`, `descricao`, `rodar`). Não mostre essas linhas brutas: apresente as opções ao usuário (ou lista numerada) e, após a escolha, rode `LUZIA <rodar>`.
- Avanço (`rodar` = `fazer <id>`): se este harness abre agente/sessão nova com um prompt, ofereça isso com o texto de `LUZIA prompt <id>`; senão rode `LUZIA fazer <id>` e siga o `ROTEIRO PARA O AGENTE`: uma pergunta por vez, não faça o trabalho no lugar da pessoa, avalie pela rubrica 0–4 e rode o `registrar` que ele indica (sem nomes da empresa, produtos internos, clientes ou colegas).
- Nível pronto: só rode `LUZIA subir "<prisma>"` com o **sim explícito** da pessoa.
- Painel local: `LUZIA career-map` (`http://localhost:8501`).
```

Limite: o foco automático com lampejos (`PostToolUse`, `UserPromptSubmit`, `SessionStart`) depende de hooks de ferramenta e hoje roda nativamente no Claude Code. Nos outros harnesses, a Luzia acompanha tudo pelos comandos `LUZIA`.
