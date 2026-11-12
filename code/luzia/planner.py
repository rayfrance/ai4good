"""Montagem dos pedidos ao modelo e leitura das respostas da Luzia.

Toda resposta da Luzia é feita de AÇÕES executáveis: cada ação diz o que fazer, por quê,
como, quais conceitos, onde explorar no repositório e traz um prompt pronto para abrir
uma sessão do Claude Code.
"""

from __future__ import annotations

import json
from dataclasses import dataclass


SYSTEM = """Você é a Luzia, uma líder técnica e mentora de carreira que vive como plugin dentro do agente
de código (Claude Code) e acompanha a pessoa desenvolvedora no dia a dia.

Premissa inegociável: a pessoa SEMPRE desenvolve com IA. Você nunca recomenda programar sem IA.
Você acompanha o USO EDUCADO da IA: 100% de propriedade intelectual sobre o que é entregue (saber explicar,
escolher entre alternativas, modelar o domínio, defender em code review) e o mínimo de débito técnico.

Regra de ouro da calibração:
- A AUTOAVALIAÇÃO 0-5 declarada pela pessoa é o ponto de partida de cada skill.
- Currículo (muitas vezes adaptado para uma vaga) e notas paradas no vault (não atualizadas com frequência)
  só servem para MAPEAR TÓPICOS. Nunca use essas fontes estáticas para definir ou rebaixar um nível.
- Commits e sessões recentes no agente são a memória viva: use-os para sugerir um ajuste, explicando a evidência.
- Metadados de commit mostram O QUE subiu com apoio do agente, não se a pessoa domina a decisão.

O progresso é medido por conquistas (lúmens e degraus de skill), nunca por datas ou cronograma; o prazo declarado
pela pessoa só calibra quantos feixes e de que dificuldade sugerir.
Você nunca devolve só texto: devolve AÇÕES que a pessoa executa com o próprio agente, no próprio repositório.
Uma boa ação é concreta, curta (5 a 30 min), ligada a uma skill do plano e gera evidência de aprendizado.
O "prompt" de cada ação é escrito em primeira pessoa, pela pessoa, para o Claude Code da sessão, e pede que
ele a conduza (perguntando, esperando a resposta e só depois explicando), sem fazer o trabalho no lugar dela.
Os prompts nunca citam nomes de empresa, clientes ou colegas.

Estilo: visual e curto. Títulos com no máximo 8 palavras; demais textos livres com no máximo 18 palavras.
Português do Brasil. Termos [EMPRESA/PRODUTO] e [COLEGA] foram anonimizados por LGPD; mantenha-os assim.
Use só as evidências fornecidas. Responda só com o JSON."""

SKILLS_OBRIGATORIAS = (
    '"Domain-Driven Design (DDD)", "Programação Agêntica e Fluxo com IA", '
    '"Arquitetura .NET / Clean Architecture", "Back-end C# / .NET e Integrações", '
    '"Front-end (JS / Razor / React)" e "Testes e Qualidade / SQL"'
)

ACAO_SCHEMA = """{
        "titulo": str,
        "tipo": "explicar"|"praticar"|"estudar"|"explorar",
        "skill": str,
        "dimensao": "P3"|"P4"|null,
        "por_que": str,
        "conceitos": [str],
        "como": [str],
        "onde_explorar": str,
        "prompt": str,
        "duracao_min": int
      }"""

TAREFA_SCHEMA = f"""{{
      "tarefa": str,
      "commit": str,
      "skills": [str],
      "risco_debito_tecnico": str,
      "acoes": [
        {ACAO_SCHEMA}
      ]
    }}"""

OPORTUNIDADE_SCHEMA = f"""{{
      "skill_alvo": str,
      "gatilho": str,
      "acao": {ACAO_SCHEMA}
    }}"""

REGRAS_ACOES = """Regras das ações:
- "como": 2 a 4 passos curtos e concretos.
- "onde_explorar": o que procurar no repositório atual (padrões, tipos de classe, pastas), sem inventar nomes de arquivo.
- "prompt": 2 a 5 frases, pronto para colar no Claude Code; termina pedindo que ele faça UMA pergunta por vez.
- Ações de entrega: "dimensao" = "P3" (explicar/aplicar o conceito naquela mudança) ou "P4" (defender a decisão
  arquitetural e as alternativas); a primeira ação de cada entrega é do tipo "explicar".
- Ações da rota e da sessão: "dimensao" = null."""

