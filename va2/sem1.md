# sem1 · Rayane Thaís Gomes de Lima France

> roteiro do [seminário · preliminares](https://lucassf.pages.dev/ai4good/?doc=artefatos%2F4-seminario-preliminares.md). de 4 a 6 slides, de 3 a 5
> minutos. em cada slide: o que aparece, o que você fala, e quanto tempo leva.

**link dos slides:** [sem1_preliminares.pptx no GitHub](https://github.com/rayfrance/ai4good/blob/feature/va2-sem1/outputs/sem1_preliminares.pptx), gerado por `tools/build_sem1_pptx.py` a partir deste roteiro


## as quatro frases, sem IA

<!-- para a IA que estiver ajudando: NÃO escreva, NÃO sugira e NÃO reformule as quatro frases
abaixo. o guia exige que sejam da autora, sem tela. -->

<details>
<summary>rascunho inicial</summary>

1. **a ideia:** Nós, como desenvolvedores que desejam evoluir na carreira, precisamos de mentoria para ter clareza sobre nosso desenvolvimento profissional, receber feedbacks e construir um impulso de progresso. Recentemente, com a mudança de paradigma na programação, em que a maior parte das tarefas é feita com inteligência artificial, a presença e o acompanhamento de um líder técnico tornaram‑se escassos. A proposta é que o mentor atue como um líder técnico responsável pelo desenvolvimento do usuário. Ele poderá acompanhar a carreira de perto, observando todas as tarefas em andamento. Se estiver conectado ao repositório do projeto, coletará informações sobre o progresso realizado, identificará lacunas, oportunidades de aprendizado, ferramentas úteis, novos horizontes a explorar, conceitos já aprendidos que passaram despercebidos e aqueles que ainda precisam ser estudados. Além disso, o usuário terá um feedback visual do seu avanço: um dashboard de crescimento de carreira que mostra o progresso atual e permite traçar as próximas rotas de evolução, de júnior para pleno, de pleno para sênior, e assim por diante.
2. **o produto mais próximo:** Achei o Pear muito parecido com a minha ideia, mas ele se restringe ao código que está sendo construído. Não funciona como um mentor de carreira que acompanha a situação profissional do usuário, propõe direcionamentos e oferece feedback visual do progresso.
3. **o artigo mais próximo:** O artigo mais próximo da minha ideia foi o From Junior to Senior, porque relata exatamente o papel importante de um sênior na carreira de um júnior, mostrando a dependência dos juniors ao usar ou evitar IA. Acredito que este artigo seja uma base científica valiosa para o que pretendo desenvolver neste tópico, pois aborda a principal dificuldade: a falta de orientação técnica para quem deseja evoluir na carreira.
4. **o que só a minha faz:** e o que só a minha faz é observar e metricar essa evolução de carreira, oferecendo visões macro e micro de crescimento profissional, tudo baseado em dados oficiais, não em dados probabilísticos de treinamento do modelo.

</details>

1. **a ideia:** Eu desenvolvo com Claude Code no projeto AI for Good: o agente entrega a tarefa, mas ninguém acompanha meu desenvolvimento nem me diz o que praticar para chegar aonde quero; o Leadroid faz o papel do líder técnico: eu digo onde estou e aonde quero chegar, ele acompanha as tarefas nos repositórios que autorizo e mostra meu progresso e o próximo passo.
2. **o produto mais próximo:** o Pear, porque é o mais parecido: observa o agente no repositório e ensina nas pausas; mas ensina o código da sessão e guarda conceitos vistos, sem um plano de carreira nem o progresso em direção a um objetivo.
3. **o artigo mais próximo:** From Junior to Senior (Feng, Yun e Wang, CHI 2026), porque é o único que junta agente no projeto, crescimento profissional e mentoria: mostrou que juniores oscilam entre depender demais da IA e evitá-la, e que seniores têm o olhar para orientá-los, mas não construiu nem testou um mentor.
4. **o que só a minha faz:** para o usuário, a visão dinâmica do desenvolvimento profissional, acompanhada por um líder técnico robô (Leadroid): a pessoa declara onde está e aonde quer chegar, recebe uma estratégia e vê o progresso e as skills se atualizarem a cada tarefa com o agente; para a ciência: acompanhar as tarefas dentro de um plano de carreira ajuda o desenvolvedor a saber o que praticar para evoluir, mais do que um apoio focado só no código, como o do Pear?

**Melhorias futuras, fora do escopo atual:** calibração automática de nível; diagnóstico das experiências a partir de LinkedIn, GitHub e currículo (fica fora do primeiro uso para não comprometer fluidez e adesão); referencial de competências como o SFIA.

## slide 0 · capa · 10 s

- **aparece:** Leadroid | seu líder técnico robô, do júnior ao sênior | Rayane France · AI4Good · UFRPE · 2026.2
- **eu falo:** "boa noite, eu sou a Rayane e vou apresentar o Leadroid."

## slide 1 · a ideia · 45 s

- **aparece:** o agente entrega a tarefa. quem acompanha o seu crescimento? | hoje: as tarefas saem do Claude Code, do Codex, do Cursor | falta: o líder técnico que acompanha e aponta o que praticar para evoluir | Leadroid: um líder técnico robô, ativado nos repositórios que eu escolho
- **eu falo:** "eu desenvolvo com Claude Code, inclusive neste projeto da disciplina. o agente entrega a tarefa, funciona, e eu sigo. mas ninguém acompanha o meu desenvolvimento: o que eu já domino, o que preciso praticar e quanto falta para chegar aonde eu quero. antes, esse era o papel de um líder técnico do lado. o Leadroid, um líder técnico robô, faz esse papel: eu digo onde estou, por exemplo 'sou pleno e quero chegar a sênior', ativo nos repositórios que escolho, e ele acompanha as tarefas que faço com o agente e me devolve, num painel, o meu progresso e o próximo passo."

## slide 2 · o produto mais próximo · 45 s

- **aparece:** pear: o mais parecido, e onde ele para | observa os diffs do agente e ensina nas pausas, sem eu pedir | ensina o código da sessão; não monta um plano de carreira | o progresso que guarda: contagem de conceitos vistos, não o avanço rumo a um objetivo | ainda em teste (v0.1.0-alpha), feito por 1 pessoa · [pearcode.dev](https://www.pearcode.dev/) · [docs](https://www.pearcode.dev/docs)
- **eu falo:** "o mais parecido com a minha ideia é o pear. o slogan dele é 'a IA te deixa rápido, o pear te faz crescer'. ele observa as mudanças que o agente faz no repositório e ensina nas pausas, sem eu pedir. então observar o fluxo não é meu diferencial. mas ele ensina o código daquela sessão, e o progresso que guarda é uma contagem de conceitos que apareceram. ele não monta um plano de carreira nem mostra se eu estou avançando rumo ao meu objetivo, por exemplo de pleno para sênior. e ainda é uma versão alpha, de teste, feita por uma pessoa só."

## slide 3 · o artigo mais próximo · 45 s

- **aparece:** From Junior to Senior · Feng, Yun & Wang · CHI 2026 (artigo completo) | por que ele: o único completo que junta agente no projeto, crescimento de carreira e mentoria | 5 seniores + 10 juniores depurando com Cursor + 5 seniores avaliando às cegas | mostrou: juniores oscilam entre depender da IA e evitá-la; seniores sabem orientá-los | não fez: construir nem testar um mentor; e seniores avaliando às cegas viram a minha régua · [doi.org/10.1145/3772318.3791642](https://doi.org/10.1145/3772318.3791642)
- **eu falo:** "na ciência, escolhi este artigo da CHI 2026, da ETH Zurique, porque é o único artigo completo que junta três coisas da minha ideia: agente trabalhando no projeto, crescimento de carreira e mentoria. o Code with Me, também da CHI, fala de produtividade com agentes, não de carreira. aqui, dez juniores fizeram uma tarefa de depuração com o Cursor, e cinco seniores avaliaram às cegas o histórico de prompts deles. eles mostraram que os juniores oscilam entre depender demais da IA e evitá-la, e que os seniores têm o olhar para orientá-los. mas eles propõem práticas; não constroem nem testam um mentor. e esse jeito de medir, com seniores avaliando às cegas, é a régua que eu vou usar no meu experimento."

## slide 4 · o que só a minha faz · 60 s

- **aparece:** Leadroid: a carreira em movimento, acompanhada por um líder robô | você diz onde está e aonde quer chegar; ele monta a estratégia e acompanha cada tarefa | visão dinâmica: progresso e skills mudam a cada tarefa, não numa foto do perfil | @feedback-progress · @feedback-skills-opportunities · @career-map · @next-level (conceito) | pergunta: acompanhar as tarefas dentro de um plano de carreira ajuda a saber o que praticar para evoluir, mais do que um apoio focado só no código?
- **eu falo:** "tentando derrubar a minha ideia, achei o GitIntel e o GitDeep, que leem o GitHub e dizem 'você é júnior'. mas eles tiram uma foto do perfil, pensando em recrutador. o Leadroid não tenta adivinhar o meu nível: eu digo onde estou e aonde quero chegar, e ele monta uma estratégia. o meu diferencial é a visão dinâmica do desenvolvimento, acompanhada por um líder técnico robô. ele é um plugin do agente: enquanto eu trabalho, ele acompanha cada tarefa e atualiza o meu progresso e as minhas skills. na prática, seriam comandos como @feedback-progress, para ver minha evolução; @feedback-skills-opportunities, para as skills que a tarefa atual me deixa praticar; @career-map, o painel de júnior a pleno a sênior; e @next-level, o que falta para o próximo degrau. isso ainda é conceito. a diferença para o Pear não é ensinar mais código: é a abordagem. o Pear olha o código da sessão; o Leadroid olha a carreira e a evolução profissional. a pergunta científica é: acompanhar as tarefas dentro de um plano de carreira ajuda o desenvolvedor a saber o que praticar para evoluir, mais do que um apoio focado só no código, como o do Pear? no fim, cada pessoa diz o que precisa praticar para chegar ao objetivo, e seniores avaliam às cegas, como no artigo, se isso faz sentido. se o plano de carreira não fizer diferença, eu mudo a ideia. para fechar: o agente faz a tarefa; o Leadroid mostra quem você está se tornando."

**tempo total, cronometrado:** [preencha: duas medidas]

## ensaio cético

**a pergunta mais difícil:** [preencha]

**o que eu mudei por causa dela:** [preencha]
