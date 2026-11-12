# Luzia · trajetória, prismas e persistência · desenho

Data: 12/11/2026 · Autora do produto: Rayane · Redação: Claude (a partir da conversa com ela) · Base: branch `feature/luzia-acoes`, commit `fec4db4`.

## 1. Intenção
A Luzia é uma líder técnica de carreira que vive **dentro do agente de código** (Claude Code, Codex, Cursor, Antigravity). Hoje ela já transforma tudo em ações com botões, mas três coisas a enfraquecem:

1. **O progresso não se sustenta.** Fica em vários JSON sem trava entre processos (hook, CLI e painel gravam ao mesmo tempo), sem histórico de rotas e sem ligação entre entregas, commits, ações e lúmens.
2. **Há texto de IA solto.** O mesmo diagnóstico aparece em todas as skills; a observação de cada entrega parece um alerta do aplicativo e não diz de onde veio.
3. **As entregas são vagas.** Não se sabe o que foi entregue, quando, em quanto tempo, com quantos commits, por quais skills passou, nem como isso se liga aos lúmens e às ações.

O objetivo é que **tudo se conecte numa experiência de jogo coesa, persistida e explicável**: a IA é o motor, mas todo texto gerado tem base visível, e todo progresso fica registrado de forma robusta.

## 2. Vocabulário (decidido com a Rayane)
Nome real primeiro; a metáfora de luz só onde explica algo.

| termo | o que é | substitui |
|:--|:--|:--|
| **Trajetória** | o caminho do nível atual até a meta (ex.: Júnior 3 → Plena) | rota |
| **Prisma** | uma skill da trajetória (ex.: "Prisma DDD") | skill (na experiência) |
| **Nível** | 0 a 5 em cada prisma; subir de nível é o que antes era "degrau" | degrau |
| **Avanço** | ação curta (5 a 30 min) de um prisma; tipos: explicar, praticar, estudar, explorar | feixe |
| **Lúmen (lm)** | a pontuação | — |
| **Luz própria / refletida** | lúmens que vieram de você / do que o agente fez | — |
| **Propriedade** | quanto de uma **entrega** é seu (P1–P4), fora do jogo | — |
| **Foco** | a Luzia observando a sessão com intenção ("a Luzia está em foco") | observador |
| **Lampejo** | o cartão curto que a Luzia mostra no chat quando percebe um conceito na mudança ("Lampejo da Luzia · Prisma DDD"); pode virar luz própria uma vez | cartão |

Modos do foco: **em foco, com lampejos** (era "ativo"), **em foco, em silêncio** (era "passivo"), **fora de foco** (era "sob demanda").

Regras de uso:
- Sempre "Prisma DDD" (nome junto), nunca "um prisma" solto. Na primeira aparição de cada tela/comando: "prisma (skill)".
- **Dossiê e textos formais** (para líder, PDI) usam "skill", "nível" e "ação", não o vocabulário do jogo.
- "Trecho" deixa de existir: "acender 3 avanços novos".
- Visual: cada prisma mostra os níveis 0–5 como **faixas de um espectro que acendem** (nível 3 = 3 faixas acesas). As cores das faixas seguem a paleta da Luzia (roxo → lilás → laranja → areia); a escolha exata é do construtor. O prisma refrata, não reflete: não desenhar reflexo.
- Tipos de avanço ganham **ícone e cor**, sem nomes inventados.

A troca vale em toda superfície visível: painel, saídas da CLI, comandos, skills, cartões do observador, linha de status, docs (`docs/luzia-ux.md`, `code/luzia/CONTEXT.md`, `harness/REGRAS.md`). Identificadores internos (nomes de tabela, colunas, funções) podem usar os termos novos; é escolha do construtor manter ou não as chaves dos esquemas JSON enviados ao modelo.

## 3. Metas, não metas e antimetas
**Metas**
- Persistência robusta e completa de todo o estado do jogo, com histórico.
- Trajetória flexível por **pedido de mudança formal**, feito pelo chat ou pelo painel.
- Entregas especificadas por fatos medidos e ligadas a prismas, avanços e lúmens.
- Leitura personalizada por prisma e por entrega, sempre com base.
- Filtros de avanços por estado, prisma e tipo, no painel e no chat.
- **Paridade chat × painel**: toda ação existe nos dois; o uso principal é pelo agente. O painel é para ver o mapa, nunca obrigatório.

