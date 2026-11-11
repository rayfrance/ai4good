# exp · Rayane Thaís Gomes de Lima France

> medições reais de tempo, memória e comportamento do plugin **LuzIA** para o [sem2](sem2.md), comparadas à estimativa prévia do [flx.md](flx.md).
> Execuções realizadas em **11/11/2026**, na máquina da apresentação, registradas em [`outputs/sem2/runs.jsonl`](../outputs/sem2/runs.jsonl), [`outputs/sem2/career_state.json`](../outputs/sem2/career_state.json) e [`outputs/sem2/falha_vs_certo.json`](../outputs/sem2/falha_vs_certo.json).

## 1 · Ambiente de execução medido

- **Máquina:** `Intel64 Family 6 Model 186 Stepping 3, GenuineIntel · Windows 11 · 12 CPUs · 16 GiB RAM · Python 3.14.3` (notebook que vai para a sala de aula).
- **Modelo:** `gemini-3.5-flash-lite` via `google-genai` (`temperature=0.1`, JSON estruturado).
- **Entrada real da autora (`Rayane`):**
  - Declaração de triagem: Desenvolvedora Fullstack Júnior nível 3 → objetivo Pleno em 12 meses (foco em DDD, arquitetura, programação agêntica).
  - Currículo real (4.142 caracteres, adaptado para vaga de Back-end Pleno).
  - Perfil público do GitHub: [`rayfrance`](https://github.com/rayfrance) (15 repositórios recentes).
  - Histórico compartilhado entre as IAs: **6 notas autorais** do vault `Cerebro_Rayane` (incluindo `ddd-cap-01.md` e índice de aprendizados do trabalho) + **30 sessões recentes** do Claude Code (`~/.claude/history.jsonl`) e Codex (`~/.codex/session_index.jsonl`) + plugins ativos.
  - Repositório de trabalho autorizado (repositório corporativo local): **39 commits recentes** da autora (apenas metadados: data, mensagem, extensões, linhas `+ins/-del`), com **anonimização local LGPD** (`[EMPRESA/PRODUTO]` ×27, `[COLEGA]` ×1, `[EMAIL]` ×1, `[TELEFONE]` ×1, `[URL]` ×1).

## 2 · Medições de custo (Tempo e Memória) vs. Estimativa do `flx.md`

| Execução (`runs.jsonl`) | Preparo local (s) | Modelo LLM (s) | **Tempo total (s)** | **Pico de memória RSS (MiB)** | Tokens entrada | Tokens saída |
|:--|:--:|--:|--:|--:|--:|--:|
| **Estimativa prévia (`flx.md`)** | ~2,50 s | ~10,00 s | **~13,00 s** | **~300,0 MiB** | ~5.000 | ~1.500 |
| `exp-1-completo` (CLI do plugin) | 1,37 s | 7,59 s | **10,88 s** | **77,1 MiB** | 10.171 | 2.466 |
| `exp-2-completo` (CLI do plugin) | 1,24 s | 7,53 s | **9,27 s** | **81,9 MiB** | 10.171 | 2.574 |
| `exp-3-completo` (CLI do plugin) | 1,24 s | 7,65 s | **9,39 s** | **82,1 MiB** | 10.171 | 2.426 |
| **Média das 3 execuções completas (CLI)** | **1,28 s** | **7,59 s** | **9,85 s** | **80,4 MiB** | **10.171** | **2.489** |
| Execução dentro do painel Streamlit (`@career-map`) | 1,30 s | 7,55 s | **~9,9 s** | **186,0 MiB** | 10.171 | ~2.450 |
| `exp-falha-sem-historico-ia` (sem vault/histórico IA) | 1,12 s | 6,64 s | **8,35 s** | **83,2 MiB** | 5.921 | 2.194 |

### Explicação das diferenças em relação ao `flx.md`

1. **Tempo total (`9,85 s` medido em média vs. `13,0 s` estimado no `flx.md`):**
   - A extração local (git + vault + currículo + GitHub) levou **1,28 s** (contra ~2,5 s estimados para git + GitHub).
   - O prompt real teve **o dobro dos tokens de entrada estimados** (`10.171` vs. `5.000`), porque o histórico compartilhado trouxe 6 notas do Obsidian e 30 sessões do Claude Code e Codex (`28.889` caracteres), e a saída teve `~2.489` tokens (vs. `1.500` estimados). Ainda assim, a inferência levou **7,59 s** (vs. `10,0 s` estimados), pois no `gemini-3.5-flash-lite` o prefill de 10 mil tokens é quase instantâneo e a taxa real de geração foi de **~325 tokens/s** (acima dos ~150–200 tokens/s supostos no `flx.md`).
2. **Pico de memória (`80,4 MiB` no CLI / `186,0 MiB` no Streamlit vs. `300,0 MiB` estimado no `flx.md`):**
   - Como o modelo roda remotamente na API do Gemini, nenhum peso neural é alocado na RAM local. No CLI do plugin (`python -m leadroid.cli triage`), o processo Python carrega apenas `google-genai`, `pypdf` e o JSON anonimizado (~80 MiB). Quando o painel visual `@career-map` roda no Streamlit (que carrega Tornado, Pandas e Altair), o pico sobe para **186 MiB**, ainda abaixo do teto de 300 MiB estimado no `flx.md`.

## 3 · Onde erra: a falha medida (`exp-falha-sem-historico-ia` vs. `exp-3-completo`)

Para testar o que acontece quando o mentor olha apenas para as fontes tradicionais de mercado e repositório (**Currículo + GitHub + 39 commits do trabalho**, sem o **histórico compartilhado de estudos e sessões de IA** no Obsidian/Claude/Codex), executamos `exp-falha-sem-historico-ia` ([`outputs/sem2/falha_vs_certo.json`](../outputs/sem2/falha_vs_certo.json)):

| Dimensão avaliada | ❌ **Saída na Falha** (só Currículo de vaga + Commits) | ✅ **Saída Certa** (cruzando com Histórico Compartilhado de IA / Vault) |
|:--|:--|:--|
| `conflito_curriculo_vs_realidade` | *"Nenhum conflito relevante; o currículo alinha-se com a atuação diária em .NET e legados hospitalares."* | *"O currículo menciona Clean Architecture e DDD como já aplicados com proficiência para fins de processos seletivos, mas a triagem real e as notas de estudo apontam que a desenvolvedora está no início do estudo formal de DDD (Capítulo 1)..."* |
| **Back-end C# / .NET e Integrações** | **`4/5 → 5/5`** (inflado como se já fosse Pleno/Sênior pelos commits feitos com agente) | **`3/5 → 4/5`** (calibrado para Júnior 3 rumo a Pleno) |
| **Arquitetura .NET / Clean Architecture** | **`3/5 → 4/5`** (*fonte: commits*) | **`2/5 → 4/5`** (*fonte: github/estudo*) |
| **Domain-Driven Design (DDD)** | **`2/5 → 4/5`** (*fonte: curriculo*) | **`1/5 → 4/5`** (*fonte: historico_ia* — Capítulo 1 do livro de Vlad Khononov no Obsidian) |
| **Próximo passo recomendado** | Genérico: *"Na próxima tarefa de integração ou refatoração com agente, explique em detalhes o desenho de domínio e os casos de teste antes de commitar."* | Específico à dúvida real da autora: *"Abra sua nota do Capítulo 1 de DDD no Obsidian, responda às suas próprias dúvidas sobre subdomínios de suporte vs. genéricos com base no seu projeto atual na empresa, e use o Claude Code para revisar sua explicação técnica."* |

- **Quem sofre esse erro:** a própria pessoa desenvolvedora (Rayane), que recebe um mapa de carreira ilusório dizendo que ela já está em nível `4/5` em Back-end e `3/5` em Arquitetura só porque adaptou o currículo para passar em filtro de RH e porque o agente entregou commits grandes (`+384/-15` linhas na integração `Jev`).
- **O que a falha revela sobre a ideia (e vira medida no `sem3`):** currículo é feito para vender e commit feito com IA mostra o que subiu para o repositório, não o que a pessoa sabe. Sem cruzar com o histórico real de dúvidas/prompts nas IAs e sem checar a **propriedade intelectual** sobre cada entrega (`propriedade: "desconhecida"` + Pergunta da LuzIA técnico), o mentor confirma uma ilusão de competência.
