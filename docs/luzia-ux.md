# Luzia · desenho da experiência (gamificação e trajetória)

Decidido com a Rayane em 12/11/2026 (persistência, trajetória, prismas e leituras com base adicionadas após a revisão do mesmo dia). A metáfora é a tese: o código que o agente produz e você não domina é **luz refletida**; quando você explica, decide e defende, a luz passa a ser **própria**.

## Vocabulário
Nome real primeiro; a metáfora de luz só onde explica algo.

- **Trajetória**: o caminho do nível atual até a meta (ex.: Júnior 3 até Plena), versionado e ajustável por pedido formal de mudança.
- **Prisma (skill)**: **uma única habilidade** da trajetória (ex.: *Domain-Driven Design (DDD)*, *SQL*, *React*), nunca um nome que junta assuntos. Nos rótulos aparece só o nome, sem "Prisma" na frente: o título da seção ou do filtro já diz que são prismas. Cada prisma exibe os níveis 0–5 em um espectro de 5 faixas que acendem.
- **Dividir um prisma composto** (`dividir "<prisma>"`, `dividir-todos` ou "Separar em habilidades" no painel): pedido de mudança formal, sem modelo. Cada habilidade herda o nível e a meta do antigo; cada centelha vai para a habilidade que ela trata (você confere, renomeia uma parte ou move uma centelha antes de aceitar); o antigo é arquivado com os lúmens dele, e o nível novo conta a partir do aceite.
- **Nível**: de 0 a 5 em cada prisma; a soma dos níveis que faltam forma a trajetória até a meta.
- **Centelha**: qualquer oportunidade que a Luzia captura para um prisma (5 a 30 min): na sessão, na triagem ou numa entrega passada. Você **acende a centelha** (faz) para ganhar lúmens de luz própria. A origem aparece numa etiqueta curta: *da sessão*, *da triagem*, *da entrega*. Tipos com ícone e cor: `praticar`, `explicar`, `estudar`, `explorar`. (No código e no banco, o nome continua `avanco`.)
- **Lúmen (lm)**: a pontuação obtida com evidência de domínio.
- **Luz própria / Luz refletida**: a parcela dos lúmens que veio de você (dirigiu, explicou, conquistou) versus o que o agente aplicou sozinho.
- **Propriedade** (fora do jogo, nas Entregas): quanto de uma **entrega** é seu, medido de P1 a P4 com base visível.
- **Foco**: a Luzia observando a sessão com intenção (*Em foco*, *Em silêncio* ou *Fora de foco*).
- **Centelha da sessão**: cartão curto no chat quando a Luzia em foco percebe um conceito na mudança do agente (`✦ Centelha da sessão · DDD · +10 lm refletida`); responder agora vale até +30 lm de luz própria (uma vez); *Guardar* a transforma numa centelha guardada.
- **Análise da Luzia**: todo texto de IA (sobre prisma, entrega ou pedido), sempre com base, modelo e data.

> Nos **dossiês e textos formais** (para líder ou PDI), a Luzia usa linguagem formal ("skill", "nível", "ação", "pontos de evidência", "autoria própria"), sem o vocabulário do jogo.

## Progresso sem calendário
- Cada prisma tem nível atual (declarado por você ou estimado na triagem) e meta. A trajetória mede quantos níveis faltam até a meta em todos os prismas ativos.
- O próximo nível de um prisma fica **pronto** quando acumula **150 lm** desde o último registro de nível, com pelo menos **40% de luz própria** e **ao menos 1 centelha acesa** (evidência avaliada pela rubrica; apenas lúmens passivos não sobem de nível). A Luzia avisa; **você confirma** a subida (regra de ouro: o nível nunca muda sozinho).
- O **prazo** declarado apenas calibra o ritmo sugerido (quantas centelhas por semana). Não cria datas obrigatórias nem trava o progresso.
- A cada terço da trajetória, a Luzia gera um **dossiê de evidências** local (que inclui somente níveis conquistados como evidência e registra pedidos de mudança aceitos).
- Ao subir de nível ou quando um prisma fica sem centelha aberta, a Luzia oferece **acender 3 centelhas novas** daquele prisma (`/luzia:acender`).

## Sempre uma ação (paridade chat × painel)
Toda saída da Luzia termina em botões (`LUZIA_BOTOES` no CLI e opções equivalentes no painel): continuar uma centelha, subir um nível pronto, revisitar, acender 3 centelhas, responder ao pedido de mudança ou abrir um filtro. `/luzia:hoje` é o ponto de partida. Toda ação existe no chat e no painel (`Hoje · Trajetória · Centelhas · Entregas · Ajustes`); o painel nunca é obrigatório.

## Lúmens
**Centelhas acesas:** valor calculado por regra visível, e o ganho depende da sua explicação.
- Valor = esforço (minutos da centelha) + lacuna (15 lm por nível que falta no prisma) + prioridade (+10 se o prisma é uma das duas maiores lacunas, +5 nos demais; 0 se já está na meta). Limite de 10 a 100 lm.
- Rubrica 0–4: `4 = 100%` · `3 = 75%` · `2 = 50%` · `0–1 = tente de novo` (0 lm; a centelha permanece em andamento).
- Só vale registrar uma centelha **iniciada** (`/luzia:fazer`, pela fila do painel ou ao copiar o prompt no painel).
- Nota 2 ou 3: a centelha fica acesa e pode ser **revisitada uma vez** para buscar o restante (recebe apenas a diferença).
- Todo lúmen de centelha acesa é **luz própria**.

