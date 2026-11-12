# Handoff · Luzia (trajetória, prismas, entregas e SQLite) · 12/11/2026

- Worktree de implementação: `C:\Repositorio\ai4good-sem2-banco` (branch `feature/luzia-banco`, originado de `feature/luzia-acoes` após a Tarefa 4).
- Worktree principal: `C:\Repositorio\ai4good-sem2` (branch `feature/luzia-acoes`, base `sem2`), pronto para receber o fast-forward e a migração real na Tarefa 16 após revisão final da Rayane.
- **Desenho e plano:**
  - Especificação: [docs/superpowers/specs/2026-11-12-luzia-trajetoria-prismas-design.md](../superpowers/specs/2026-11-12-luzia-trajetoria-prismas-design.md)
  - Plano em 16 tarefas: [docs/superpowers/plans/2026-11-12-luzia-trajetoria-prismas.md](../superpowers/plans/2026-11-12-luzia-trajetoria-prismas.md)
  - Regras de experiência atualizadas: [docs/luzia-ux.md](../luzia-ux.md)

## O que foi entregue (Tasks 1–15)
1. **Fundação SQLite e concorrência (`banco.py`, `migrar.py`, `arquivos.py`):**
   - `LUZIA_PRIVATE` configurável por ambiente e suíte isolada sobre dados sintéticos (`conftest.py`, nunca toca em `code/luzia/private/`).
   - Persistência única em `private/luzia.db` (SQLite WAL, `busy_timeout=5000`, transações `BEGIN IMMEDIATE`) com livros só de acréscimo (`lumen`, `avanco_evento`, `nivel_registro`, `trajetoria_versao`, `chamada_modelo`).
   - Migração idempotente e sem perda dos JSON legados (backup automático em `private/migracao-AAAAMMDD/` antes de importar).
   - Spool não-bloqueante em `pendentes.jsonl` com lock atômico no Windows para hooks nunca travarem ou perderem reconhecimentos passivos sob contenção.
2. **Motor de trajetória, prismas e avanços (`trajetoria.py`, `jogo.py`, `acoes.py`, `pedidos.py`):**
   - Versões imutáveis da trajetória (`trajetoria_versao`), prismas ativos/arquivados com palavras-chave, registros de nível separados por origem (`conquistado`, `declarado`, `migrado`, `pedido`) e progresso de nível calculado a partir do último registro.
   - Pedidos formais de mudança na trajetória (`incluir`, `mudar_meta`, `arquivar`, `reativar`) com histórico de propostas, análise fundamentada e transições `aberto → proposto → aceito / recusado` sem perda de progresso.
   - Dossiê formal em `private/dossies/` usando termos formais (`skill`, `nível`, `ação`), contabilizando apenas subidas `conquistado` e listando pedidos aceitos.
3. **Entregas reais no git e propriedade (`entregas.py`, `propriedade.py`):**
   - Detecção local via `git` nos repositórios autorizados (apenas autoria da pessoa): merges de PR (`Merged PR`, `Merge pull request`), agrupamento por ticket e commits isolados, janela inicial de 90 dias (ampliável) + leituras incrementais, com títulos mascarados pelo `Redactor`.
   - Vínculo completo entre entrega, prismas atravessados (com termos achados), avanços feitos e úteis, lúmens na janela (`±1 dia`), propriedade `P1–P4` (incluindo `p2_entrega`) e leitura assinada.
4. **Leituras fundamentadas em lote (`leituras.py`, `planner.py`):**
   - Leituras por **prisma**, **entrega** e **pedido** armazenam fatos usados (`base_json`), `base_hash` (sha256), `modelo` e `criado_em`.
   - Regeneração em lote numa chamada ao modelo apenas quando a base muda ou sob pedido explícito; transações tudo-ou-nada e degradação graciosa sem modelo (`leitura indisponível`).
5. **Paridade Chat × Painel e vocabulário novo (`cli.py`, `observer.py`, `statusline.py`, `commands/`, `skills/`, `server.py`, `painel/`):**
   - Vocabulário atualizado em todas as superfícies: **Trajetória · Prisma (skill) · Nível · Avanço · Lúmen · Luz própria/refletida · Foco · Lampejo** (aliases de compatibilidade na CLI por 1 versão).
   - Comandos novos/atualizados (`/luzia:trajetoria`, `/luzia:avancos`, `/luzia:acender`, `/luzia:entregas`, `pedido ...`, `entrega <id>`, `nivel <prisma> <N>`), todos terminando em `LUZIA_BOTOES`.
   - Painel local (`Hoje · Trajetória · Avanços · Entregas · Ajustes`) com espectro de 5 faixas nos prismas, leituras assinadas com fatos/modelo/data, filtros combináveis com contagem em **Avanços**, fluxo completo de pedidos de mudança na **Trajetória** e detalhe completo em **Entregas** — verificado no navegador em `1440×960` e `375×812`.

## Histórico resumido (versão anterior, JSON)
Antes da migração para SQLite (`sem2` / `feature/luzia-acoes` até commit `0c4ea81`), o protótipo chamava os avanços de *feixes*, os níveis de *degraus*, a trajetória de *rota* e armazenava cada entidade em arquivos JSON separados (`feixes.json`, `lumens.jsonl`, `degraus.json`, `autoavaliacao.json`, `cartoes.json`, `evidencias.jsonl`, `fila.json`, `sessao.jsonl`). Esses nomes antigos permanecem apenas em testes de migração legada (`tests/dados/`), em apelidos internos de compatibilidade na CLI/servidor e na foto congelada `outputs/sem2/`.