**Não metas (agora)**
- Integração com Jira/Azure DevOps por MCP (passo futuro, só se a pessoa quiser).
- Sincronização entre máquinas, banco em nuvem, uso por times.

**Antimetas (seria fracasso mesmo funcionando)**
- Qualquer texto de IA exibido sem "com base em" (fatos), modelo e data.
- Perder progresso (lúmens, avanços, níveis) por mudança de trajetória, migração ou escrita concorrente.
- Exigir abrir o painel para alguma ação.
- Nomes infantis ou fantasiosos além do vocabulário acima.
- Nome da empresa, de produto interno, clientes, colegas, e-mails, números de PR/ticket ou hashes em arquivo versionado ou na tela.

## 4. Restrições
- Local, Python da biblioteca padrão (sem dependência nova para persistência), Windows primeiro, funciona sem internet exceto nas chamadas ao modelo.
- LGPD: tudo pessoal em `code/luzia/private/` (gitignored). O mascaramento existente (`privacy.Redactor`) continua valendo antes de qualquer envio ao modelo.
- Regras de jogo já decididas continuam (ver `docs/luzia-ux.md`): valor do avanço = esforço + lacuna + prioridade (10–100 lm); rubrica 4/3/2 = 100/75/50%, 0–1 tente de novo; uma revisita (só a diferença); registrar exige avanço iniciado; passivos +10 refletida / +20 própria / conversão até +30 uma vez por cartão; teto 40 lm passivos por prisma por dia; subir de nível: 150 lm desde o último nível, ≥40% luz própria, ≥1 avanço conquistado, e **só com o sim da pessoa**.
- Agnóstico de harness: toda saída da CLI termina com `LUZIA_CLI` / `LUZIA_PERGUNTA` / `LUZIA_BOTOES` (protocolo atual).
- Plugin do Claude Code continua válido (`claude plugin validate`).

## 5. Persistência (decisão do Claude, aceita pela Rayane)
**SQLite** num arquivo `private/luzia.db` (módulo `sqlite3`), modo WAL, `busy_timeout` de 5 s, toda escrita numa transação (`BEGIN IMMEDIATE`). Isso resolve a concorrência entre hook, CLI e painel. Uma camada única (ex.: `luzia/banco.py`) concentra o acesso; nenhum outro módulo abre arquivo de estado.

**Princípios**
- **Livros só de acréscimo** para o que é histórico: lúmens, eventos de avanço, níveis subidos, versões da trajetória, chamadas ao modelo. Nada disso é apagado nem reescrito.
- Estado atual (ex.: estado de um avanço, nível de um prisma) pode ficar em colunas para leitura rápida, mas tem de bater com os livros (um teste confere).
- Todo texto de IA mora numa tabela de leituras com a base.

**Entidades mínimas** (nomes de colunas ficam com o construtor)
| entidade | guarda |
|:--|:--|
| perfil | rótulos da trajetória (onde está, aonde vai), horizonte, modo do observador, agente, repositórios autorizados |
| prisma | nome, palavras-chave, nível atual, meta, estado (ativo/arquivado), origem (triagem ou pedido), base de nível, data do último nível |
| trajetoria_versao | número, data, origem (triagem ou pedido), foto dos prismas e metas daquela versão |
| pedido_mudanca | tipo (incluir prisma, arquivar, reativar, mudar meta), alvo, motivo da pessoa, proposta da Luzia (nível de partida, meta, palavras, avanços iniciais), leitura ligada, estado (aberto → proposto → aceito/recusado), datas |
| avanco | id curto estável, prisma, tipo, título, por quê, conceitos, como, onde explorar, prompt, duração, valor e conta, origem (triagem, entrega, sessão, acender, cartão), entrega ligada (opcional), dimensão P3/P4 (opcional), estado, nota, lm ganho, tentativas, revisita |
| avanco_evento | avanço, quando, evento (sugerido, enviado, iniciado, tente de novo, conquistado, revisitado, descartado com motivo, restaurado), onde, nota, resumo |
| lumen | quando, prisma, lm, luz (própria/refletida), fonte (avanço, passivo-prompt, passivo-refletida, conversão), referência (avanço, cartão, sessão, entrega) |
| nivel_subido | prisma, de → para, quando, lm e % luz própria no momento |
| lampejo | prisma, sessão, quando, estado (aberto/convertido/guardado) |
| entrega | título mascarado, início, fim, nº commits, arquivos, linhas, áreas, ids privados de PR/ticket, fonte de detecção |
| commit | hash (privado), data, mensagem mascarada, arquivos, linhas, áreas; ligado à entrega |
| entrega_prisma | prismas que a entrega atravessa, com a evidência da detecção (quais termos) |
| leitura | alvo (prisma, entrega, trajetória, pedido), texto, base (fatos usados, em JSON), hash da base, modelo, data |
| fila | avanços enviados do painel ao agente, sessões em que já foram oferecidos |
| sessao_evento | evento mascarado do observador (quando, sessão, prisma, extensão, origem, lm, luz) |
| chamada_modelo | custo de cada chamada (o que hoje vai para `runs.jsonl`) |