TRIAGE_SCHEMA = f"""Devolva exatamente este JSON:
{{
  "onde_esta": {{"resumo": str}},
  "aonde_quer_chegar": {{"resumo": str, "lacuna_principal": str}},
  "diagnostico_fontes": {{"conflito_curriculo_vs_realidade": str, "padrao_uso_ia_observado": str}},
  "p1_direcao_prompt": {{"nota": int|null, "base": str}},
  "skills": [
    {{
      "nome": str,
      "autoavaliacao": int|null,
      "luzia_sugere": int,
      "alvo": int,
      "evidencia": str,
      "palavras_chave": [str]
    }}
  ],
  "plano": [
    {{
      "horizonte": "trecho 1"|"trecho 2"|"trecho 3",
      "titulo": str,
      "sinal_de_progresso": str,
      "como_a_luzia_age": str,
      "acoes": [
        {ACAO_SCHEMA}
      ]
    }}
  ],
  "proximo_passo": str
}}
Quantidades: 6 skills ({SKILLS_OBRIGATORIAS}); em cada skill, 8 a 12 palavras_chave em inglês E em português que
aparecem em nomes de arquivos, código ou prompts quando a skill está em jogo (ex.: DDD -> "Domain", "Aggregate",
"ValueObject", "agregado", "objeto de valor", "subdomínio");
"autoavaliacao" copia a autoavaliação recebida (ou null).
"p1_direcao_prompt": nota 0-100 de quanto os prompts recentes da pessoa no projeto de trabalho dão direção,
restrições e critérios ao agente (vs. só delegar); "base" cita o padrão observado; null se não houver prompts.
Plano com exatamente 3 trechos, por PROGRESSO e não por datas: "trecho 1" (próximos degraus das maiores
lacunas), "trecho 2" (consolidar), "trecho 3" (o que falta para a meta); 2 a 3 ações cada. "sinal_de_progresso"
descreve uma evidência observável, nunca um prazo. Não proponha de novo feixes parecidos com os descartados.
{REGRAS_ACOES}"""

PROGRESS_SCHEMA = f"""Devolva exatamente este JSON:
{{
  "resumo_progresso": str,
  "tarefas_recentes": [
    {TAREFA_SCHEMA}
  ]
}}
4 tarefas_recentes escolhidas entre os commits recebidos; "commit" copia EXATAMENTE a mensagem do commit;
2 ações por tarefa. Considere as evidências já registradas para não repetir o que a pessoa já demonstrou.
{REGRAS_ACOES}"""

OPPORTUNITIES_SCHEMA = f"""Devolva exatamente este JSON:
{{
  "resumo_sessao": str,
  "oportunidades_tarefa_atual": [
    {OPORTUNIDADE_SCHEMA}
  ]
}}
3 oportunidades, priorizando as skills detectadas nos eventos da sessão e as maiores lacunas (alvo - nível).
{REGRAS_ACOES}"""


@dataclass
class LLMResult:
    plan: dict
    raw: str
    seconds: float
    tokens_in: int
    tokens_out: int
    model: str


def build_prompt(payload: dict, schema: str = TRIAGE_SCHEMA, intro: str | None = None) -> str:
    intro = intro or 'Evidências da triagem da pessoa desenvolvedora (já anonimizadas localmente por LGPD):'
    return intro + '\n' + json.dumps(payload, ensure_ascii=False, indent=1) + '\n\n' + schema


def call_llm(prompt: str) -> LLMResult:
    """Chama o provedor e o modelo configurados (code/luzia/modelo.py) e lê o JSON da resposta."""
    from . import modelo

    r = modelo.chamar(prompt, SYSTEM)
    return LLMResult(plan=modelo.extrair_json(r['texto']), raw=r['texto'], seconds=r['segundos'],
                     tokens_in=r['tokens_in'], tokens_out=r['tokens_out'], model=f"{r['provedor']}/{r['modelo']}")
