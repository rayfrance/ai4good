# code/luzia — plugin Luzia

> Líder técnica de carreira dentro do agente. Regras do jogo e da trajetória: [docs/luzia-ux.md](../../docs/luzia-ux.md). Continuidade: [docs/handoffs/luzia-acoes.md](../../docs/handoffs/luzia-acoes.md).

## Instalar
- **Claude Code (plugin):** `claude plugin marketplace add <pasta do repositório>` e `claude plugin install luzia@ai4good`. Comandos, skills e hooks usam `${CLAUDE_PLUGIN_ROOT}`; nada de caminho fixo.
- **Sem plugin:** `python -m luzia.instalar` (comandos e skills em `~/.claude`), com `--hooks` e `--statusline` opcionais (fazem backup do `settings.json`). Não misture com o plugin.
- **Codex, Cursor, Antigravity:** `python -m luzia.instalar --regras` imprime o bloco de [harness/REGRAS.md](harness/REGRAS.md) com o caminho desta máquina.

## Peças
| arquivo | o que faz |
|:--|:--|
| `banco.py` | persistência local em SQLite (`private/luzia.db`, WAL, `BEGIN IMMEDIATE`), esquema versionado e fila de fallback `pendentes.jsonl` para hooks nunca travarem |
| `migrar.py` | migração idempotente e sem perda dos JSON antigos para o SQLite (mantendo backup em `private/migracao-AAAAMMDD/`) |
| `trajetoria.py` | perfil, prismas (skills), palavras-chave, registros de nível e histórico imutável de versões da trajetória |
| `pedidos.py` | fluxo formal de pedidos de mudança na trajetória (`abrir`, `propor`, `aceitar`, `recusar`, `listar`) |
| `entregas.py` | detecção local via `git` (PR merges, tickets, commits), prismas atravessados, ligação com lúmens/avanços e detalhe completo |
| `leituras.py` | geração em lote e cache de leituras assinadas por IA com base determinística, hash, modelo e data (prisma, entrega e pedido) |
| `cli.py` | comandos (`hoje`, `trajetoria`, `pedido`, `avancos`, `acender`, `entregas`, `entrega`, `acender-entrega`, `identidade`, `leituras`, `foco`, `modelo usar`, `agente`, `nivel`, `fazer`, `registrar`, `subir`, `dossie`...); toda saída termina em `LUZIA_BOTOES` |
| `jogo.py` | avanços, lúmens, níveis, lampejos, tetos diários, ritmo e dossiê formal de evidências |
| `acoes.py` | catálogo de avanços derivado do plano, fila do painel, evidências P3/P4 e prompt autossuficiente |
| `propriedade.py` | propriedade intelectual das entregas (P1–P4 e `p2_entrega` sobre a entrega consolidada) |
| `observer.py` | foco e hooks `SessionStart`, `UserPromptSubmit` e `PostToolUse` (local, sem modelo) com envio de lampejos; `reconhecer_em` é a única implementação do reconhecimento, usada também pelo comando `foco` da CLI (agentes sem hooks) |
| `statusline.py` | linha de status do Claude Code com estado do foco e prisma mais próximo (só nos repositórios autorizados) |
| `server.py` + `painel/` | painel local em `127.0.0.1:8501` (**Hoje · Trajetória · Avanços · Entregas · Ajustes**), espectro de 5 faixas e proteção Host/Origin/JSON |
| `planner.py`, `pipeline.py`, `modelo.py` | esquemas JSON estruturados, chamadas ao modelo configurável e registro de custo em `runs.jsonl` e `chamada_modelo` |
| `triage.py`, `privacy.py` | leitura das fontes locais e mascaramento LGPD (`Redactor`) |
| `arquivos.py` | leitura/escrita atômica para arquivos de configuração (`observer.json`, `entrada.json`, etc.), `LUZIA_PRIVATE` e registro seguro de erros |
| `commands/`, `skills/`, `hooks/`, `.claude-plugin/`, `.*-plugin/` | plugin multi-harness (fonte única em `code/luzia`; o instalador resolve `${CLAUDE_PLUGIN_ROOT}` quando usado fora do sistema de plugins) |

## Privado (fora do git)
`private/` (ou `LUZIA_PRIVATE` em testes): `luzia.db` (fonte única do estado do jogo), `pendentes.jsonl` (spool temporário sob contenção), `migracao-AAAAMMDD/` (backups dos JSON legados), `entrada.json`, `observer.json`, `modelo.json`, `termos.txt` e `erros.log`. `outputs/sem2/career_state.json` é apenas a foto histórica do seminário. Nomes da empresa, produtos internos, clientes, colegas, e-mails, números privados de PR/ticket e hashes nunca entram em arquivo versionado ou na tela.
