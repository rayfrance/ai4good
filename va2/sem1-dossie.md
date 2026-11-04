# Dossiê de defesa · sem1 (04/11/2026)

> Material de apoio preparado com IA a partir do `cmp.md`, `brw.md` e `tec.md`. Traz **fatos com
> fonte e opções**, não frases prontas. As quatro frases, a fala, as respostas ao ensaio e ao
> professor são suas. Capturas de tela em `outputs/sem1/`, feitas em 04/11/2026.

## O que o professor vai checar (mínimos do guia)

| ponto | mínimo para passar |
|:--|:--|
| 1 · a ideia | um usuário concreto **e uma cena** (não "os desenvolvedores"); quem sofre, com o quê, o que a ideia faz |
| 2 · produto | app que existe, **tela ou link no slide**, por que é o mais próximo, **onde falha para o seu usuário** |
| 3 · artigo | **título, ano, veículo** no slide, **artigo completo**, o que ele **mostrou**, por que é o mais próximo |
| 4 · diferencial | o que só a sua faz para o usuário **e** uma pergunta científica que o experimento **pode responder "não"** |

Armadilhas do exemplo quase bom a evitar: ideia sem pessoa (anot. 1), lista de funções no lugar da ideia (2), competidor de palha (3), artigo que não compete (4), diferencial em adjetivos (5), ensaio sem mudança e tempo não cronometrado (6).

## Decisão 1 · produto mais próximo

