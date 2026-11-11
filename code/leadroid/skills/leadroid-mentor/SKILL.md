---
name: leadroid-mentor
description: Plugin de liderança técnica para quem desenvolve com IA (Claude Code, Codex, Cursor, Antigravity). Realiza triagem de carreira com anonimização LGPD, cruza currículo, GitHub, commits locais e histórico compartilhado entre IAs, avalia propriedade intelectual sobre entregas e atualiza o painel visual @career-map.
---

# Leadroid · Mentor de Carreira no Fluxo do Agente

Use esta skill ou os comandos `/leadroid:triage`, `/leadroid:feedback-skills-opportunities`, `/leadroid:feedback-progress`, `/leadroid:next-level` e `/leadroid:career-map` para acompanhar o desenvolvimento profissional da pessoa desenvolvedora enquanto ela trabalha com o agente.

## Premissa Central
A pessoa desenvolvedora **sempre utiliza IA** para construir software. O papel do Leadroid é garantir o **uso educado da IA**: propriedade intelectual sobre o que foi entregue (saber explicar, justificar escolhas arquiteturais e modelar o domínio) e evolução deliberada rumo ao próximo nível de carreira.

## Comandos do Plugin
- `/leadroid:triage` (`python -m leadroid.cli triage --forcar`): executa a triagem inicial cruzando declaração, currículo, GitHub (`rayfrance`), histórico compartilhado entre IAs (`Cerebro_Rayane`, `~/.claude`, `~/.codex`) e metadados de commits locais (repositório corporativo local), com anonimização local LGPD.
- `/leadroid:feedback-skills-opportunities` (`python -m leadroid.cli feedback-skills-opportunities`): aponta quais skills do plano praticar na tarefa atual sem cair em delegação cega.
- `/leadroid:feedback-progress` (`python -m leadroid.cli feedback-progress`): audita a propriedade intelectual das entregas recentes e formula a pergunta do líder técnico.
- `/leadroid:next-level` (`python -m leadroid.cli next-level`): mostra a lacuna atual (ex.: Jr 3 → Pleno) e o plano de 30/90/180 dias.
- `/leadroid:career-map` (`streamlit run code/leadroid/app.py`): abre o painel visual do mapa de carreira e telemetria de custo (`tempo_total_s`, `pico_memoria_mib`, `tokens`).