**Migração**: na primeira execução, importar `feixes.json`, `lumens.jsonl`, `degraus.json`, `autoavaliacao.json`, `cartoes.json`, `evidencias.jsonl`, `fila.json`, `acoes_guardadas.json`, `sessao.jsonl` e `career_state.json` para o banco, numa transação. Copiar os originais para `private/migracao-AAAAMMDD/` e não apagar. Idempotente (rodar de novo não duplica). Teste: totais de lúmens, estados de avanços e níveis iguais antes e depois.

`outputs/sem2/` continua como foto do seminário; `runs.jsonl` pode seguir recebendo o custo (versionado, sem dados pessoais) além da tabela.

## 6. Trajetória flexível (pedido de mudança)
Decidido com a Rayane: toda mudança é **formalizada** como pedido.

Fluxo (igual no chat e no painel):
1. A pessoa pede: incluir um prisma que não estava no currículo, arquivar, reativar ou mudar a meta. No chat, em linguagem natural ("Luzia, quero incluir Mensageria") ou `/luzia:trajetoria`.
2. A Luzia analisa contra a meta e **propõe**: nível de partida, meta, palavras para o observador, 3 avanços iniciais e quantos níveis a trajetória ganha. A análise é uma leitura com base.
3. Botões: **Aceitar**, **Ajustar** (a pessoa muda nível/meta e a Luzia refaz a proposta), **Recusar**.
4. Aceito: nova versão da trajetória; prisma criado ou atualizado; avanços entram no catálogo.
5. Nada se perde: lúmens, avanços conquistados e níveis já subidos continuam. Prisma arquivado guarda tudo e pode ser reativado.
6. O pedido (data, motivo, análise, decisão) entra no dossiê como evidência de que a pessoa dirige a própria carreira.

## 7. Entregas
Decidido com a Rayane: uma entrega é um **ticket** no DevOps; por enquanto rastreada como **PR**, um bloco fechado e com sentido de commits.

**Janela (decidido com a Rayane):** a primeira leitura volta **90 dias** no histórico; a pessoa pode ampliar depois, pelo chat ou pelo painel. Daí em diante, cada nova leitura só acrescenta o que é novo.

**Detecção (local, git, sem IA)**, no repositório autorizado e só com commits da pessoa:
- Merge commits de PR (padrões do Azure DevOps "Merged PR <n>: …" e do GitHub "Merge pull request #<n> …"): os commits da pessoa entre o pai principal e o pai do PR formam a entrega.
- Sem merge (squash ou rebase): agrupar por id de ticket na mensagem (ex.: `AB#123`, `#123`); sem id, cada commit isolado é uma entrega de 1 commit.
- A fonte de detecção fica registrada na entrega.

**Fatos medidos por entrega:** período (primeiro e último commit) e duração; nº de commits, arquivos, linhas; áreas; **prismas atravessados**, detectados pelas palavras-chave do prisma nos caminhos de arquivo e nas mensagens (a evidência dos termos achados fica guardada). Se o construtor quiser usar também as linhas adicionadas do diff, limitar o volume e nunca guardar código.

