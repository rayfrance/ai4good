# Luzia · trajetória, prismas e persistência · plano de implementação

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** levar todo o estado da Luzia para um banco SQLite local, com entregas medidas a partir do git, leituras de IA sempre com base, pedido formal de mudança da trajetória, filtros de avanços e o vocabulário novo (trajetória, prisma, nível, avanço, lúmen, foco, lampejo), com paridade chat × painel.

**Architecture:** uma camada única `banco.py` (SQLite em WAL, transações `BEGIN IMMEDIATE`) guarda tudo; `jogo.py` mantém a API pública atual mas passa a ler e gravar no banco; módulos novos `entregas.py`, `leituras.py` e `pedidos.py` ficam sobre o banco; `cli.py`, `server.py`, o painel, o observador e a linha de status só falam com esses módulos.

**Tech Stack:** Python 3.14 (biblioteca padrão: `sqlite3`, `subprocess`, `json`, `hashlib`), pytest 9, git local, painel em HTML/CSS/JS sem dependências, modelo configurável por `modelo.py` (hoje Gemini `gemini-3.5-flash-lite`).

**Spec:** `docs/superpowers/specs/2026-11-12-luzia-trajetoria-prismas-design.md` (ler inteiro antes de cada tarefa; a seção 11 traz decisões que os testes precisam respeitar).

## Global Constraints
- Worktree `C:\Repositorio\ai4good-sem2`, branch `feature/luzia-acoes`. Commits por tarefa, em inglês, Conventional Commits, terminando com `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`. **Sem push.**
- Nada de dependência nova. Persistência só com `sqlite3`.
- Testes **nunca** leem nem escrevem `code/luzia/private/`. Toda tarefa usa a fixture `privado` (Tarefa 1), que aponta `LUZIA_PRIVATE` para uma pasta temporária com dados sintéticos.
- LGPD: nomes da empresa, de produto interno, clientes, colegas, e-mails, números de PR/ticket e hashes nunca em arquivo versionado nem na tela. Hashes e ids de PR/ticket só no banco privado.
- Regras de jogo (valores exatos): valor do avanço = esforço (5–30) + 15 × níveis que faltam + prioridade (+10 nas duas maiores lacunas, +5 nas outras, 0 na meta), limitado a 10–100 lm; rubrica 4/3/2 = 100/75/50%, 0–1 tente de novo (avanço segue aberto); uma revisita, só a diferença, só depois de aberta; registrar exige avanço `em_andamento` (ou revisita aberta); passivos: refletida +10, prompt +20, conversão de lampejo até +30 (×rubrica) uma vez por lampejo, lampejo vale 24 h; teto de 40 lm passivos por prisma por dia; um reconhecimento por prisma por sessão; subir de nível: 150 lm desde o último registro de nível, ≥ 40% de luz própria, ≥ 1 avanço conquistado, e só com o sim da pessoa.
- Estados internos dos avanços continuam `sugerido`, `na_fila`, `em_andamento`, `conquistado`, `descartado`; motivos de descarte `nao_faz_sentido`, `ja_domino`, `agora_nao`. Modos internos continuam `ativo`, `passivo`, `sob_demanda` (só os nomes exibidos mudam).
- Vocabulário exibido (seção 2 do spec): trajetória, "Prisma <nome>", nível, avanço, lúmen (lm), luz própria/refletida, propriedade (P1–P4), foco ("em foco, com lampejos" / "em foco, em silêncio" / "fora de foco"), lampejo. Dossiê usa skill, nível e ação.
- Toda leitura de IA exibida traz texto + "com base em" + modelo + data; sem modelo, sem chave ou sem internet: só fatos e "leitura indisponível".
- Toda saída da CLI termina com `LUZIA_CLI`, `LUZIA_PERGUNTA`, `LUZIA_BOTOES` (protocolo atual de `cli.botoes`).
- Plugin precisa continuar passando em `claude plugin validate code/luzia` e `claude plugin validate .`.

## Review Focus
1. **Duas escritas ao mesmo tempo** (hook + painel + CLI): nenhum lúmen ou evento pode sumir → teste com 4 processos na Tarefa 2 e teste de banco travado na Tarefa 4.
2. **Migração rodada duas vezes ou interrompida no meio**: não duplica nem perde → testes de idempotência e de rollback na Tarefa 3.
3. **Repositório sem merges (squash) ou com commits de outras pessoas**: entregas não podem misturar autores nem sumir → testes na Tarefa 8.
4. **Pedido de mudança que arquiva um prisma com lúmens**: lúmens continuam no total e nas entregas; reativar devolve tudo → teste na Tarefa 11.
5. **Modelo fora do ar no meio de uma leitura em lote**: nada de leitura parcial gravada; a tela mostra só fatos → teste na Tarefa 10.

