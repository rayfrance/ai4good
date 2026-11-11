---
name: leadroid-session-observer
description: Observador ativo de sessão do Leadroid no harness do agente (Claude Code, Cursor, Codex, Antigravity). Monitora a tarefa em andamento, reconhece quando conceitos do plano de carreira (DDD, Clean Architecture, testes, redução de débito técnico) aparecem na atividade e intervém de forma configurável para preservar a propriedade intelectual.
---

# Leadroid · Observador de Sessão e Intervenção no Fluxo

Esta skill atua continuamente enquanto a pessoa desenvolve no repositório com o agente, respeitando a configuração de intervenção em `outputs/sem2/career_state.json` (`preferencias_intervencao`).

## Como o Observador atua durante uma tarefa

1. **Detecção de oportunidade conceitual no código em construção:**
   - Ao ler ou editar arquivos na tarefa atual, cruza o contexto do código com as **lacunas ativas do plano de carreira** (`@next-level`: 90 dias, 6 meses, 12 meses).
   - Quando identifica um conceito que a pessoa precisa praticar (ex.: fronteira entre subdomínio principal, de suporte e genérico em DDD; desacoplamento de serviço externo; prevenção de débito técnico em legado), emite um aviso curto no fluxo:
     > *"🧭 **Leadroid · Oportunidade na Sessão:** Esta atividade toca diretamente em `[conceito/skill do seu plano]`. Antes de delegar a implementação completa, veja como a teoria se aplica aqui: `[conexão rápida com o código atual]`."*
2. **Defesa do plano de carreira e redução de débito técnico:**
   - Lembra a pessoa dos compromissos do marco atual (90 dias / 6 meses / 12 meses) quando percebe uma entrega que pode gerar débito técnico ou delegação cega.
3. **Respeito à preferência da pessoa usuária:**
   - Se `intervencao_ativa = false` ou se o modo silencioso estiver ativado para a sessão, registra a oportunidade apenas no painel `@career-map` sem interromper o chat.
