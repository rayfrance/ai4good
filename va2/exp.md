# exp · Rayane Thaís Gomes de Lima France

> medições reais de tempo, memória e comportamento da **Luzia** para o [sem2](sem2.md), comparadas à estimativa prévia do [flx.md](flx.md).
> Execuções realizadas em **11/11/2026**, na máquina da apresentação, registradas em [`outputs/sem2/runs.jsonl`](../outputs/sem2/runs.jsonl), [`outputs/sem2/career_state.json`](../outputs/sem2/career_state.json) e [`outputs/sem2/falha_run.json`](../outputs/sem2/falha_run.json).

## 1 · Ambiente de execução medido

- **Máquina:** `Intel64 Family 6 Model 186 Stepping 3, GenuineIntel · Windows 11 · 12 CPUs · 16 GiB RAM · Python 3.14.3` (notebook que vai para a sala de aula).
- **Modelo:** `gemini-3.5-flash-lite` via `google-genai` (`temperature=0.1`, JSON estruturado).
- **Entrada real da autora (`Rayane`):**
  - Declaração de triagem: Desenvolvedora Fullstack Júnior nível 3 → objetivo Pleno em 12 meses (foco em DDD, arquitetura, programação agêntica).
  - Currículo real (4.142 caracteres, adaptado para vaga de Back-end Pleno).
  - Perfil público do GitHub: [`rayfrance`](https://github.com/rayfrance) (15 repositórios recentes).
  - Histórico compartilhado entre as IAs: **6 notas autorais** do vault `Cerebro_Rayane` (incluindo `ddd-cap-01.md` e índice de aprendizados do trabalho) + **30 sessões recentes** do Claude Code (`~/.claude/history.jsonl`) e Codex (`~/.codex/session_index.jsonl`) + plugins ativos.
  - Repositório de trabalho autorizado (repositório corporativo local): **39 commits recentes** da autora (apenas metadados: data, mensagem, extensões, linhas `+ins/-del`), com **anonimização local LGPD** (`[EMPRESA/PRODUTO]` ×27, `[COLEGA]` ×1, `[EMAIL]` ×1, `[TELEFONE]` ×1, `[URL]` ×4), 34 itens no total.

## 2 · Medições de custo (tempo e memória) vs. estimativa do `flx.md`

Todas as execuções abaixo estão em [`outputs/sem2/runs.jsonl`](../outputs/sem2/runs.jsonl), feitas na **versão commitada `9727f6e`** (sem alterações locais), na máquina descrita no § 1, com `gemini-3.5-flash-lite`.

| Execução (`runs.jsonl`) | Local + LGPD (s) | Modelo (s) | **Tempo total (s)** | **Pico de memória (MiB)** | Tokens entrada → saída |
|:--|--:|--:|--:|--:|--:|
| **Estimativa prévia (`flx.md`)** | ~2,50 | ~10,00 | **~13,00** | **~300,0** | ~5.000 → ~1.500 |
| `sem2-completo-1` (triagem) | 2,98 | 6,78 | **13,47** | **76,6** | 10.277 → 2.591 |
| `sem2-completo-2` (triagem) | 2,09 | 8,00 | **13,01** | **76,8** | 10.277 → 2.849 |
| `sem2-completo-3` (triagem) | 2,01 | 7,53 | **12,95** | **76,8** | 10.277 → 2.721 |
| **Média das 3 triagens** | **2,36** | **7,44** | **13,14** | **76,7** | 10.277 → ~2.720 |
| `sem2-dia-a-dia-feedback-progress` | — | — | **8,12** | **75,8** | 2.158 → 956 |
| `sem2-dia-a-dia-feedback-skills-opportunities` | — | — | **6,98** | **75,7** | 853 → 361 |
| `sem2-falha-fontes-estaticas` (sem histórico nem autoavaliação) | 1,98 | 6,66 | **11,88** | **76,6** | 6.111 → 2.603 |

- **Falha de rede registrada:** uma tentativa de `sem2-completo-3` terminou em `504 DEADLINE_EXCEEDED` da API (timeout), sem registro no `runs.jsonl` porque a exceção acontece antes do log. Repetida em seguida. O modo dia a dia depende da rede da sala.
- **O total é maior que local + modelo** em ~3,3 s: o total inclui carregar o SDK `google-genai`, criar o cliente e montar o prompt, que não entram na coluna "modelo".
- **Observador passivo:** o hook roda localmente, sem modelo; não tem custo de API.

### Explicação das diferenças em relação ao `flx.md`

1. **Tempo (13,14 s medido vs. ~13,0 s estimado):** bateu no total, mas por motivos diferentes. Os tokens de entrada foram o dobro do estimado (10.277 vs. 5.000), porque o histórico entre IAs trouxe notas do vault e sessões do Claude Code e do Codex. A geração foi mais rápida que o suposto (~7,4 s para ~2.700 tokens de saída). O preparo local foi parecido (2,36 s vs. 2,5 s), e o carregamento do SDK (~3,3 s) não estava na estimativa.
2. **Memória (76,7 MiB medido vs. ~300 MiB estimado):** cerca de 4× menor. O modelo roda na API, então nenhum peso fica na RAM local; o processo do plugin carrega só o SDK, o `pypdf`, o `psutil` e o JSON anonimizado. O servidor do painel (Streamlit) é um processo separado e não foi medido nesta versão.
3. **Uso diário:** depois da triagem, os comandos do dia a dia mandam só o plano salvo, os commits recentes ou os eventos da sessão, então ficam em 7–8 s e com 4 a 12 vezes menos tokens.

## 3 · Onde erra: a falha medida

A regra de ouro, que a Luzia tem no prompt, diz que fonte estática não define nível: currículo, muitas vezes adaptado para vaga, e notas paradas no vault só mapeiam tópicos. O nível parte da autoavaliação da pessoa, e a memória viva (sessões e commits) ajusta. As duas execuções abaixo mostram que **a regra escrita no prompt não basta**.

| Dimensão | ❌ `sem2-falha-fontes-estaticas` (só currículo + GitHub + commits) | ❌ `sem2-completo-3` (com histórico entre IAs) |
|:--|:--|:--|
| `conflito_curriculo_vs_realidade` | "Sem conflito relevante, currículo alinhado com commits recentes." | "Currículo cita Clean Architecture e DDD, mas a prática atual foca em legado MVC 5." |
| DDD (`luzia_sugere`) | 2/5 · "Commits mostram foco em serviços e models…" | **1/5 · "Início do estudo formal no clube de leitura e notas do capítulo 1."** |
| Programação agêntica (`luzia_sugere`) | **4/5** · "Uso ativo de múltiplos agentes…" | 3/5 |
| Arquitetura (`luzia_sugere`) | 3/5 | 2/5 |

- **O que saiu errado:**
  - Sem o histórico, a Luzia não vê conflito entre o currículo de vaga e a prática.
  - Com o histórico, ela usa a nota do capítulo 1 de DDD, que a autora não atualiza com frequência, para rebaixar o DDD para 1/5. Isso contraria a regra de ouro, e a autora usa DDD na prática.
- **O certo:** a nota só indica que DDD é um tópico em estudo. O nível parte da autoavaliação da autora, ajustada no painel (`🎚️ Ajustar minha autoavaliação`). No gráfico, o ◆ "Luzia sugere" fica separado do ● "você", e a diferença entre os dois fica visível.
- **Quem sofre:** a própria desenvolvedora, que receberia um mapa de carreira errado (rebaixada em DDD ou inflada em agêntica) e um plano de estudo mal direcionado.
- **O que vira medida no sem3:** com que frequência a sugestão da Luzia contraria a autoavaliação por causa de uma fonte estática, e se separar a "fonte de tópico" da "fonte de nível" no próprio payload, e não só no prompt, reduz esse erro.

<details>
<summary>Histórico: medições da 1ª versão (11/11, antes do commit, versão não identificada)</summary>

A 1ª versão registrou `exp-1-completo` a `exp-3-completo` (10,88 s, 9,27 s, 9,39 s; 77,1 a 82,1 MiB; 10.171 → ~2.489 tokens) e `exp-falha-sem-historico-ia` (8,35 s; 83,2 MiB). Essas execuções gravaram a versão como `[HASH]+dirty`: foram feitas antes do commit, sem identificar a versão do código. Por isso foram substituídas pelas medições acima. As linhas continuam no `runs.jsonl`. O valor de 186 MiB atribuído ao painel Streamlit não tinha registro no `runs.jsonl` e foi retirado.

</details>