## Quem implementa (spec 12a)
| tarefas | modelo | portão |
|:--|:--|:--|
| 1–4 (banco, migração, pendentes) | Opus 5.5 | revisão Opus |
| 5–7 (motor do jogo no banco) | Sonnet 5.5 | revisão Opus |
| 8–9 (entregas) | Sonnet 5.5 | revisão Opus |
| 10–11 (leituras, pedidos) | Opus 5.5 | revisão Opus |
| 12–13 (CLI, comandos, foco, servidor) | Sonnet 5.5 | revisão Opus |
| 14 (painel) | Sonnet 5.5 | revisão Opus + conferência no navegador |
| 15 (docs e varredura) | Haiku 5.5 | revisão Opus |
| 16 (verificação final) | Opus 5.5 (sessão principal) | — |

Rodar a suíte inteira: `cd C:/Repositorio/ai4good-sem2/code && python -m pytest luzia/tests -q`.

---

### Task 1: Pasta privada configurável e base de testes

**Files:**
- Modify: `code/luzia/arquivos.py` (constantes `PRIVATE`, `ERROS`, `ESTADO`)
- Modify: `code/luzia/jogo.py`, `acoes.py`, `observer.py`, `pipeline.py`, `statusline.py` (derivar caminhos de `arquivos.PRIVATE` em vez de recalcular)
- Create: `code/luzia/tests/__init__.py`, `code/luzia/tests/conftest.py`, `code/luzia/tests/test_arquivos.py`

**Interfaces:**
- Produces: `arquivos.PRIVATE: Path` = `Path(os.environ['LUZIA_PRIVATE'])` se definida, senão `code/luzia/private`; fixture pytest `privado(tmp_path, monkeypatch) -> Path` que define `LUZIA_PRIVATE`, recarrega os módulos `luzia.*` que guardam caminhos e escreve dados sintéticos: `entrada.json` (`repo`, `author`, `horizonte: "12 meses"`), `observer.json` (`modo: "ativo"`, `autorizados: [<tmp>/repo]`), `career_state.json` com 3 skills (`"Domain-Driven Design (DDD)"` nível 1 meta 4, `"Testes e Qualidade / SQL"` 2→4, `"Front-end (JS / Razor / React)"` 3→4), 1 trecho de plano com 3 ações, 2 `tarefas_recentes` e `p1_direcao_prompt {nota: 65}`.

- [ ] **Step 1: Teste** `test_private_vem_do_ambiente`: com `LUZIA_PRIVATE=<tmp>`, `arquivos.PRIVATE == Path(<tmp>)` e `jogo.FEIXES.parent == Path(<tmp>)`.
- [ ] **Step 2:** `python -m pytest luzia/tests/test_arquivos.py -q` → FAIL.
- [ ] **Step 3:** Implementar a leitura do ambiente e a fixture; mover os testes do scratchpad (`teste_lote1.py`, `teste_lote23.py`, ver `docs/handoffs/luzia-acoes.md`) para `tests/test_regras_atuais.py` usando a fixture (eles viram a rede de segurança das tarefas 5–7).
- [ ] **Step 4:** suíte inteira → PASS (as 39 verificações atuais como testes pytest).
- [ ] **Step 5:** commit `test(luzia): configurable private dir and pytest suite for current rules`.

### Task 2: Banco SQLite e esquema

**Files:**
- Create: `code/luzia/banco.py`, `code/luzia/tests/test_banco.py`

