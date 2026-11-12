# tec · Rayane Thaís Gomes de Lima France

> folha do artefato [tecnologia base demonstrável](https://lucassf.pages.dev/ai4good/?doc=artefatos%2F3-tecnologia-base.md). siga o guia passo a
> passo e preencha cada seção aqui. as decisões são suas, e decidir é saber explicar.

## 0 · a minha ideia completa

**Mentor no fluxo (Luzia)**

Desenvolvedores e engenheiros de software ativam um mentor de IA nos projetos que escolherem.  
Um agente baseado em modelo de linguagem relaciona tarefas, estudos e histórico autorizado para reconhecer oportunidades técnicas, de negócio e comunicação profissional.  
O apoio respeita o contexto e envolve comparar, justificar e adaptar decisões, com retomadas em outras tarefas.  
Devolutivas visuais apresentam evidências, assistência conhecida e lacunas, com interpretações corrigíveis; as reações orientam futuras melhorias.  
A proposta busca ampliar o domínio sobre produções com IA e a autonomia na carreira, começando por episódios e temas delimitados.

**Técnica do BRW § 6b:** Modelo de linguagem baseado em transformers, integrado a um agente.

**Por que sem ela não roda — texto preservado do BRW:** O modelo interpretaria tarefas, estudos e episódios autorizados para propor oportunidades, ajustar o apoio e relacionar aplicações posteriores. O agente organizaria ações; RAG poderia recuperar fontes e histórico. Sem essa interpretação semântica, regras e lembretes dependeriam de relações previamente cadastradas ou análise humana recorrente, limitando a adaptação automática a situações diferentes. Permissões e armazenamento são convencionais. A hipótese exige comparação com alternativas simples e avaliação de pertinência; não comprova aprendizagem humana nem exige múltiplos agentes ou treinamento próprio.

Fonte: [brw.md, §§ 5 e 6b](brw.md).

## 1 · as peças

**Verificação prática na máquina em 11/11/2026:** o servidor Ollama 0.40.2 instalado falhou ao iniciar na máquina com GPU integrada Intel UHD (`Failed to start: Unable to init instance: Unspecified error`), inviabilizando os caminhos dependentes de Ollama local. A implementação adotou o SDK oficial `google-genai` (Apache 2.0) com saída estruturada JSON (`gemini-3.5-flash-lite`) integrado como plugin multi-agente (`.claude-plugin`, `.cursor-plugin`, `.codex-plugin`, `.antigravity-plugin` + comandos slash `/luzia:*`) e painel visual em `streamlit` + `altair`.

| peça | central ou apoio | o que faz na ideia | link oficial | licença | por que esta, e não as alternativas |
|:--|:--|:--|:--|:--|:--|
| [`google-genai`](https://github.com/googleapis/python-genai) + `gemini-3.5-flash-lite` | central | interpreta e cruza declaração de carreira, currículo, GitHub, histórico compartilhado entre IAs e metadados de commits anonimizados para devolver o mapa de skills, auditoria de propriedade intelectual e plano estruturado em JSON | [github.com/googleapis/python-genai](https://github.com/googleapis/python-genai) | [Apache 2.0](https://github.com/googleapis/python-genai/blob/main/LICENSE) (SDK); API Gemini sob termos do Google AI Studio | já homologado e funcional na máquina (`code/scripts/llm_clients.py`), com suporte nativo a `response_mime_type="application/json"` e latência medida de ~7,6 s para ~10 mil tokens de entrada, enquanto o Ollama local exigido pelo exemplo do Agno não iniciou na Intel UHD integrada e frameworks adicionais (smolagents/PydanticAI) adicionariam camada intermediária sem ganho para o plugin |
| Plugin Multi-Agente (`.claude-plugin` / `commands/` / `skills/`) | apoio | integra os comandos `/luzia:triage`, `/luzia:feedback-skills-opportunities`, `/luzia:feedback-progress`, `/luzia:next-level` e `/luzia:career-map` ao fluxo do Claude Code, com o observador passivo via hook (Codex, Cursor e Antigravity: só manifestos, sem observador) | [code/luzia/.claude-plugin/plugin.json](../code/luzia/.claude-plugin/plugin.json) | MIT / próprio | permite que a Luzia rode dentro do próprio agente de código onde a pessoa desenvolve, em vez de ser apenas um analisador externo |
| Painel próprio (`code/luzia/server.py` + `code/luzia/painel/`) | apoio | página local da Luzia (127.0.0.1:8501): próxima ação, mapa de skills, propriedade por entrega com a base de cada dimensão, rota 90d/6m/12m e ajustes; cada ação vira um prompt copiável para qualquer agente | — | próprio | substituiu o Streamlit (usado no sem2) para ter identidade visual e layout livres; usa só a biblioteca padrão do Python e HTML/CSS/JS, sem dependência nem CDN |
| [`pypdf`](https://github.com/py-pdf/pypdf) + [`psutil`](https://github.com/giampaolo/psutil) | apoio | extração local de texto de PDFs (currículo/LinkedIn) e medição de pico de memória RSS/Working Set por execução | [github.com/py-pdf/pypdf](https://github.com/py-pdf/pypdf) · [github.com/giampaolo/psutil](https://github.com/giampaolo/psutil) | [BSD-3-Clause](https://github.com/py-pdf/pypdf/blob/main/LICENSE) · [BSD-3-Clause](https://github.com/giampaolo/psutil/blob/master/LICENSE) | leves, executam 100% localmente antes do filtro LGPD (`code/luzia/privacy.py`) |

## 2 · o exemplo oficial, rodando

**de onde veio o código:** chamada básica `client.models.generate_content` do README oficial de [`googleapis/python-genai`](https://github.com/googleapis/python-genai#generate-content) e cliente base em [`code/scripts/llm_clients.py`](../code/scripts/llm_clients.py).

**o que eu mudei nele:** seleção do modelo `gemini-3.5-flash-lite` com chave `GEMINI_API_KEY` via `.env`.

**o comando e a saída, colados como vieram:**

```text
$ python -c "from google import genai;import time;c=genai.Client();t=time.perf_counter();r=c.models.generate_content(model='gemini-3.5-flash-lite',contents='responda so: ok');print(r.text, round(time.perf_counter()-t,2), r.usage_metadata.total_token_count)"
ok 1.39 7
```

## 3 · a alteração mínima (protótipo Luzia ponta a ponta)

**o commit:** `9727f6e` na branch `feature/va2-sem2` ([`code/luzia/`](../code/luzia/)).

**a entrada:** antes, um prompt estático de teste (`"responda so: ok"`); agora, a triagem real da autora (Desenvolvedora Fullstack Jr 3 → Pleno em 12 meses, currículo, GitHub `rayfrance`, 6 notas de estudo no Obsidian incluindo `ddd-cap-01.md`, 30 sessões do Claude Code e Codex e 39 commits do repositório de trabalho anonimizados localmente por LGPD).

**a saída:** antes, texto livre curto; agora, o diagnóstico calibrado de carreira, mapa de 6 skills (atual × alvo), propriedade intelectual por entrega (P1–P4 e passos até 100%), oportunidades da sessão, plano de 90 dias, 6 meses e 12 meses e telemetria completa (`tempo_total_s`, `pico_memoria_mib`, `tokens`), exibidos no agente e no painel `@career-map`.

**o comando e a saída, colados como vieram:**

```text
$ cd code && python -m luzia.cli triage --rotulo sem2-completo-3
(…diagnóstico e mapa de skills…)
`⏱ 12.95 s · 🧠 76.8 MiB · 🔤 10277→2721 tokens · 🔒 34 itens mascarados · versão 9727f6e`
```

**onde a saída erra:** mesmo com a regra de ouro no prompt (fonte estática só mapeia tópico), a execução completa sugeriu DDD `1/5` por causa das "notas do capítulo 1" no vault, que a autora não atualiza com frequência. Sem o histórico, a execução `sem2-falha-fontes-estaticas` não viu conflito entre o currículo de vaga e a prática e inflou a programação agêntica para `4/5`. Detalhes em [`va2/exp.md`](exp.md) e [`outputs/sem2/falha_run.json`](../outputs/sem2/falha_run.json).

## 4 · o vídeo

**link:** [preencha com a gravação do ensaio do sem2] · **duração:** [preencha] · **o que aparece:** [o plugin rodando e o painel `@career-map`]

## 5 · o que deu certo e o que errou, sem IA

[PREENCHA — até 4 linhas suas sobre o que acertou, onde errou, quanto tempo/memória pediu e o que muda na ideia]