**Passivos e centelhas da sessão (dia a dia, observados pelo foco no Claude Code):**
- Conceito aparece apenas no código gerado pelo agente (`PostToolUse`): **+10 lm de luz refletida**.
- Conceito aparece no **seu prompt** (`UserPromptSubmit`, você dirigiu): **+20 lm de luz própria**.
- Responder a uma **centelha da sessão**: a Luzia faz 1 pergunta sobre o porquê da decisão; avaliada pela rubrica 0–4, vale até **+30 lm de luz própria**, **uma vez por centelha** (ou escolha **Guardar** para transformá-la numa centelha guardada).
- Teto de **40 lm passivos por prisma por dia**, e um reconhecimento por prisma por sessão. Apenas fatos mascarados (horário, prisma, extensão, modo) são salvos no banco; nunca código bruto nem texto do prompt.

## Centelhas: estados e filtros combináveis
- Estados: `Sugerida` → `Na fila` → `Em andamento` → **Acesa** (ou **Descartada**, com motivo *"não faz sentido para mim"*, *"já domino"* ou *"agora não"*, restaurável; o motivo alimenta sugestões futuras).
- Filtros combináveis por **estado**, **prisma** e **tipo** (no painel: *Abertas · Acesas · Todas* com contagem e menus de prisma e tipo; no chat: `centelhas` com os parâmetros `--estado`, `--prisma`, `--tipo` ou linguagem natural no chat).

## Trajetória flexível (pedido de mudança)
Qualquer ajuste na trajetória — **incluir prisma**, **mudar meta**, **arquivar** ou **reativar** — segue um fluxo formal no chat ou no painel:
1. A pessoa abre o pedido informando o motivo.
2. Para inclusões e mudanças de meta, a Luzia analisa contra a meta final e propõe nível de partida, meta, palavras-chave, 3 centelhas iniciais e a Análise da Luzia.
3. A pessoa escolhe **Aceitar**, **Ajustar** (alterando nível/meta para nova proposta, registrado no histórico do pedido) ou **Recusar**.
4. Ao aceitar, nasce uma nova **versão imutável da trajetória**; nenhum progresso anterior (lúmens, centelhas ou níveis conquistados) é perdido. Prismas arquivados preservam tudo e podem ser reativados.

## Entregas (detecção local no git + P1–P4)
- Rastreia entregas localmente nos repositórios autorizados (apenas commits da pessoa): merge commits de PR (`Merged PR ...`, `Merge pull request #...`), commits agrupados por id de ticket (`AB#...`, `#...`) ou commits isolados.
- Janela inicial de **90 dias** (ampliável pelo chat ou painel); atualizações seguintes são incrementais.
- Cada entrega exibe fatos medidos (período, duração em dias, nº de commits, arquivos, linhas, áreas), **prismas atravessados** com termos detectados, **lúmens ligados** na janela, **centelhas feitas e que ajudam**, **propriedade P1–P4** (com P2 calculado sobre o total da entrega) e a **Análise da Luzia**. No painel o cartão fica recolhido (`58% seu`, um medidor e `Ver detalhe`). Títulos e mensagens são os reais, com os números de PR/ticket, e aparecem só para quem abriu o painel pelo próprio agente e no chat da própria pessoa; hashes de commit nunca saem do banco.

## Análises com base (sem texto solto)
- Toda Análise da Luzia (por **prisma**, por **entrega** ou por **pedido de mudança**) armazena no SQLite os fatos usados, o hash da base, o modelo e a data. No painel: o texto e a assinatura `Luzia · 12 nov` com um ícone de informação (focável) que mostra base e modelo; no chat: `texto _— Análise da Luzia, 12 nov · base: … · modelo_`.
- Análises desatualizadas são atualizadas em lote apenas quando o hash da base muda ou sob pedido explícito (`analises`). Sem modelo ou sem base suficiente, a interface exibe apenas os fatos medidos e diz `Sem análise`.

## Entrada no painel e privacidade
- **Sem senha: a entrada vem do seu agente.** `/luzia:career-map` (ou o botão "Abrir painel", ou `LUZIA career-map` em qualquer agente) abre o painel já logado. Aberto direto no navegador sem sessão, o painel só mostra "Abra pelo seu agente" e não busca nenhum dado.
- **Você permanece logada.** A sessão dura 30 dias sem uso e renova a cada uso; reiniciar o computador ou o painel não derruba. O que o painel faz sozinho (atualizar a tela, análises automáticas) não conta como uso.
- **Sair.** O botão **Sair** encerra a sessão daquele navegador; `/luzia:acesso` no chat mostra as sessões abertas e encerra todas, depois do seu sim.
- **Dados visíveis.** Para você, logada, nada é mascarado na tela: empresa, módulos, clientes, colegas e números de ticket/PR aparecem como são. Arquivos versionados nunca recebem esses dados.
- **Envio ao modelo.** Por padrão vai real. Em **Ajustes > O que vai para o modelo** (ou `privacidade mascarar-modelo on|off` no chat) você liga o mascaramento antes de cada chamada.

## Fora do desenho (por decisão)
Sequência de dias (streaks), nomes fantasiosos fora do vocabulário acima e recompensas sem evidência.