**Interfaces:**
- Produces:
  - `banco.ESQUEMA_VERSAO = 1`; `banco.caminho() -> Path` (`arquivos.PRIVATE / 'luzia.db'`).
  - `banco.conectar() -> sqlite3.Connection`: `row_factory=sqlite3.Row`, `PRAGMA journal_mode=WAL`, `busy_timeout=5000`, `foreign_keys=ON`; chama `garantir(con)`.
  - `banco.transacao(con)`: context manager com `BEGIN IMMEDIATE`, commit ou rollback.
  - `banco.garantir(con) -> None`: cria o esquema se faltar e grava `meta('esquema', '1')`; chama `migrar.migrar(con)` (Tarefa 3) uma única vez, dentro de `BEGIN EXCLUSIVE`, marcando `meta('migrado_em', ...)`.
  - Tabelas e colunas que outras tarefas usam (demais colunas livres):
    `meta(chave PK, valor)`; `perfil(chave PK, valor_json)`;
    `prisma(nome PK, palavras_json, nivel, meta, estado 'ativo'|'arquivado', origem 'triagem'|'pedido', ultimo_nivel_em, criado_em)`;
    `trajetoria_versao(numero PK, criada_em, origem, pedido_id, foto_json)`;
    `pedido(id PK, tipo 'incluir'|'arquivar'|'reativar'|'mudar_meta', prisma, motivo, proposta_json, leitura_id, estado 'aberto'|'proposto'|'aceito'|'recusado', criado_em, decidido_em)`;
    `avanco(id PK TEXT, prisma, tipo, titulo, conteudo_json, duracao_min, valor_lm, conta_json, origem, entrega_id, dimensao, estado, nota, lm_ganho, tentativas, revisitas, revisita_aberta, criado_em)`;
    `avanco_evento(id PK, avanco_id, quando, evento, onde, nota, resumo, motivo)`;
    `lumen(id PK, quando, prisma, lm, luz 'propria'|'refletida', fonte, ref)`;
    `nivel_registro(id PK, prisma, de, para, quando, origem 'conquistado'|'declarado'|'migrado'|'pedido', lm, luz_propria)`;
    `lampejo(id PK, prisma, sessao, quando, estado 'aberto'|'convertido'|'guardado', usado_em)`;
    `entrega(id PK, chave UNIQUE, titulo, inicio, fim, commits, arquivos, linhas, areas_json, ids_privados_json, fonte)`;
    `commit_(hash PK, entrega_id, data, mensagem, arquivos, linhas, areas_json)`;
    `entrega_prisma(entrega_id, prisma, termos_json, PK(entrega_id, prisma))`;
    `leitura(id PK, alvo_tipo 'prisma'|'entrega'|'pedido', alvo_id, texto, base_json, base_hash, modelo, criado_em)`;
    `fila(avanco_id PK, titulo, quando, oferecida_json)`;
    `sessao_evento(id PK, quando, sessao, prisma, extensao, ferramenta, modo, lm, luz, interveio)`;
    `chamada_modelo(id PK, quando, rotulo, modelo, segundos, tokens_in, tokens_out, registro_json)`.
  - Tabelas `lumen`, `avanco_evento`, `nivel_registro`, `trajetoria_versao`, `chamada_modelo` são **só de acréscimo** (nenhum `UPDATE`/`DELETE` no código; um teste procura essas palavras nas consultas de `banco.py`/`jogo.py` contra essas tabelas).

- [ ] **Step 1: Testes** `test_esquema_criado` (todas as tabelas acima existem, `meta.esquema == '1'`), `test_wal_e_timeout` (`journal_mode == 'wal'`, `busy_timeout == 5000`), `test_escrita_concorrente` (4 processos `multiprocessing` gravam 200 linhas cada em `lumen` → 800 linhas, nenhuma exceção), `test_livros_sem_update`.
- [ ] **Step 2:** rodar → FAIL. **Step 3:** implementar. **Step 4:** rodar → PASS.
- [ ] **Step 5:** commit `feat(luzia): sqlite store with WAL, transactions and schema v1`.

### Task 3: Migração dos JSON para o banco

**Files:**
- Create: `code/luzia/migrar.py`, `code/luzia/tests/test_migrar.py`, `code/luzia/tests/dados/` (JSON sintéticos no formato atual de `feixes.json`, `lumens.jsonl`, `degraus.json`, `autoavaliacao.json`, `cartoes.json`, `evidencias.jsonl`, `fila.json`, `acoes_guardadas.json`, `sessao.jsonl`, `career_state.json`)

**Interfaces:**
- Consumes: `banco.transacao`.
- Produces: `migrar.migrar(con) -> dict` (contagens por tabela); `migrar.totais_json(pasta: Path) -> dict` e `migrar.totais_banco(con) -> dict` com as chaves `lumens_total`, `lumens_propria`, `avancos_por_estado`, `niveis`.

