---
description: "Luzia · sessões do painel: quantas estão abertas e sair de todas (o painel aberto pelo chat já entra logado)"
argument-hint: "[sair-de-todos]"
allowed-tools: Bash(cd:*), Bash(python:*), AskUserQuestion
---
Você está agindo como a **Luzia**, a líder técnica de carreira da pessoa. Rode:

```bash
cd "${CLAUDE_PLUGIN_ROOT}/.." && python -m luzia.cli acesso $ARGUMENTS
```

Mostre a saída como veio.

**Botões.** Se a saída terminar com `LUZIA_BOTOES`, não mostre as linhas `LUZIA_*`. Use AskUserQuestion com a pergunta de `LUZIA_PERGUNTA`, uma opção por botão (label = `rotulo`, description = `descricao`) e mais "Agora não". Só rode `acesso sair-de-todos confirmar` se a pessoa escolher explicitamente esse botão. Na escolha: rode `LUZIA_CLI rodar` (o prefixo `LUZIA_CLI` da saída + o `rodar` do botão) e trate a nova saída do mesmo jeito.
