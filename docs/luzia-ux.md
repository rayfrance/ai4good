# Luzia · desenho da experiência (gamificação e trajetória)

Decidido com a Rayane em 12/11/2026 (persistência, trajetória, prismas e leituras com base adicionadas após a revisão do mesmo dia). A metáfora é a tese: o código que o agente produz e você não domina é **luz refletida**; quando você explica, decide e defende, a luz passa a ser **própria**.

## Vocabulário
Nome real primeiro; a metáfora de luz só onde explica algo.

- **Trajetória**: o caminho do nível atual até a meta (ex.: Júnior 3 até Plena), versionado e ajustável por pedido formal de mudança.
- **Prisma (skill)**: uma competência da trajetória (sempre com o nome junto, ex.: *Prisma Domain-Driven Design (DDD)*). Cada prisma exibe os níveis 0–5 em um espectro de 5 faixas que acendem.
- **Nível**: de 0 a 5 em cada prisma; a soma dos avanços de nível forma a trajetória até a meta.
- **Avanço**: ação curta (5 a 30 min) apontada para um prisma; tipos com ícone e cor: `praticar`, `explicar`, `estudar`, `explorar`.
- **Lúmen (lm)**: a pontuação obtida com evidência de domínio.
- **Luz própria / Luz refletida**: a parcela dos lúmens que veio de você (dirigiu, explicou, conquistou) versus o que o agente aplicou sozinho.
- **Propriedade** (fora do jogo, nas Entregas): quanto de uma **entrega** é seu, medido de P1 a P4 com base visível.
- **Foco**: a Luzia observando a sessão com intenção (*Em foco, com lampejos*, *Em foco, em silêncio* ou *Fora de foco*).
- **Lampejo**: cartão curto no chat quando a Luzia em foco percebe um conceito na mudança do agente (`✦ Lampejo da Luzia · Prisma <nome>`); pode virar luz própria uma vez.

> Nos **dossiês e textos formais** (para líder ou PDI), a Luzia usa linguagem formal ("skill", "nível", "ação", "pontos de evidência", "autoria própria"), sem o vocabulário do jogo.

## Progresso sem calendário
- Cada prisma tem nível atual (declarado por você ou estimado na triagem) e meta. A trajetória mede quantos níveis faltam até a meta em todos os prismas ativos.
- O próximo nível de um prisma fica **pronto** quando acumula **150 lm** desde o último registro de nível, com pelo menos **40% de luz própria** e **ao menos 1 avanço conquistado** (evidência avaliada pela rubrica; apenas lúmens passivos não sobem de nível). A Luzia avisa; **você confirma** a subida (regra de ouro: o nível nunca muda sozinho).
- O **prazo** declarado apenas calibra o ritmo sugerido (quantos avanços por semana). Não cria datas obrigatórias nem trava o progresso.
- A cada terço da trajetória, a Luzia gera um **dossiê de evidências** local (que inclui somente níveis conquistados como evidência e registra pedidos de mudança aceitos).
- Ao subir de nível ou quando um prisma fica sem avanço aberto, a Luzia oferece **acender 3 avanços novos** daquele prisma (`/luzia:acender`).

## Sempre uma ação (paridade chat × painel)
Toda saída da Luzia termina em botões (`LUZIA_BOTOES` no CLI e opções equivalentes no painel): continuar um avanço, subir um nível pronto, revisitar, acender 3 avanços, responder ao pedido de mudança ou abrir um filtro. `/luzia:hoje` é o ponto de partida. Toda ação existe no chat e no painel (`Hoje · Trajetória · Avanços · Entregas · Ajustes`); o painel nunca é obrigatório.

## Lúmens
**Ativos (avanços):** valor calculado por regra visível, e o ganho depende da sua explicação.
- Valor = esforço (minutos do avanço) + lacuna (15 lm por nível que falta no prisma) + prioridade (+10 se o prisma é uma das duas maiores lacunas, +5 nos demais; 0 se já está na meta). Limite de 10 a 100 lm.
- Rubrica 0–4: `4 = 100%` · `3 = 75%` · `2 = 50%` · `0–1 = tente de novo` (0 lm; o avanço permanece em andamento).
- Só vale registrar um avanço **iniciado** (`/luzia:fazer`, pela fila do painel ou ao copiar o prompt no painel).
- Nota 2 ou 3: o avanço fica conquistado e pode ser **revisitado uma vez** para buscar o restante (recebe apenas a diferença).
- Todo lúmen de avanço é **luz própria**.