**Ligação com o jogo, mostrada em cada entrega:**
- avanços **feitos para ela** (acendem P3/P4);
- avanços abertos dos mesmos prismas que **seriam úteis nela**;
- lúmens **ligados a ela**: os de avanços dela e os passivos/conversões dos seus prismas dentro do período (com folga de 1 dia);
- propriedade P1–P4 com base: P1 geral (prompts), **P2 calculado sobre a entrega inteira** (regra atual aplicada a arquivos, linhas e áreas somados), P3/P4 só com evidência;
- **Leitura da Luzia sobre esta entrega** (substitui o texto de "risco"): 1–2 frases geradas só a partir dos fatos, com "com base em …", modelo e data. Visual de observação assinada, não de alerta.

Títulos de entrega mascarados; números de PR/ticket e hashes nunca na tela.

## 8. Leituras com base (fim do texto solto)
Toda leitura de IA guarda os fatos usados, o hash desses fatos, o modelo e a data, e aparece como "Leitura da Luzia · com base em: … · modelo · data".
- **Por prisma** (substitui o diagnóstico geral repetido): fatos = commits e entregas que passaram pelo prisma, avanços e notas, lúmens próprios × refletidos, proporção dirigido × feito pelo agente ("como você usa IA aqui", calculado), nível e meta, e o trecho da triagem sobre aquele prisma (evidência e currículo × prática). Texto curto: o que a Luzia vê e o próximo foco.
- **Por entrega**: ver seção 7.
- **Por pedido de mudança**: ver seção 6.
- Regeneração só quando o hash da base muda (nível subido, entrega nova, avanço conquistado) ou a pedido da pessoa; leituras vencidas são renovadas **em lote numa chamada** para poupar tokens. Sem base suficiente, a tela mostra só os fatos e "a Luzia ainda não tem base para uma leitura".

## 9. Avanços: filtros e paridade
- Painel: filtros combináveis por **estado** (em andamento, na fila, sugerido, conquistado, descartado), **prisma** e **tipo**; contagem em cada filtro.
- Chat: o mesmo por comando e por linguagem natural (ex.: "meus avanços de DDD conquistados" → CLI com os filtros), terminando em botões.
- Todas as ações do painel existem no chat: fazer, enviar, revisitar, descartar com motivo, restaurar, subir de nível, acender avanços, pedir mudança de trajetória, declarar nível, trocar modo/modelo.

## 10. O que muda nas superfícies
- **CLI e comandos**: termos novos nas saídas. Comandos novos ou renomeados: `/luzia:trajetoria` (ver e pedir mudança), `/luzia:avancos` (lista com filtros, substitui `/luzia:acoes`), `/luzia:acender <prisma>` (substitui `/luzia:trecho`), `/luzia:entregas` (substitui `/luzia:feedback-progress`, com a leitura por fatos). `hoje`, `fazer`, `subir`, `next-level`, `dossie`, `fila`, `career-map`, `triage` continuam. Os nomes antigos seguem como apelidos na CLI por uma versão.
- **Painel**: Hoje · Trajetória · Avanços · Entregas · Ajustes. Prisma com espectro de níveis; leitura do prisma com base; entrega com cabeçalho de fatos (período, duração, commits, prismas), avanços ligados, lúmens ligados, P1–P4 e leitura assinada; botão "Pedir mudança" na Trajetória.
- **Foco (observador), lampejos e linha de status**: termos novos; gravam no banco.

## 11. Decisões tomadas pelo Claude depois da revisão (a Rayane pode contestar)
- **Commits da pessoa:** identidades (nome e e-mails de autor, podem ser várias) e repositórios autorizados ficam no perfil; a carga inicial vem de `private/entrada.json` (`author`, `repo`) e de `observer.json`. O horário de um commit é a data de autor.
- **Níveis fora da regra dos 150 lm:** declarar nível, migrar dados antigos e aceitar um pedido gravam no livro de níveis com uma marca de origem (`declarado`, `migrado`, `pedido`) diferente de `conquistado`. O dossiê só conta os conquistados como evidência; a contagem "lm desde o último nível" parte do último registro de qualquer origem.
- **Mudar meta:** nunca mexe no nível atual nem nos lúmens. Meta abaixo do nível atual = prisma na meta. "Quantos níveis a trajetória ganha" = soma de (meta − nível) dos prismas ativos, antes × depois.
- **Arquivar:** o prisma sai da trajetória (os níveis dele deixam de contar no total da trajetória e ele não recebe passivos nem avanços novos), mas os lúmens dele continuam no livro, no total de lúmens, nas entregas e no dossiê. Reativar devolve tudo como estava.
- **Um pedido aberto por prisma**; "Ajustar" pode se repetir sem limite, e cada proposta fica registrada.
- **Observador (caminho quente):** abrir o banco e gravar o evento deve caber no tempo do hook. Se o banco estiver travado além do `busy_timeout`, o evento vai para `private/pendentes.jsonl` e é absorvido na próxima escrita bem-sucedida (nenhum evento se perde, a sessão nunca trava).
- **Migração:** pode disparar de qualquer ponto de entrada (hook, CLI, painel), dentro de uma transação exclusiva com uma marca de versão do esquema; quem chega depois só confere a marca.
- **Sem modelo ou sem internet:** a tela mostra os fatos medidos e "leitura indisponível"; nenhum texto montado por modelo de frase finge ser leitura da Luzia.

