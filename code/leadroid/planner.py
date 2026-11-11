"""Montagem dos pedidos ao modelo e leitura das respostas da Luzia."""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass

MODEL = os.environ.get('LUZIA_MODEL', 'gemini-3.5-flash-lite')

SYSTEM = """Você é a Luzia, uma líder técnica e mentora de carreira que vive como plugin dentro do agente
de código (Claude Code) e acompanha a pessoa desenvolvedora no dia a dia.

Premissa inegociável: a pessoa SEMPRE desenvolve com IA. Você nunca recomenda programar sem IA.
Você acompanha o USO EDUCADO da IA: 100% de propriedade intelectual sobre o que é entregue (saber explicar,
escolher entre alternativas, modelar o domínio, defender em code review) e o mínimo de débito técnico.

Regra de ouro da calibração:
- A AUTOAVALIAÇÃO 0-5 declarada pela pessoa é o ponto de partida de cada skill.
- Currículo (muitas vezes adaptado para uma vaga) e notas paradas no vault (não atualizadas com frequência)
  só servem para MAPEAR TÓPICOS. Nunca use essas fontes estáticas para definir ou rebaixar um nível.
- Commits e sessões recentes no agente são a memória viva: use-os para sugerir um ajuste à autoavaliação,
  explicando a evidência. Se não houver autoavaliação, diga isso e sugira a partir da memória viva.
- Metadados de commit mostram O QUE subiu com apoio do agente, não se a pessoa domina a decisão. Sem evidência
  de entendimento próprio, a propriedade intelectual é baixa e você mostra os passos para chegar a 100%.

Estilo: visual e curto. Cada texto livre tem no máximo 14 palavras. Fale em português do Brasil,
no feminino ("a Luzia"), sem jargão desnecessário. Termos [EMPRESA/PRODUTO] e [COLEGA] foram
anonimizados localmente por LGPD; mantenha-os assim. Use só as evidências fornecidas. Responda só com o JSON."""

SKILLS_OBRIGATORIAS = (
    '"Domain-Driven Design (DDD)", "Programação Agêntica e Fluxo com IA", '
    '"Arquitetura .NET / Clean Architecture", "Back-end C# / .NET e Integrações", '
    '"Front-end (JS / Razor / React)" e "Testes e Qualidade / SQL"'
)

TAREFA_SCHEMA = """{
      "tarefa": str,
      "skills": [str],
      "indice_propriedade": int (0-100),
      "p1_direcao_prompt": int (0-100),
      "p2_coesao_commit": int (0-100),
      "p3_aplicacao_conceitual": int (0-100),
      "p4_dominio_arquitetural": int (0-100),
      "risco_debito_tecnico": str,
      "passos_para_100": [{"passo": str, "ganho": int}]
    }"""

OPORTUNIDADE_SCHEMA = """{
      "skill_alvo": str,
      "gatilho": str,
      "alerta": str,
      "teoria_na_pratica": str,
      "como_praticar_com_agente": str
    }"""

TRIAGE_SCHEMA = f"""Devolva exatamente este JSON:
{{
  "onde_esta": {{"resumo": str}},
  "aonde_quer_chegar": {{"resumo": str, "lacuna_principal": str}},
  "diagnostico_fontes": {{"conflito_curriculo_vs_realidade": str, "padrao_uso_ia_observado": str}},
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
  "tarefas_recentes": [
    {TAREFA_SCHEMA}
  ],
  "oportunidades_tarefa_atual": [
    {OPORTUNIDADE_SCHEMA}
  ],
  "plano": [
    {{
      "horizonte": "90 dias"|"6 meses"|"12 meses",
      "titulo": str,
      "passos": [str],
      "como_a_luzia_age": str,
      "sinal_de_progresso": str
    }}
  ],
  "proximo_passo": str
}}
Quantidades: 6 skills ({SKILLS_OBRIGATORIAS}); em cada skill, 6 a 10 palavras_chave em inglês que aparecem em
nomes de arquivos ou código quando a skill está em jogo (ex.: DDD -> "Domain", "Aggregate", "ValueObject");
"autoavaliacao" copia a autoavaliação recebida (ou null); 4 tarefas_recentes escolhidas entre os commits,
cada uma com 2 ou 3 passos_para_100 cujos ganhos somam (100 - indice_propriedade);
3 oportunidades_tarefa_atual; plano com exatamente 3 itens: "90 dias", "6 meses" e "12 meses", até 3 passos cada."""

PROGRESS_SCHEMA = f"""Devolva exatamente este JSON:
{{
  "resumo_progresso": str,
  "tarefas_recentes": [
    {TAREFA_SCHEMA}
  ]
}}
4 tarefas_recentes escolhidas entre os commits recebidos; 2 ou 3 passos_para_100 cujos ganhos somam
(100 - indice_propriedade)."""

OPPORTUNITIES_SCHEMA = f"""Devolva exatamente este JSON:
{{
  "resumo_sessao": str,
  "oportunidades_tarefa_atual": [
    {OPORTUNIDADE_SCHEMA}
  ]
}}
3 oportunidades, priorizando as skills detectadas nos eventos da sessão e as maiores lacunas (alvo - autoavaliacao)."""


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


def call_llm(prompt: str, model: str = MODEL) -> LLMResult:
    from google import genai
    from google.genai import types

    client = genai.Client(
        api_key=os.environ['GEMINI_API_KEY'],
        http_options=types.HttpOptions(timeout=30_000),
    )
    models = [model] + [m for m in ('gemini-2.5-flash',) if m != model]
    last_err = None
    for m in models:
        try:
            t0 = time.perf_counter()
            resp = client.models.generate_content(
                model=m,
                contents=prompt,
                config=types.GenerateContentConfig(
                    system_instruction=SYSTEM,
                    temperature=0.1,
                    response_mime_type='application/json',
                ),
            )
            seconds = time.perf_counter() - t0
            raw = resp.text or ''
            usage = resp.usage_metadata
            return LLMResult(
                plan=json.loads(raw),
                raw=raw,
                seconds=seconds,
                tokens_in=getattr(usage, 'prompt_token_count', 0) or 0,
                tokens_out=getattr(usage, 'candidates_token_count', 0) or 0,
                model=m,
            )
        except Exception as e:
            last_err = e
            continue
    raise RuntimeError(f'Falha nos modelos {models}: {last_err}')
