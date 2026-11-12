---
name: luzia-observador
description: Como responder aos avisos automáticos da Luzia ([Luzia · luz refletida], [Luzia · luz própria], [Luzia · fila], [Luzia · início]) que os hooks do plugin colocam no contexto do Claude Code.
---

# Luzia · observador de sessão

Os hooks do plugin rodam `observer.py` localmente, sem chamar modelo, só nos repositórios autorizados (`private/observer.json`). Guardam só o evento mascarado (horário, skill, extensão), nunca caminho, código ou texto de prompt.

- **[Luzia · luz refletida]** (depois de uma edição ou commit): o agente aplicou um conceito de uma skill com lacuna (+10 lm de luz refletida). Termine a tarefa e mostre o cartão de 3 linhas pedido no aviso; ofereça "Responder agora" e "Guardar para depois". A resposta da pessoa, avaliada pela rubrica, converte em luz própria (até +30 lm, uma vez por cartão).
- **[Luzia · luz própria]**: a pessoa dirigiu o conceito no prompt (+20 lm). Uma linha no fim, só isso.
- **[Luzia · fila]**: a pessoa mandou um feixe do painel. Responda ao que ela pediu e, no fim, ofereça "Abrir em sessão nova", "Fazer aqui" e "Depois".
- **[Luzia · início]**: há algo a retomar (feixe em andamento, degrau pronto, fila). Uma linha no fim da primeira resposta, sugerindo `/luzia:hoje`.

Modos (painel > Ajustes, ou `cd "${CLAUDE_PLUGIN_ROOT}/.." && python -m luzia.cli modo <modo>`): `ativo` (cartões no chat), `passivo` (só soma lúmens), `sob_demanda` (não observa). Limites: um reconhecimento por skill por sessão e 40 lm passivos por skill por dia. Nunca interrompa a tarefa nem cite nomes da empresa, de clientes ou de colegas.
