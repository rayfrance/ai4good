---
name: luzia-observador
description: "Como responder aos avisos automáticos da Luzia ([Luzia · luz refletida], [Luzia · luz própria], [Luzia · fila], [Luzia · início]) que os hooks do plugin colocam no contexto do Claude Code."
---

# Luzia · observador de sessão

Os hooks do plugin rodam `observer.py` localmente, sem chamar modelo, só nos repositórios autorizados (`private/observer.json`). Guardam só o evento mascarado (horário, prisma, extensão), nunca caminho, código ou texto de prompt.

- **[Luzia · luz refletida]** (depois de uma edição ou commit): o agente aplicou um conceito de um prisma com lacuna (+10 lm de luz refletida). Termine a tarefa e mostre a centelha da sessão de 3 linhas (`✦ Centelha da sessão · <nome curto> · +10 lm refletida`) pedida no aviso; ofereça "Responder agora" e "Guardar". A resposta da pessoa, avaliada pela rubrica, converte em luz própria (até +30 lm, uma vez por centelha); "Guardar" a transforma numa centelha guardada.
- **[Luzia · luz própria]**: a pessoa dirigiu o conceito no prompt (+20 lm). Uma linha no fim, só isso.
- **[Luzia · fila]**: a pessoa mandou uma centelha do painel. Responda ao que ela pediu e, no fim, ofereça "Abrir em sessão nova", "Fazer aqui" e "Depois".
- **[Luzia · início]**: há algo a retomar (centelha em andamento, nível pronto, fila). Uma linha no fim da primeira resposta, sugerindo `/luzia:hoje`.

Foco da Luzia (painel > Ajustes, ou `cd "${CLAUDE_PLUGIN_ROOT}/.." && python -m luzia.cli modo <modo>`):
- `ativo` (**Em foco**): observa e mostra centelhas da sessão no chat.
- `passivo` (**em foco, em silêncio**): só soma lúmens no banco sem interromper.
- `sob_demanda` (**fora de foco**): não observa; responde só quando chamada.
Limites: um reconhecimento por prisma por sessão e 40 lm passivos por prisma por dia. Nunca interrompa a tarefa.