Mapeamento: `career_state.json` → `perfil` (plano inteiro em `perfil('plano')`, rótulos em `perfil('rotulos')`) + `prisma` (nível de `autoavaliacao.json` ou do plano, meta = `alvo`, palavras = `palavras_chave` + `observer.PALAVRAS_PADRAO`) + `trajetoria_versao` nº 1 (origem `triagem`); `feixes.json` → `avanco` (+ `historico` → `avanco_evento`); `lumens.jsonl` → `lumen`; `degraus.json` → `nivel_registro` (cada item do histórico com origem `conquistado`; a base declarada vira 1 registro `migrado`); `cartoes.json` → `lampejo`; `fila.json` → `fila`; `sessao.jsonl` → `sessao_evento`; `acoes_guardadas.json` → `avanco` (origem `lampejo`). Originais copiados para `PRIVATE/migracao-AAAAMMDD/` antes; nada é apagado.

- [ ] **Step 1: Testes** `test_totais_iguais` (`totais_json == totais_banco` com os dados sintéticos), `test_idempotente` (chamar duas vezes → mesmas contagens), `test_rollback` (exceção forçada no meio → banco sem nenhuma linha migrada e sem `meta.migrado_em`), `test_backup_criado`.
- [ ] **Step 2–4:** FAIL → implementar → PASS.
- [ ] **Step 5:** commit `feat(luzia): one-time lossless migration from json files`.

### Task 4: Escrita segura do observador (pendentes)

**Files:**
- Modify: `code/luzia/banco.py`; Create: `code/luzia/tests/test_pendentes.py`

**Interfaces:**
- Produces: `banco.gravar_ou_pendurar(operacao: str, dados: dict) -> bool` (tenta gravar com `busy_timeout` curto de 1500 ms; se `sqlite3.OperationalError` de bloqueio, acrescenta `{"operacao","dados","quando"}` em `PRIVATE/pendentes.jsonl` e devolve `False`); `banco.absorver_pendentes(con) -> int` (chamado no início de toda `transacao`; aplica e esvazia o arquivo). Operações suportadas: `'lumen'`, `'sessao_evento'`, `'lampejo'`.

- [ ] **Step 1: Testes** `test_travado_vai_para_pendentes` (outra conexão segura `BEGIN EXCLUSIVE`; `gravar_ou_pendurar('lumen', …)` → `False` em < 2 s e uma linha em `pendentes.jsonl`), `test_absorve_na_proxima_escrita` (solta o bloqueio, abre `transacao` → a linha está em `lumen` e o arquivo ficou vazio).
- [ ] **Step 2–5:** FAIL → implementar → PASS → commit `feat(luzia): hook writes never block or get lost`.

**Portão 1 (Opus):** revisão de concorrência, migração e LGPD antes da Tarefa 5.

### Task 5: Prismas, perfil e trajetória no banco

**Files:**
- Create: `code/luzia/trajetoria.py`, `code/luzia/tests/test_trajetoria.py`
- Modify: `code/luzia/jogo.py` (`niveis`, `skill_de`, `garantir_base`, `rota`), `code/luzia/pipeline.py` (`load_state`, `save_state`, `update_state`, `rotulos` passam a usar `perfil`)

**Interfaces:**
- Produces:
  - `trajetoria.prismas(con, incluir_arquivados=False) -> list[dict]` (chaves `nome, nivel, meta, estado, palavras, origem`).
  - `trajetoria.declarar_nivel(con, nome: str, nivel: int) -> None` (grava `nivel_registro` origem `declarado`).
  - `trajetoria.nova_versao(con, origem: str, pedido_id: int | None) -> int` (foto dos prismas ativos e metas).
  - `trajetoria.resumo(con) -> dict` com `niveis_total = Σ(meta − nivel_base)` e `niveis_feitos` só de prismas ativos, `lm_total` e `luz_propria` de **todos** os lúmens, `pct`, `marcos` (terços).
  - `pipeline.log_run(record)` grava também em `chamada_modelo` (e continua acrescentando em `outputs/sem2/runs.jsonl`, que não tem dado pessoal).
  - `jogo.niveis(plan)` e `jogo.rota(plan)` mantêm as mesmas chaves de hoje (`degraus_total`/`degraus_feitos` passam a ser `niveis_total`/`niveis_feitos`, com os nomes antigos como apelidos até a Tarefa 12).
- [ ] **Step 1: Testes** `test_declarar_nivel_registra_origem`, `test_arquivado_fora_da_trajetoria_mas_lumens_contam`, `test_nova_versao_guarda_foto`, `test_rota_compat` (as chaves de `jogo.rota` usadas por `cli.py` e `server.py` existem).
- [ ] **Step 2–5:** FAIL → implementar → PASS → commit `feat(luzia): prisms, profile and trajectory versions on sqlite`.

### Task 6: Avanços no banco

