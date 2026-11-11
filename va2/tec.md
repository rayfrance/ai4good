# tec · Rayane Thaís Gomes de Lima France

> folha do artefato [tecnologia base demonstrável](https://lucassf.pages.dev/ai4good/?doc=artefatos%2F3-tecnologia-base.md). siga o guia passo a
> passo e preencha cada seção aqui. as decisões são suas, e decidir é saber explicar.

## 0 · a minha ideia completa

**Mentor no fluxo (LuzIA)**

Desenvolvedores e engenheiros de software ativam um mentor de IA nos projetos que escolherem.  
Um agente baseado em modelo de linguagem relaciona tarefas, estudos e histórico autorizado para reconhecer oportunidades técnicas, de negócio e comunicação profissional.  
O apoio respeita o contexto e envolve comparar, justificar e adaptar decisões, com retomadas em outras tarefas.  
Devolutivas visuais apresentam evidências, assistência conhecida e lacunas, com interpretações corrigíveis; as reações orientam futuras melhorias.  
A proposta busca ampliar o domínio sobre produções com IA e a autonomia na carreira, começando por episódios e temas delimitados.

**Técnica do BRW § 6b:** Modelo de linguagem baseado em transformers, integrado a um agente.

**Por que sem ela não roda — texto preservado do BRW:** O modelo interpretaria tarefas, estudos e episódios autorizados para propor oportunidades, ajustar o apoio e relacionar aplicações posteriores. O agente organizaria ações; RAG poderia recuperar fontes e histórico. Sem essa interpretação semântica, regras e lembretes dependeriam de relações previamente cadastradas ou análise humana recorrente, limitando a adaptação automática a situações diferentes. Permissões e armazenamento são convencionais. A hipótese exige comparação com alternativas simples e avaliação de pertinência; não comprova aprendizagem humana nem exige múltiplos agentes ou treinamento próprio.

Fonte: [brw.md, §§ 5 e 6b](brw.md).

## 1 · as peças

**Verificação prática na máquina em 11/11/2026:** o servidor Ollama 0.40.2 instalado falhou ao iniciar na máquina com GPU integrada Intel UHD (`Failed to start: Unable to init instance: Unspecified error`), inviabilizando os caminhos dependentes de Ollama local. A implementação adotou o SDK oficial `google-genai` (Apache 2.0) com saída estruturada JSON (`gemini-3.5-flash-lite`) integrado como plugin multi-agente (`.claude-plugin`, `.cursor-plugin`, `.codex-plugin`, `.antigravity-plugin` + comandos slash `/LuzIA:*`) e painel visual em `streamlit` + `altair`.

| peça | central ou apoio | o que faz na ideia | link oficial | licença | por que esta, e não as alternativas |
|:--|:--|:--|:--|:--|:--|
| [`google-genai`](https://github.com/googleapis/python-genai) + `gemini-3.5-flash-lite` | central | interpreta e cruza declaração de carreira, currículo, GitHub, histórico compartilhado entre IAs e metadados de commits anonimizados para devolver o mapa de skills, auditoria de propriedade intelectual e plano estruturado em JSON | [github.com/googleapis/python-genai](https://github.com/googleapis/python-genai) | [Apache 2.0](https://github.com/googleapis/python-genai/blob/main/LICENSE) (SDK); API Gemini sob termos do Google AI Studio | já homologado e funcional na máquina (`code/scripts/llm_clients.py`), com suporte nativo a `response_mime_type="application/json"` e latência medida de ~7,6 s para ~10 mil tokens de entrada, enquanto o Ollama local exigido pelo exemplo do Agno não iniciou na Intel UHD integrada e frameworks adicionais (smolagents/PydanticAI) adicionariam camada intermediária sem ganho para o plugin |
| Plugin Multi-Agente (`.claude-plugin` / `commands/` / `skills/`) | apoio | integra os comandos `/LuzIA:triage`, `/LuzIA:feedback-skills-opportunities`, `/LuzIA:feedback-progress`, `/LuzIA:next-level` e `/LuzIA:career-map` diretamente ao fluxo do Claude Code, Codex, Cursor e Antigravity | [code/leadroid/.claude-plugin/plugin.json](../code/leadroid/.claude-plugin/plugin.json) | MIT / próprio | permite que o LuzIA rode dentro do próprio agente de código onde a pessoa desenvolve, em vez de ser apenas um analisador externo |
| [`streamlit`](https://github.com/streamlit/streamlit) + [`altair`](https://github.com/vega/altair) | apoio | renderiza o painel visual `@career-map` (`code/leadroid/app.py`) com gráfico de skills (atual × alvo), propriedade nas tarefas, comparativo da falha e telemetria de custo | [github.com/streamlit/streamlit](https://github.com/streamlit/streamlit) | [Apache 2.0](https://github.com/streamlit/streamlit/blob/develop/LICENSE) | já instalado no ambiente (v1.63/1.64) e entrega o dashboard interativo do `@career-map` com baixo consumo (~186 MiB RSS) |
| [`pypdf`](https://github.com/py-pdf/pypdf) + [`psutil`](https://github.com/giampaolo/psutil) | apoio | extração local de texto de PDFs (currículo/LinkedIn) e medição de pico de memória RSS/Working Set por execução | [github.com/py-pdf/pypdf](https://github.com/py-pdf/pypdf) · [github.com/giampaolo/psutil](https://github.com/giampaolo/psutil) | [BSD-3-Clause](https://github.com/py-pdf/pypdf/blob/main/LICENSE) · [BSD-3-Clause](https://github.com/giampaolo/psutil/blob/master/LICENSE) | leves, executam 100% localmente antes do filtro LGPD (`code/leadroid/privacy.py`) |

## 2 · o exemplo oficial, rodando

**de onde veio o código:** chamada básica `client.models.generate_content` do README oficial de [`googleapis/python-genai`](https://github.com/googleapis/python-genai#generate-content) e cliente base em [`code/scripts/llm_clients.py`](../code/scripts/llm_clients.py).

**o que eu mudei nele:** seleção do modelo `gemini-3.5-flash-lite` com chave `GEMINI_API_KEY` via `.env`.

**o comando e a saída, colados como vieram:**

```text
$ python -c "from google import genai;import time;c=genai.Client();t=time.perf_counter();r=c.models.generate_content(model='gemini-3.5-flash-lite',contents='responda so: ok');print(r.text, round(time.perf_counter()-t,2), r.usage_metadata.total_token_count)"
ok 1.39 7
```

## 3 · a alteração mínima (protótipo LuzIA ponta a ponta)

**o commit:** tag `sem2` na branch `feature/va2-sem2` ([`code/leadroid/`](../code/leadroid/)).

**a entrada:** antes, um prompt estático de teste (`"responda so: ok"`); agora, a triagem real da autora (Desenvolvedora Fullstack Jr 3 → Pleno em 12 meses, currículo, GitHub `rayfrance`, 6 notas de estudo no Obsidian incluindo `ddd-cap-01.md`, 30 sessões do Claude Code e Codex e 39 commits do repositório de trabalho anonimizados localmente por LGPD).

**a saída:** antes, texto livre curto; agora, o diagnóstico calibrado de carreira, mapa de 6 skills (atual × alvo), avaliação de propriedade intelectual por tarefa com Pergunta da LuzIA técnico, plano de 30/90/180 dias e telemetria completa (`tempo_total_s`, `pico_memoria_mib`, `tokens`), exibidos no agente e no painel `@career-map`.

**o comando e a saída, colados como vieram:**

```text
$ cd code && python -m leadroid.cli triage --forcar --rotulo exp-3-completo
DONE exp-3-completo 9.39 s | 82.1 MiB | tokens: 10171 -> 2426
```

**onde a saída erra:** quando executado sem o histórico compartilhado de estudos/IAs (`exp-falha-sem-historico-ia`, olhando apenas currículo adaptado para vaga de Back-end Pleno + commits feitos com agente), o modelo afirma `"Nenhum conflito relevante entre currículo e realidade"` e superestima Back-end (`4/5`), Arquitetura (`3/5`) e DDD (`2/5`), quando na realidade a autora está no Capítulo 1 do estudo de DDD (`1/5`). Detalhes completos em [`va2/exp.md`](exp.md) e [`outputs/sem2/falha_vs_certo.json`](../outputs/sem2/falha_vs_certo.json).

## 4 · o vídeo

**link:** [preencha com a gravação do ensaio do sem2] · **duração:** [preencha] · **o que aparece:** [o plugin rodando e o painel `@career-map`]

## 5 · o que deu certo e o que errou, sem IA

[PREENCHA — até 4 linhas suas sobre o que acertou, onde errou, quanto tempo/memória pediu e o que muda na ideia]