**Passivos e lampejos (dia a dia, observados pelo foco no Claude Code):**
- Conceito aparece apenas no código gerado pelo agente (`PostToolUse`): **+10 lm de luz refletida**.
- Conceito aparece no **seu prompt** (`UserPromptSubmit`, você dirigiu): **+20 lm de luz própria**.
- Converter um **lampejo**: a Luzia faz 1 pergunta sobre o porquê da decisão; avaliada pela rubrica 0–4, vale até **+30 lm de luz própria**, **uma vez por lampejo** (ou escolha **guardar** para transformar em avanço sugerido).
- Teto de **40 lm passivos por prisma por dia**, e um reconhecimento por prisma por sessão. Apenas fatos mascarados (horário, prisma, extensão, modo) são salvos no banco; nunca código bruto nem texto do prompt.

## Avanços: estados e filtros combináveis
- Estados: `Sugerido` → `Na fila` → `Em andamento` → **Conquistado** (ou **Descartado**, com motivo *"não faz sentido para mim"*, *"já domino"* ou *"agora não"*, restaurável; o motivo alimenta sugestões futuras).
- Filtros combináveis por **estado**, **prisma** e **tipo** (com contagens no painel e parâmetros `--estado`, `--prisma`, `--tipo` ou linguagem natural no chat).

## Trajetória flexível (pedido de mudança)
Qualquer ajuste na trajetória — **incluir prisma**, **mudar meta**, **arquivar** ou **reativar** — segue um fluxo formal no chat ou no painel:
1. A pessoa abre o pedido informando o motivo.
2. Para inclusões e mudanças de meta, a Luzia analisa contra a meta final e propõe nível de partida, meta, palavras-chave, 3 avanços iniciais e análise fundamentada.
3. A pessoa escolhe **Aceitar**, **Ajustar** (alterando nível/meta para nova proposta, registrado no histórico do pedido) ou **Recusar**.
4. Ao aceitar, nasce uma nova **versão imutável da trajetória**; nenhum progresso anterior (lúmens, avanços ou níveis conquistados) é perdido. Prismas arquivados preservam tudo e podem ser reativados.

## Entregas (detecção local no git + P1–P4)
- Rastreia entregas localmente nos repositórios autorizados (apenas commits da pessoa): merge commits de PR (`Merged PR ...`, `Merge pull request #...`), commits agrupados por id de ticket (`AB#...`, `#...`) ou commits isolados.
- Janela inicial de **90 dias** (ampliável pelo chat ou painel); atualizações seguintes são incrementais.
- Cada entrega exibe fatos medidos (período, duração em dias, nº de commits, arquivos, linhas, áreas), **prismas atravessados** com termos detectados, **lúmens ligados** na janela, **avanços feitos e úteis**, **propriedade P1–P4** (com P2 calculado sobre o total da entrega) e a **leitura assinada** da Luzia. Títulos e mensagens são os reais, com os números de PR/ticket, e aparecem só para quem entrou no painel (senha local) e no chat da própria pessoa; hashes de commit nunca saem do banco.

## Leituras com base (sem texto solto)
- Toda leitura gerada por IA (por **prisma**, por **entrega** ou por **pedido de mudança**) armazena no SQLite os fatos usados, o hash da base, o modelo e a data, exibindo `Leitura da Luzia · com base em: … · modelo · data`.
- Leituras vencidas são renovadas em lote apenas quando o hash da base muda ou sob pedido explícito. Sem modelo ou sem base suficiente, a interface exibe apenas os fatos medidos e informa leitura indisponível.

## Login do painel e privacidade
- **Senha local.** No primeiro acesso, o painel pede para criar uma senha (mínimo 8 caracteres, com confirmação); ela fica só como hash em `private/acesso.json`. Depois, o painel abre na tela "Entrar" e não mostra nenhum dado antes do login.
- **Sessão.** Cai após 30 min sem uso, ao clicar em **Sair** ou ao reiniciar o servidor. Cinco senhas erradas seguidas travam a entrada por 60 s.
- **Esqueci a senha.** No chat, `/luzia:senha` (ou `senha` na CLI) apaga a senha depois do seu sim e encerra as sessões; o próximo acesso ao painel cria uma nova. O chat não pede senha: ele já roda como você no sistema.
- **Dados visíveis.** Para você, autenticada, nada é mascarado na tela: empresa, módulos, clientes, colegas e números de ticket/PR aparecem como são. Arquivos versionados nunca recebem esses dados.
- **Envio ao modelo.** Por padrão vai real. Em **Ajustes > Privacidade no envio ao modelo** (ou `privacidade mascarar-modelo on|off` no chat) você liga o mascaramento antes de cada chamada.

## Fora do desenho (por decisão)
Sequência de dias (streaks), nomes fantasiosos fora do vocabulário acima e recompensas sem evidência.