**Files:**
- Modify: `code/luzia/jogo.py` (`sincronizar`, `catalogo`, `_mudar`, `enfileirar`, `iniciar`, `descartar`, `restaurar`, `pode_revisitar`, `motivos_descartados`, `valor`), `code/luzia/acoes.py` (`fila`, `enfileirar`, `desenfileirar`, `guardar`, `eventos`, `evidencias`, `status_map`, `todas`, `find`)
- Test: `code/luzia/tests/test_avancos.py`

**Interfaces:**
- Consumes: `banco.conectar`, `banco.transacao`.
- Produces: mesmas funções e retornos de hoje (dicts com `id, titulo, tipo, skill, skill_plano, estado, valor_lm, conta, nota, lm_ganho, tentativas, revisitas, origem, entrega, dimensao, historico, ...`), agora lidos de `avanco`/`avanco_evento`. Nova: `jogo.avancos(con, estado: str | None = None, prisma: str | None = None, tipo: str | None = None) -> list[dict]` (filtros combináveis, ordem de hoje).
- `sincronizar` só faz `INSERT` de avanços novos e `UPDATE` de valor/conta quando mudaram (sem regravar tudo).
- [ ] **Step 1: Testes** `test_filtros_combinaveis` (estado+prisma+tipo), `test_evento_registrado_em_cada_mudanca`, mais os testes de `test_regras_atuais.py` que tratam de fila, revisita e descarte passando sobre o banco.
- [ ] **Step 2–5:** FAIL → implementar → PASS → commit `feat(luzia): advances and their history on sqlite with filters`.

### Task 7: Lúmens, níveis, lampejos e dossiê no banco

**Files:**
- Modify: `code/luzia/jogo.py` (`lancar`, `livro`, `passivo`, `conquistar`, `progresso_skill`, `subir`, `abrir_cartao`, `usar_cartao`, `converter`, `ritmo`, `dossie`), `code/luzia/observer.py` (gravar via `banco.gravar_ou_pendurar`)
- Test: `code/luzia/tests/test_lumens_niveis.py`

**Interfaces:**
- Produces: mesmas assinaturas; apelidos novos `jogo.progresso_prisma = progresso_skill`, `jogo.abrir_lampejo = abrir_cartao`, `jogo.usar_lampejo = usar_cartao`. `progresso_skill` conta "desde" o último `nivel_registro` de qualquer origem. `subir` grava `nivel_registro` origem `conquistado`. `dossie` escreve em linguagem formal (skill, nível, ação) e lista só níveis `conquistado` como evidência, mais os pedidos de mudança aceitos.
- [ ] **Step 1: Testes** `test_subir_registra_conquistado`, `test_declarado_nao_e_evidencia_no_dossie`, `test_teto_passivo_por_dia`, `test_lampejo_uma_vez`, `test_observer_grava_no_banco` (evento simulado de PostToolUse → linha em `lumen` e em `sessao_evento`) e toda a `test_regras_atuais.py` verde sobre o banco.
- [ ] **Step 2–4:** FAIL → implementar → PASS.
- [ ] **Step 5:** remover leituras/escritas dos JSON antigos em `jogo.py`, `acoes.py`, `observer.py` (o teste `test_sem_json_antigo` faz `grep` por `feixes.json`, `lumens.jsonl`, `degraus.json`, `cartoes.json`, `fila.json` fora de `migrar.py`) → commit `feat(luzia): lumens, levels and flashes on sqlite`.

**Portão 2 (Opus):** revisão do motor (fidelidade às regras globais) antes das tarefas 8 e 10.

### Task 8: Detecção das entregas no git

**Files:**
- Create: `code/luzia/entregas.py`, `code/luzia/tests/test_entregas.py`

**Interfaces:**
- Consumes: `privacy.Redactor`, `triage.EXT_AREA`, `trajetoria.prismas`.
- Produces:
  - `entregas.identidades(con) -> list[str]` (de `perfil('identidades')`; carga inicial `entrada.json.author`).
  - `entregas.detectar(repo: Path, identidades: list[str], desde: str) -> list[dict]`: cada entrega com `chave, titulo, inicio, fim, commits:list[{hash,data,mensagem,arquivos,linhas,areas,caminhos}], fonte 'merge-pr'|'ticket'|'commit', ids_privados`. Data = data de autor. Só commits cujo autor está em `identidades`.
  - `entregas.atualizar(con, dias: int = 90) -> dict` (`novas`, `atualizadas`; grava `entrega`, `commit_`, `entrega_prisma`; mensagens e títulos mascarados pelo `Redactor`; primeira execução volta `dias`, depois só o que é novo; `perfil('entregas_desde')` guarda a janela).
