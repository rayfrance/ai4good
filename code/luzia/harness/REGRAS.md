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
  - "Não achou minhas entregas / meu nome no git é outro": `LUZIA identidade` e `LUZIA identidade adicionar "<nome ou e-mail>"`
  - "Acender avanços para provar a propriedade de uma entrega": `LUZIA acender-entrega <id>` (2 avanços: P3 e P4)
  - "Atualizar as leituras vencidas (cada leitura mostra base, modelo e data)": `LUZIA leituras`
  - "Trocar o modelo / o agente": `LUZIA modelo usar <provedor> <modelo>` (a chave nunca pelo chat: painel ou `.env`) e `LUZIA agente <nome>`
  - "Sair do painel em todos os navegadores": `LUZIA acesso` (só rode `LUZIA acesso sair-de-todos confirmar` depois do sim explícito da pessoa)
  - "Mascarar (ou não) o que vai para o modelo": `LUZIA privacidade mascarar-modelo on|off` (padrão: desligado)
  - "Declarar nível de partida (0–5)": `LUZIA nivel "<prisma>" <0-5>`
  - "Plano em horizontes / próximo nível": `LUZIA next-level` · Dossiê formal: `LUZIA dossie`
- Toda saída pode terminar com `LUZIA_CLI`, `LUZIA_PERGUNTA` e `LUZIA_BOTOES` (JSON com `rotulo`, `descricao`, `rodar`). Não mostre essas linhas brutas: apresente as opções ao usuário (ou lista numerada) e, após a escolha, rode `LUZIA <rodar>`.
- Avanço (`rodar` = `fazer <id>`): se este harness abre agente/sessão nova com um prompt, ofereça isso com o texto de `LUZIA prompt <id>`; senão rode `LUZIA fazer <id>` e siga o `ROTEIRO PARA O AGENTE`: uma pergunta por vez, não faça o trabalho no lugar da pessoa, avalie pela rubrica 0–4 e rode o `registrar` que ele indica (o resumo fica só no banco privado e no dossiê local da pessoa).
- **Foco sem hooks (reconhecimento passivo).** Este harness não tem hooks, então você mesma chama o foco:
  - Depois de **editar arquivos**: `LUZIA foco --arquivos <caminhos editados> --cwd "<pasta do projeto>"`. A Luzia lê só o `git diff` desses caminhos e não guarda código.
  - No **começo de um pedido** da pessoa que cite um conceito: grave o texto do pedido num arquivo temporário e rode `LUZIA foco --prompt-arquivo <arquivo> --cwd "<pasta do projeto>"`; apague o arquivo em seguida. O texto não é guardado.
  - Opcional: `--sessao <id>` (sem ele, vale um id por pasta e por dia).
  - Regras (as mesmas do hook): +10 lm de luz refletida quando você aplicou o conceito, +20 lm de luz própria quando a pessoa o dirigiu no pedido, uma vez por prisma por sessão, teto de 40 lm por prisma por dia, lampejo só em "em foco, com lampejos". Se a saída trouxer um lampejo, mostre no fim da resposta e ofereça os botões "Responder agora" e "Guardar para depois". Se não trouxer nada novo, não comente.
- Nível pronto: só rode `LUZIA subir "<prisma>"` com o **sim explícito** da pessoa.
- Painel local: `LUZIA career-map` (`http://127.0.0.1:8501`). Aberto por esse comando, o painel já entra com a sessão da pessoa (link de uso único no navegador, sessão de 30 dias); aberto direto no navegador sem sessão, ele pede para abrir pelo agente. Se a saída trouxer um link porque o navegador não abriu, mostre-o uma vez como veio (vale 2 minutos, uma vez só). Os dados reais (empresa, colegas, tickets) aparecem para ela no painel e no chat, mas nunca em arquivo versionado.
```

Os hooks (`PostToolUse`, `UserPromptSubmit`, `SessionStart`) rodam nativamente só no Claude Code. Nos outros harnesses, o comando `LUZIA foco` (acima) dá o mesmo reconhecimento passivo, e o resto da Luzia vem dos comandos `LUZIA`.
