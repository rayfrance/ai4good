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
| `pedidos.py` | fluxo formal de pedidos de mudança na trajetória (`abrir`, `propor`, `aceitar`, `recusar`, `listar`, `dividir_todos`); tipos incluir, arquivar, reativar, mudar meta e dividir |
| `prismas.py` | um prisma = uma habilidade: divisão determinística de nomes compostos (mapa revisável + regra genérica), palavras de cada habilidade e classificação dos avanços, sem modelo |
| `entregas.py` | detecção local via `git` (PR merges, tickets, commits), prismas atravessados, ligação com lúmens/avanços e detalhe completo |
| `leituras.py` | geração em lote e cache de leituras assinadas por IA com base determinística, hash, modelo e data (prisma, entrega e pedido) |
| `cli.py` | comandos (`hoje`, `trajetoria`, `pedido`, `dividir`, `dividir-todos`, `avancos`, `acender`, `entregas`, `entrega`, `acender-entrega`, `identidade`, `leituras`, `foco`, `modelo usar`, `agente`, `nivel`, `fazer`, `registrar`, `subir`, `dossie`, `acesso`, `privacidade`...); toda saída termina em `LUZIA_BOTOES` |
| `jogo.py` | avanços, lúmens, níveis, lampejos, tetos diários, ritmo e dossiê formal de evidências |
| `acoes.py` | catálogo de avanços derivado do plano, fila do painel, evidências P3/P4 e prompt autossuficiente |
| `propriedade.py` | propriedade intelectual das entregas (P1–P4 e `p2_entrega` sobre a entrega consolidada) |
| `observer.py` | foco e hooks `SessionStart`, `UserPromptSubmit` e `PostToolUse` (local, sem modelo) com envio de lampejos; `reconhecer_em` é a única implementação do reconhecimento, usada também pelo comando `foco` da CLI (agentes sem hooks) |
| `statusline.py` | linha de status do Claude Code com estado do foco e prisma mais próximo (só nos repositórios autorizados) |
| `server.py` + `painel/` | painel local em `127.0.0.1:8501` (**Hoje · Trajetória · Avanços · Entregas · Ajustes**), espectro de 5 faixas, proteção Host/Origin/JSON e login: toda rota `/api` fora `ping` e `acesso/*` exige sessão (401) |
| `acesso.py` | entrada no painel herdada do agente: `career-map` grava um link de uso único (2 min, só o SHA-256 em `acesso_link`) e abre `#entrar=<token>`; a página troca o link por uma sessão de 30 dias sem uso (só o SHA-256 em `acesso_sessao`, sobrevive a reinícios; o polling manda `X-Luzia-Auto: 1` e não renova); 10 links errados por minuto dão 429; `acesso sair-de-todos` encerra todas |
| `planner.py`, `pipeline.py`, `modelo.py` | esquemas JSON estruturados, chamadas ao modelo configurável e registro de custo em `runs.jsonl` e `chamada_modelo` |
| `triage.py`, `privacy.py` | leitura das fontes locais e mascaramento LGPD (`Redactor`, `mascarar_estrutura`), usado só no envio ao modelo com o interruptor `mascarar_modelo` ligado (`pipeline.run_plan`) |
| `arquivos.py` | leitura/escrita atômica para arquivos de configuração (`observer.json`, `entrada.json`, etc.), `LUZIA_PRIVATE` e registro seguro de erros |
| `commands/`, `skills/`, `hooks/`, `.claude-plugin/`, `.*-plugin/` | plugin multi-harness (fonte única em `code/luzia`; o instalador resolve `${CLAUDE_PLUGIN_ROOT}` quando usado fora do sistema de plugins) |

## Limites conhecidos do login
- O painel só atende em `http://127.0.0.1:8501` (nunca `localhost`, que pode resolver para `::1`, onde outro processo poderia escutar a mesma porta), com a porta exclusiva (sem `SO_REUSEADDR`; `SO_EXCLUSIVEADDRUSE` no Windows). Ao subir, ele grava um segredo novo e o PID em `private/painel.json`; antes de gerar o link, o `career-map` manda um desafio a `/api/ping?desafio=` e só segue se a resposta for o HMAC certo. Sem a prova (outro programa na porta, ou um painel antigo que não sabe se identificar), não sai link nenhum. O segredo vale o que vale a pasta `private/`: quem lê essa pasta já lê o banco.
- Painel rodando com código de antes de uma atualização (versão ou esquema diferentes no ping autenticado) é encerrado pelo PID que ele mesmo informou e ligado de novo. Um painel de antes desta identificação não sabe responder ao desafio: feche-o uma vez (ou reinicie o computador).
- O cookie `luzia_sessao` é de `127.0.0.1`, e navegadores não separam cookies por porta: qualquer outro servidor local aberto no mesmo navegador recebe o cookie. Ele é `HttpOnly` e `SameSite=Strict` (sites de fora não o usam), mas um programa local malicioso em outra porta poderia lê-lo; quem tem esse acesso à máquina já lê `private/`.
- Entra quem tem acesso ao usuário do Windows da pessoa e ao agente dela (é quem consegue rodar `career-map`). Não há senha: a proteção é a mesma do resto de `private/`.
- Se o navegador não abrir (agente remoto, SSH ou POSIX sem tela), o link aparece uma vez no chat: vale 2 minutos e uma vez só. Quem vir o chat nesse intervalo pode usá-lo.
- A sessão fica 30 dias num navegador sem uso; num computador compartilhado, use **Sair** no painel ou `acesso sair-de-todos` no chat.

## Privado (fora do git)
`private/` (ou `LUZIA_PRIVATE` em testes): `luzia.db` (fonte única do estado do jogo), `pendentes.jsonl` (spool temporário sob contenção), `migracao-AAAAMMDD/` (backups dos JSON legados), `entrada.json`, `observer.json`, `modelo.json`, `painel.json` (segredo e PID do painel em execução), `termos.txt` e `erros.log`. `outputs/sem2/career_state.json` é apenas a foto histórica do seminário. Nomes da empresa, produtos internos, clientes, colegas, e-mails e números de PR/ticket nunca entram em arquivo versionado; na tela, aparecem só para quem abriu o painel pelo próprio agente (e no chat da própria pessoa). Sessões e links do painel ficam no `luzia.db`, só como SHA-256. Hashes de commit ficam só no banco. O envio ao modelo vai real por padrão e mascarado com `mascarar_modelo` ligado (`perfil('privacidade')`).