- Regras de agrupamento: merge com assunto `Merged PR <n>: <título>` ou `Merge pull request #<n> from <branch>` → commits da pessoa em `merge^1..merge^2`; sem merge → por id de ticket na mensagem (`AB#\d+` ou `#\d+`); senão 1 commit = 1 entrega. Prismas atravessados: palavras do prisma (sem diferenciar maiúsculas, mesma regra de borda de `observer.detectar`) nos caminhos e mensagens; `termos_json` guarda os termos achados.
- [ ] **Step 1: Testes** com repositório git criado no `tmp_path` (`git init`, commits de duas identidades, `merge --no-ff -m "Merged PR 12: Ajusta agregado"`): `test_merge_pr_agrupa_so_minha_autoria`, `test_squash_agrupa_por_ticket`, `test_commit_isolado`, `test_prismas_atravessados_com_termos`, `test_janela_90_dias_e_incremental`, `test_titulo_mascarado_sem_ids` (nenhum `#12`, hash ou nome do `termos.txt` sintético no `titulo`).
- [ ] **Step 2–5:** FAIL → implementar → PASS → commit `feat(luzia): detect deliveries from git (PR merges, tickets, commits)`.

### Task 9: Entrega ligada ao jogo

**Files:**
- Modify: `code/luzia/propriedade.py`; Create: função em `entregas.py`; Test: `code/luzia/tests/test_entrega_detalhe.py`

**Interfaces:**
- Produces:
  - `propriedade.p2_entrega(commits: list[dict]) -> dict | None`: regra atual de `p2_coesao` aplicada à soma de arquivos e linhas e à união de áreas da entrega (conta visível).
  - `entregas.detalhe(con, entrega_id: int) -> dict` com `fatos` (`inicio, fim, duracao_dias, commits, arquivos, linhas, areas`), `prismas` (com termos), `avancos_feitos` (avanços com `entrega_id`), `avancos_uteis` (abertos dos mesmos prismas, até 3), `lumens_ligados` (lúmens com `ref` da entrega ou de avanços dela, mais passivos/conversões dos prismas dela entre `inicio − 1 dia` e `fim + 1 dia`), `propriedade` (P1 geral, P2 sobre a entrega, P3/P4 por evidência), `leitura` (de `leituras.obter`, Tarefa 10, ou `None`).
  - `entregas.listar(con) -> list[dict]` (mais recentes primeiro, com resumo dos fatos).
- [ ] **Step 1: Testes** `test_p2_sobre_entrega`, `test_lumens_ligados_janela_e_prisma`, `test_avancos_uteis_mesmos_prismas`.
- [ ] **Step 2–5:** FAIL → implementar → PASS → commit `feat(luzia): delivery detail linked to advances, lumens and ownership`.

### Task 10: Leituras com base

**Files:**
- Create: `code/luzia/leituras.py`, `code/luzia/tests/test_leituras.py`
- Modify: `code/luzia/planner.py` (esquema `LEITURAS_SCHEMA`: `{"leituras": [{"alvo": str, "texto": str}]}`, texto ≤ 3 frases, só a partir dos fatos recebidos, sem nomes da empresa)

**Interfaces:**
- Consumes: `entregas.detalhe`, `trajetoria.prismas`, `jogo.progresso_skill`, `modelo.chamar` via `pipeline.run_plan(schema=...)`.
- Produces:
  - `leituras.base(con, alvo_tipo: str, alvo_id: str) -> dict` (fatos determinísticos; para prisma: entregas e commits que passaram, avanços e notas, lúmens própria × refletida, proporção dirigido × feito pelo agente calculada de `sessao_evento`/`lumen`, nível, meta, evidência e currículo × prática da triagem para aquele prisma). `leituras.hash_base(base) -> str` (sha256 do JSON ordenado).
  - `leituras.vencidas(con) -> list[tuple[str, str]]`.
  - `leituras.gerar(con, alvos: list[tuple[str, str]] | None = None) -> int`: uma chamada ao modelo para todos os alvos vencidos; grava todas ou nenhuma (transação); sem modelo/chave/internet → 0 e nada gravado.
  - `leituras.obter(con, alvo_tipo, alvo_id) -> dict | None` (`texto, base, modelo, criado_em, vencida: bool`).