## 12. Deixado ao construtor
Nomes de tabelas e colunas, índices, formato exato da foto de versão da trajetória, cores das faixas do espectro dentro da paleta, se as chaves JSON dos esquemas do modelo mudam e como dividir módulos.

## 12a. Orquestração da construção (decidido com a Rayane)
**Qualidade acima de economia de tokens.** O trabalho é dividido em fases e cada uma vai para o modelo que a faz melhor; modelo mais barato só onde ele dá conta com folga.

| fase | o que entrega | quem implementa | por quê |
|:--|:--|:--|:--|
| 1 | banco, esquema, camada de acesso, migração dos JSON, fila de pendentes | **Opus 5.5** | é a fundação: integridade dos dados e concorrência não podem errar |
| 2 | motor do jogo sobre o banco (avanços, lúmens, níveis, lampejos, revisita, tetos) | **Sonnet 5.5** | regras já definidas e testadas hoje; é transporte para o banco |
| 3 | entregas a partir do git (detecção de PR, fatos, prismas atravessados, ligação com avanços e lúmens) | **Sonnet 5.5** | algoritmo descrito na seção 7 |
| 4 | leituras com base (prisma, entrega, pedido), regeneração em lote e pedido de mudança da trajetória | **Opus 5.5** | desenho de prompts e da máquina de estados; é onde nasce ou morre o "texto solto" |
| 5 | CLI, comandos, skills, foco/lampejo e vocabulário novo; filtros no chat | **Sonnet 5.5** | segue o protocolo de botões existente |
| 6 | painel (Trajetória, Avanços com filtros, Entregas, espectro dos prismas) | **Sonnet 5.5**, com conferência visual no navegador | segue o design system existente |
| 7 | docs, `CONTEXT.md`, `luzia-ux.md`, regras para outros agentes; varreduras mecânicas (renomeações, buscas LGPD) | **Haiku 5.5** | trabalho mecânico e verificável |

**Portões de qualidade em toda fase:**
- testes automáticos sobre **cópia** dos dados privados (nunca os reais), incluindo os testes das regras de jogo já existentes;
- **revisão de código por Opus** antes de seguir (correção, concorrência, LGPD, fidelidade a este documento);
- uma fase que depende de outra só começa depois que a anterior passou no portão;
- ao final: teste ponta a ponta pelo chat (avanço → registrar → nível → pedido de mudança) e pelo painel no navegador, `claude plugin validate` e busca LGPD;
- commits por fase, mostrados antes, sem push sem autorização.

## 13. Critérios de aceite
- Migração sem perda (totais iguais) e idempotente; nenhum módulo lê/escreve os JSON antigos depois dela.
- Escritas simultâneas de hook, CLI e painel (teste com processos em paralelo) sem perder evento.
- Nenhum texto de IA na tela sem base, modelo e data.
- Cada entrega mostra período, duração, commits, prismas, avanços ligados e lúmens ligados.
- Pedido de mudança completo (pedir → proposta → aceitar/ajustar/recusar) pelo chat e pelo painel, gerando nova versão da trajetória sem perder progresso.
- Filtros de avanços por estado, prisma e tipo nos dois lados.
- Vocabulário novo em todas as superfícies; dossiê em linguagem formal.
- `git grep` sem nomes da empresa/clientes/colegas; `claude plugin validate` passando; testes das regras de jogo atuais continuam passando.
