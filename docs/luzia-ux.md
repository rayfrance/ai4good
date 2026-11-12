# Luzia · desenho da experiência (gamificação)

Decidido com a Rayane em 12/11/2026 (regras de evidência reforçadas na revisão do mesmo dia). A metáfora é a tese: o código que o agente produz e você não domina é **luz refletida**; quando você explica, decide e defende, a luz passa a ser **própria**.

## Vocabulário (só três palavras temáticas)
- **Feixe**: uma ação curta (5 a 30 min) apontada para uma lacuna.
- **Lúmen (lm)**: o que você ganha com evidência de domínio.
- **Rota**: o caminho de Júnior 3 até Plena, feito de **degraus**.
- **Luz própria**: o quanto de uma entrega (ou de uma skill) é seu, e não do agente.

## Progresso sem calendário
- Cada skill tem nível atual (declarado por você) e meta. Cada nível a subir é um **degrau**; a Rota é a soma dos degraus até a meta.
- Um degrau fica **pronto** quando a skill junta **150 lm** desde o último degrau, com pelo menos **40% de luz própria** e **ao menos 1 feixe conquistado** (evidência avaliada pela rubrica; só lúmens passivos não sobem degrau). A Luzia avisa; **você confirma** a subida (regra de ouro: o nível nunca muda sozinho).
- O **prazo** que você declara só calibra o ritmo sugerido (quantos feixes por semana, dificuldade). Não trava nada nem cria datas.
- A cada terço da Rota, a Luzia gera um **dossiê de evidências** (local) para levar ao líder ou ao PDI. A cada degrau, o próximo trecho de feixes se acende.

## Lúmens
**Ativos (feixes)**: valor por regra visível, e o ganho depende da sua explicação.
- Valor = esforço (minutos do feixe) + lacuna (15 lm por nível que falta na skill) + prioridade (+10 se a skill é uma das duas maiores lacunas, +5 nas demais; 0 se já está na meta). Limite de 10 a 100 lm.
- Rubrica: 4 = 100% · 3 = 75% · 2 = 50% · 0–1 = tente de novo (0 lm, o feixe continua aberto).
- Só vale registrar um feixe **iniciado** (por `/luzia:fazer`, pela fila ou ao copiar o prompt no painel).
- Nota 2 ou 3: o feixe fica conquistado e pode ser **revisitado uma vez** para buscar o restante (só a diferença; o que já ganhou não conta de novo).
- Todo lúmen de feixe é **luz própria**.

**Passivos (dia a dia, observados pelo hook):**
- O conceito aparece só no código que o agente escreveu: **+10 lm de luz refletida**.
- O conceito aparece no **seu prompt** (você dirigiu): **+20 lm de luz própria**.
- Converter: a Luzia pede 1 frase sua sobre o porquê; avaliada pela rubrica, vale até **+30 lm de luz própria**, **uma vez por cartão** (o cartão vale por 24 h).
- Limite de 40 lm passivos por skill por dia, e um reconhecimento por skill por sessão. Só a skill e o tipo são guardados; nunca o texto do prompt nem o código.

## Feixes (estados)
Sugerido → Na fila → Em andamento → **Conquistado**. Ou **Descartado**, com motivo ("não faz sentido para mim", "já domino", "agora não"), restaurável; o motivo volta para a Luzia sugerir melhor. Feixes ficam num catálogo persistente: não somem quando a Luzia gera novas sugestões.

## Fora do desenho (por decisão)
Ritmo/sequência de dias, constelação, nomes temáticos extras, recompensas sem evidência.