| | **Pear** (sua escolha no CMP, 28/10) | **Vibe Check** (contraexemplo que a derrubada achou) |
|:--|:--|:--|
| o que é | CLI em alpha: `pear watch` observa diffs do Claude Code/Cursor e ensina nas pausas; guarda progresso de conceitos entre sessões. GitHub em 04/11: v0.1.0-alpha, 4 estrelas, 1 contribuidor, último commit há ~4 meses. [site](https://www.pearcode.dev/) · [README](https://github.com/MitchTheStonky/pear) · tela: `outputs/sem1/pear_site.png`, `pear_readme.png` | Extensão VS Code, v0.7.0, 31 instalações: transforma inserções grandes de código de IA em quiz estilo Duolingo, com revisão espaçada (FSRS). [Marketplace](https://marketplace.visualstudio.com/items?itemName=cognitra.vibe-check-cognitra) · tela: `outputs/sem1/vibecheck.png` |
| no que é bom | proativo, usa mudanças reais do repositório, slogan "AI makes you fast. pear makes you grow." (mesma motivação sua) | **prática ativa** ligada ao código + revisão espaçada: cobre o mecanismo da sua frase provisória |
| onde falha (com fonte) | [prompts atuais](https://github.com/MitchTheStonky/pear/blob/main/cli/prompt/assembler.go#L19) instruem **não** aplicar perguntas/quizzes proativos; contagem de exposição a conceitos ≠ domínio; sem validação de compreensão ou carreira | dispara também em colagens sem IA; acerto/XP não demonstra transferência; sem registro de razões/alternativas nem dimensão de carreira |
| consequência | ameaça a **observação no fluxo** (proatividade não é diferencial seu — já corrigido no CMP) | ameaça a **prática ativa** (seu foco escolhido). Anotação 2 do excelente: "o competidor que dói", e dizer o que ele derrubou |

Pergunta para você decidir: qual dos dois ameaça mais o que você vai defender no ponto 4? Se o ponto 4 for prática ativa, o professor provavelmente perguntará "isso não é o Vibe Check?".

## Decisão 2 · artigo mais próximo (só completos; Vibe-GUIDE é preprint e fica fora)

| | **From Junior to Senior** | **Code with Me or for Me?** |
|:--|:--|:--|
| referência | Dana Feng, Bhada Yun, April Yi Wang · **CHI 2026** (Barcelona), artigo completo, 24 p. · [DOI](https://doi.org/10.1145/3772318.3791642) · [texto](https://arxiv.org/html/2602.00496v2) · tela: `outputs/sem1/junior_senior.png` | Valerie Chen, Ameet Talwalkar, Robert Brennan, Graham Neubig · **CHI 2026**, completo, 19 p. · [DOI](https://doi.org/10.1145/3772318.3790850) · [texto](https://arxiv.org/html/2507.08149v2) · tela: `outputs/sem1/code_with_me.png` |
| o que fez | 3 fases: Delphi com 5 seniores; tarefa de depuração com IA (Cursor Agent/Ask) com 10 juniores; revisão cega dos históricos de prompt dos juniores por 5 seniores | estudo controlado com 20 desenvolvedores: copiloto (GitHub Copilot) × agente (OpenHands, que edita arquivos e roda código) |
| o que mostrou (resumo dos autores) | agência é mais limitada por política organizacional que por preferência; experientes controlam por delegação detalhada; **novatos oscilam entre dependência excessiva e evitação**; seniores têm perspectiva valiosa para mentorar; propõem 3 práticas para preservar agência em codificar, **aprender e mentorar** | agentes superam copilotos em algumas tarefas e reduzem esforço, mas **garantir que o usuário entenda o comportamento do agente** continua um desafio |
| o que não mediu | não implementa nem testa um mentor; compreensão e aprendizagem não medidas por teste objetivo; práticas são propostas | compreensão **autorrelatada**; sessões curtas; não mede formação de habilidade |
| proximidade com você | mesmo tema (crescimento profissional + agente no projeto) e propõe mentoria; é o que você "implementaria e testaria" | mesmo cenário técnico (agente que age no projeto) e aponta o problema da compreensão |

## Decisão 3 · o diferencial e a pergunta que pode dar "não"

Estado do CMP: auditoria disse que **o diferencial ainda não está estabelecido**; Vibe Check e Socratiskill já fazem prática ativa no código. Abaixo, lacunas que as fontes **não** cobriram, como opções para você escolher ou descartar. Nenhuma está provada como exclusiva.

| lacuna | quem cobre parte | o que ninguém do catálogo mediu | tipo de resultado que responderia "não" |
|:--|:--|:--|:--|
| (i) compreensão do código feito pelo agente medida **por teste**, não autorrelato | Vibe-GUIDE (teste com rubrica, sem vantagem clara, preprint); (Im)Paired (preprint) | efeito de prática no fluxo sobre compreensão objetiva, com profissionais | grupo com mentor não acerta mais que grupo só com agente |
| (ii) **transferência**: aplicar o critério numa tarefa posterior diferente | Socratiskill/Vibe Check revisam o mesmo conceito; Pear guarda progresso | nenhum mede desempenho numa tarefa nova, sem a ferramenta | quem praticou não resolve melhor a tarefa nova |
| (iii) **interpretação do episódio corrigível** (evidência, assistência conhecida, lacunas), do BRW § 6c / § 3 "como começar" | Decodie registra razões; Pear/Vibe Check dão feedback | conferência dirigida não achou o ciclo completo em Pear nem Vibe Check (não prova ausência) | a pessoa não concorda/corrige mais, ou a devolutiva não muda decisão seguinte |

Linhas de base que o professor espera ver depois no EXP: o "jeito de hoje" (agente sozinho) e o competidor mais forte (Pear ou Vibe Check).

Lembrete do guia: diferencial **para o usuário** e contribuição **científica** são coisas separadas (anotação 4 do excelente).

## Busca de 04/11 · diagnóstico de nível de carreira e referenciais

Pedido da autora após propor diagnóstico de nível, ancorado em fontes oficiais, com visão de progressão. Busca e abertura feitas pelo agente em 04/11/2026; nada foi instalado ou executado.

**Já existe diagnóstico de nível a partir do GitHub (derruba "diagnosticar o nível" como novidade isolada):**

| ferramenta | o que documenta | limite para o seu caso |
|:--|:--|:--|
| [GitIntel](https://github.com/Divya4879/Github-Analyzer) (MIT, 3 estrelas, hackathon) | Gemini pontua até 5 repositórios em 8 dimensões; perfil com nível **Junior → Staff**, forças, fraquezas e áreas de crescimento | análise pontual de perfil público; não acompanha o trabalho com agente nem cita referencial de competências |
| [showmethecode](https://github.com/ikarius6/showmethecode) (0 estrelas) | estima senioridade via LLM | critérios próprios: Junior = "1-2 linguagens", Senior = "5+ linguagens" — regra do autor, não referencial oficial |
| [GitDeep](https://github.com/yuvraj-sarathe/gitdeep) | modo Developer de mentoria, "trajetória de carreira" (subindo/estável/caindo), radar de habilidades | estimativa da IA sobre o perfil; a busca reporta que o próprio README avisa que confiança é estimativa da IA, não métrica medida |

Nenhuma das três, nas fontes abertas, (a) ancora o nível num referencial publicado, (b) acompanha tarefas no fluxo com agente, ou (c) foi validada contra avaliação humana. "Não encontrado" ≠ ausência comprovada.

**Referencial oficial que existe:** [SFIA](https://sfia-online.org/en/framework), da SFIA Foundation (sem fins lucrativos): habilidades × **7 níveis de responsabilidade**, com [visão de engenharia de software](https://sfia-online.org/en/sfia-8/sfia-views/software-engineering-competencies) alinhada ao SWEBOK e uma [camada de habilidades de IA](https://sfia-online.org/en/tools-and-resources/ai-skills-framework) no SFIA 9. Conferir no site qual versão é a atual antes de citar no slide. A avaliação oficial SFIA é **humana**: [SkillsTX](https://skillstx.com/certify/) usa assessores credenciados, com autoavaliação inicial e evidências de prática. A SkillsTX anuncia um produto com agentes de IA (TXpertIQ) que **não foi aberto nem conferido**; é o primeiro lugar a checar se o professor perguntar "alguém já faz isso com SFIA?".

**Consequência para o ponto 4 (opções, decisão sua):** o que sobra como possível diferença é a **combinação** de diagnóstico ancorado num referencial (ex.: SFIA) com acompanhamento no fluxo de trabalho com agente. Uma pergunta que pode dar "não" nasce da linha de base humana: o assessor SFIA, ou os seniores que avaliaram juniores às cegas no From Junior to Senior.

## Perguntas prováveis do professor (fatos para você responder com suas palavras)

| pergunta | onde estão os fatos |
|:--|:--|
| "por que esse produto e não outro?" | tabela da Decisão 1; CMP § 4 (Pear × Chiron) e § 7 (Vibe Check) |
| "por que esse artigo?" | Decisão 2; CMP § 4 (Junior/Senior × CS Achievement; Code with Me × Professional Developers Don't Vibe) |
| "isso não é o Vibe Check / Socratiskill?" | CMP § 5 matriz (eixos 3, 4, 5) e § 7 |
| "o que é um agente? por que agêntico e não chat?" | CMP § 1 recorte de 21/10; agente = modelo + ferramentas que agem no projeto (edita, roda); slides da disciplina "agente de ia", "uso de ferramentas" |
| "o que é transformer / por que LLM?" | TEC § 0 ("por que sem ela não roda"); slides da disciplina "transformers", "modelos de linguagem" |
| "qual é a pessoa concreta? qual a cena?" | sua experiência real com Claude Code/Codex; BRW § 3 "como começar" |
| "como você vai saber se funcionou?" | sua pergunta do ponto 4; EXP ainda não feito — dizer o que será medido |
| "o prejuízo de habilidade é comprovado?" | CMP § 6 checagem: Feng e Chen não demonstram perda causal; (Im)Paired, preprint, achou menor compreensão imediata numa condição |

## Prompt do ensaio cético (passo 3 do guia) — cole numa conversa nova, não nesta

```text
você é um professor cético numa banca de 5 minutos. vou apresentar uma ideia de projeto em 4 pontos:
[cole as 4 frases e o texto dos slides]. faça as 5 perguntas mais difíceis que você faria, uma por vez,
e espere a minha resposta antes da próxima. não invente referências. no fim, diga em qual ponto
eu não te convenci, e por quê. não reescreva a minha fala.
o padrão é lucassf.pages.dev/ai4good/sem1-excelente; evite o que faz lucassf.pages.dev/ai4good/sem1-raso.
```

Responda de cabeça. Se uma pergunta te derrubar, mude a frase ou o slide (não a resposta) e registre no `sem1.md`.