- [ ] **Step 1: Testes** (modelo simulado com `monkeypatch` em `pipeline.run_plan`): `test_lote_uma_chamada`, `test_nao_regenera_sem_mudar_base`, `test_regenera_quando_nivel_sobe`, `test_falha_no_meio_nao_grava_nada`, `test_sem_modelo_devolve_none`, `test_base_sem_nomes_privados`.
- [ ] **Step 2–5:** FAIL → implementar → PASS → commit `feat(luzia): grounded AI readings with stored facts, model and date`.

### Task 11: Pedido de mudança da trajetória

**Files:**
- Create: `code/luzia/pedidos.py`, `code/luzia/tests/test_pedidos.py`
- Modify: `code/luzia/planner.py` (`PEDIDO_SCHEMA`: `{"nivel_partida": int, "meta": int, "palavras_chave": [str], "acoes": [ACAO], "analise": str}`)

**Interfaces:**
- Consumes: `trajetoria.*`, `leituras` (a análise é gravada como leitura `alvo_tipo='pedido'` com a base do pedido), `jogo.sincronizar`.
- Produces: `pedidos.abrir(con, tipo, prisma, motivo) -> dict` (recusa se já há pedido aberto/proposto para o prisma), `pedidos.propor(con, pedido_id, nivel: int | None = None, meta: int | None = None) -> dict` (chama o modelo; "Ajustar" = chamar de novo com nível/meta; cada proposta fica no histórico do pedido), `pedidos.aceitar(con, pedido_id) -> dict` (cria/atualiza/arquiva/reativa o prisma, `nivel_registro` origem `pedido` quando o nível muda, avanços iniciais com origem `pedido`, `trajetoria.nova_versao`), `pedidos.recusar(con, pedido_id) -> dict`, `pedidos.listar(con) -> list[dict]`. Tipos `arquivar` e `reativar` não chamam o modelo.
- [ ] **Step 1: Testes** `test_um_pedido_aberto_por_prisma`, `test_ajustar_guarda_propostas`, `test_aceitar_incluir_cria_prisma_avancos_e_versao`, `test_arquivar_preserva_lumens_e_reativar_devolve`, `test_mudar_meta_nao_toca_nivel_nem_lumens`, `test_recusar_nao_muda_trajetoria`.
- [ ] **Step 2–5:** FAIL → implementar → PASS → commit `feat(luzia): formal trajectory change requests with versions`.

**Portão 3 (Opus):** revisão de leituras e pedidos (nenhum texto sem base; estados do pedido) antes da Tarefa 12.

### Task 12: CLI, comandos, foco e vocabulário

**Files:**
- Modify: `code/luzia/cli.py`, `code/luzia/observer.py`, `code/luzia/statusline.py`, `code/luzia/commands/*.md`, `code/luzia/skills/*/SKILL.md`, `code/luzia/hooks/hooks.json` (se necessário)
- Create: `code/luzia/commands/trajetoria.md`, `avancos.md`, `acender.md`, `entregas.md`; Test: `code/luzia/tests/test_cli.py`

**Interfaces:**
- Consumes: tudo acima.
- Produces (comandos da CLI): `trajetoria` (mostra versão, prismas com espectro em texto `▰▰▰▱▱` e pedidos), `pedido abrir <tipo> "<prisma>" --motivo`, `pedido ajustar <id> [--nivel N] [--meta N]`, `pedido aceitar <id>`, `pedido recusar <id>`, `avancos [--estado E] [--prisma P] [--tipo T]`, `acender "<prisma>"` (apelido `trecho`), `entregas [--ampliar DIAS]`, `entrega <id>`, `nivel "<prisma>" N` (declarar); apelidos por uma versão: `acoes`→`avancos`, `trecho`→`acender`, `feedback-progress`→`entregas`. Toda saída com o vocabulário novo e terminando em botões (aceitar/ajustar/recusar no pedido; filtros sugeridos em `avancos`). Lampejo no observador: cartão começa com `✦ Lampejo da Luzia · Prisma <nome>`; contexto do SessionStart e da linha de status com "em foco". Comandos `.md` com `description` entre aspas.
- [ ] **Step 1: Testes** (CLI chamada por `cli.main` com `sys.argv` e a fixture): `test_toda_saida_termina_em_botoes` (todos os comandos sem modelo), `test_avancos_filtros`, `test_pedido_fluxo_completo_pelo_chat` (modelo simulado), `test_vocabulario_sem_termos_antigos` (nenhuma saída visível contém `feixe`, `degrau`, `trecho`, `rota ` como termo do jogo, `cartão`), `test_dossie_formal`.
- [ ] **Step 2–4:** FAIL → implementar → PASS; `claude plugin validate code/luzia` e `claude plugin validate .` → "Validation passed".
- [ ] **Step 5:** `python -m luzia.instalar` só se a sessão principal pedir (ela atualiza `~/.claude`); commit `feat(luzia): chat parity for trajectory, advances, deliveries and new vocabulary`.

