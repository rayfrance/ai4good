# code/luzia — plugin Luzia

> Líder técnica de carreira dentro do agente. Regras do jogo: [docs/luzia-ux.md](../../docs/luzia-ux.md). Continuidade: [docs/handoffs/luzia-acoes.md](../../docs/handoffs/luzia-acoes.md).

## Instalar
- **Claude Code (plugin):** `claude plugin marketplace add <pasta do repositório>` e `claude plugin install luzia@ai4good`. Comandos, skills e hooks usam `${CLAUDE_PLUGIN_ROOT}`; nada de caminho fixo.
- **Sem plugin:** `python -m luzia.instalar` (comandos e skills em `~/.claude`), com `--hooks` e `--statusline` opcionais (fazem backup do `settings.json`). Não misture com o plugin.
- **Codex, Cursor, Antigravity:** `python -m luzia.instalar --regras` imprime o bloco de [harness/REGRAS.md](harness/REGRAS.md) com o caminho desta máquina.

## Peças
| arquivo | o que faz |
|:--|:--|
| `cli.py` | comandos (`hoje`, `next-level`, `fazer`, `registrar`, `subir`, `trecho`...); toda saída termina em botões (`LUZIA_BOTOES`) |
| `jogo.py` | feixes, lúmens, degraus, rota, cartões e dossiê |
| `acoes.py` | catálogo derivado do plano, fila do painel, evidências e prompt autossuficiente |
| `propriedade.py` | propriedade das entregas (P1–P4 com base visível) |
| `observer.py` | hooks `SessionStart`, `UserPromptSubmit` e `PostToolUse` (local, sem modelo) |
| `statusline.py` | linha de status do Claude Code (só nos repositórios autorizados) |
| `server.py` + `painel/` | painel local em 127.0.0.1:8501 (só aceita a própria página) |
| `planner.py`, `pipeline.py`, `modelo.py` | pedidos ao modelo configurável e medição de custo |
| `triage.py`, `privacy.py` | leitura das fontes e mascaramento LGPD local |
| `arquivos.py` | gravação atômica, estado vivo e o comando da CLI |
| `commands/`, `skills/`, `hooks/`, `.claude-plugin/` | o plugin (fonte única; o instalador copia daqui) |

## Privado (fora do git)
`private/`: entrada, estado vivo (`career_state.json`), feixes, lúmens, degraus, cartões, evidências, fila e `erros.log`. `outputs/sem2/career_state.json` é só a foto do seminário. Nomes da empresa, de clientes e de colegas nunca entram em arquivo versionado.
