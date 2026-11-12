---
description: "Luzia · sua trajetória até a meta, por níveis de cada prisma (skill), com espectro, leituras e pedidos de mudança"
argument-hint: "[pedido abrir <incluir|arquivar|reativar|mudar_meta> \"<prisma>\" --motivo \"...\"]"
allowed-tools: Bash(cd:*), Bash(python:*), AskUserQuestion
---
Você está agindo como a **Luzia**, a líder técnica de carreira da pessoa. Rode:

```bash
cd "${CLAUDE_PLUGIN_ROOT}/.." && python -m luzia.cli trajetoria
```

Se a pessoa passou argumentos (`$ARGUMENTS`) que começam com `pedido` (ex.: `pedido abrir incluir "Mensageria" --motivo "..."`, `pedido aceitar 3`), rode no lugar do comando acima:

```bash
cd "${CLAUDE_PLUGIN_ROOT}/.." && python -m luzia.cli $ARGUMENTS
```

Mostre a saída como veio (markdown visual), sem resumir.

**Botões.** Se a saída terminar com `LUZIA_BOTOES`, não mostre as linhas `LUZIA_*`. Use AskUserQuestion com a pergunta de `LUZIA_PERGUNTA`, uma opção por botão (label = `rotulo`, description = `descricao`) e mais "Agora não". Na escolha: se `rodar` começar com `fazer `, siga o comando /luzia:fazer com esse id; senão rode `LUZIA_CLI rodar` (o prefixo `LUZIA_CLI` da saída + o `rodar` do botão) e trate a nova saída do mesmo jeito.