### Task 13: API do painel

**Files:**
- Modify: `code/luzia/server.py`; Test: `code/luzia/tests/test_server.py`

**Interfaces:**
- Produces: `GET /api/estado` (perfil, trajetória, prismas com leitura e espectro, avanços, entregas resumidas, lúmens recentes, pedidos, regras, modelo, modo com nome exibido), `GET /api/entrega?id=N` (`entregas.detalhe`), `GET /api/avancos?estado=&prisma=&tipo=`, `POST /api/pedido` (`{acao:'abrir'|'ajustar'|'aceitar'|'recusar', ...}`), `POST /api/nivel`, `POST /api/acender` (substitui `/api/trecho`, que fica como apelido), `POST /api/leituras` (regenerar sob pedido), `POST /api/entregas/ampliar`. Mantém as proteções de Host/Origin/JSON/64 KB.
- [ ] **Step 1: Testes** com `http.client` contra o servidor em thread na fixture: cada rota responde com a forma acima; POST de outra origem → 403.
- [ ] **Step 2–5:** FAIL → implementar → PASS → commit `feat(luzia): panel api for trajectory, deliveries, requests and filters`.

### Task 14: Painel

**Files:**
- Modify: `code/luzia/painel/index.html`, `luzia.js`, `luzia.css`

**Interfaces:**
- Consumes: rotas da Tarefa 13.
- Produces: telas **Hoje · Trajetória · Avanços · Entregas · Ajustes**. Prisma com espectro de 5 faixas (faixas acesas = nível, meta marcada) nas cores da paleta (`--roxo`, `--refletida`, `--luz`, `--areia`, `--salvia`). Leitura do prisma com "Leitura da Luzia · com base em … · modelo · data" (estilo de observação assinada, sem ícone de alerta). Avanços com filtros combináveis (estado, prisma, tipo) e contagens; tipos com ícone e cor. Entregas: cabeçalho de fatos (período, duração, commits, arquivos, prismas), avanços feitos e úteis, lúmens ligados, P1–P4, leitura assinada. Trajetória: versão atual, histórico de versões, botão "Pedir mudança" com o fluxo aceitar/ajustar/recusar. Ajustes: modos com os nomes do foco.
- [ ] **Step 1:** subir o servidor sobre a fixture de dados sintéticos (`LUZIA_PRIVATE=<tmp>`) e conferir no navegador (Browser pane) cada tela em 1440×960 e 375×812, sem texto estourando, sem erro no console.
- [ ] **Step 2:** commit `feat(luzia): panel for trajectory, prisms spectrum, filters and deliveries`.

**Portão 4 (Opus):** revisão de CLI, servidor e painel.

### Task 15: Documentação e varredura

**Files:**
- Modify: `docs/luzia-ux.md`, `code/luzia/CONTEXT.md`, `code/luzia/harness/REGRAS.md`, `docs/handoffs/luzia-acoes.md`

- [ ] **Step 1:** atualizar o vocabulário e as regras (seções 2, 6–9 do spec) nos docs; `REGRAS.md` com os comandos novos.
- [ ] **Step 2:** `git grep -n -i -f <(grep -v '^#' code/luzia/private/termos.txt)` vazio (os nomes ficam só em `private/termos.txt`, fora do git); `grep` dos termos antigos do jogo (`feixe`, `degrau`, `trecho`) só em histórico/handoff.
- [ ] **Step 3:** commit `docs(luzia): new vocabulary, persistence and trajectory requests`.

### Task 16: Verificação final (sessão principal)
- [ ] Suíte inteira verde; migração real feita sobre **cópia** de `private/` (totais iguais aos JSON); depois, com o OK da Rayane, migrar os dados reais (backup automático).
- [ ] Ponta a ponta no chat: `/luzia:hoje` → fazer avanço → registrar → subir nível → `/luzia:trajetoria` pedido incluir → aceitar.
- [ ] Ponta a ponta no painel (navegador) com os dados migrados.
- [ ] `claude plugin validate` nos dois manifestos; `python -m luzia.instalar` para atualizar `~/.claude`; handoff atualizado.
