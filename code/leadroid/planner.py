"""Montagem do pedido ao modelo e leitura do plano de carreira."""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass

MODEL = os.environ.get('LuzIA_MODEL', 'gemini-3.5-flash-lite')

SYSTEM = """Você é o LuzIA, uma líder técnica e mentora que funciona como plugin dentro do agente de código
(Claude Code, Codex, Cursor, Antigravity) e acompanha a carreira da pessoa desenvolvedora.

Premissa inegociável: a pessoa SEMPRE desenvolve com IA. Você não recomenda programar sem IA.
O que você acompanha é o USO EDUCADO da IA: a pessoa precisa ter propriedade intelectual sobre o que
constrói (saber explicar decisões, escolher entre alternativas, modelar o domínio e defender no quadro
ou em code review) e adquirir novas habilidades no processo rumo ao próximo nível de carreira.

Regras:
- Use apenas as evidências fornecidas (declaração da triagem, currículo, GitHub, histórico compartilhado
  entre as IAs com notas de estudo/impressões e metadados de commits). Não invente empresas, cargos ou datas.
- Quando houver divergência entre o currículo (ex.: adaptado para vaga) e a declaração real ou as notas de
  estudo do histórico compartilhado (ex.: estudando o Capítulo 1 de DDD com dúvidas sobre domínio vs.
  subdomínio), priorize a situação real declarada e as notas de estudo para calibrar o nível atual da skill.
  Se não houver histórico compartilhado, avalie apenas pelo que está no currículo e nos commits.
- Metadados de commit mostram O QUE foi entregue com apoio do agente, não QUEM decidiu a arquitetura nem se
  a pessoa domina o código gerado. Quando não houver evidência de entendimento próprio daquela entrega,
  marque a propriedade como "desconhecida" ou "baixa" e formule a pergunta técnica exata que um líder
  faria para validar a propriedade intelectual.
- Termos como [EMPRESA/PRODUTO] e [COLEGA] foram anonimizados localmente por LGPD; mantenha-os assim.
- Responda em português do Brasil, de forma direta, só com o JSON pedido."""

SCHEMA_HINT = """Devolva exatamente este JSON:
{
  "onde_esta": {"resumo": str, "evidencias": [str]},
  "aonde_quer_chegar": {"resumo": str, "lacuna_principal": str},
  "diagnostico_fontes": {
    "conflito_curriculo_vs_realidade": str,
    "padrao_uso_ia_observado": str
  },
  "skills": [
    {
      "nome": str,
      "atual": int,
      "alvo": int,
      "evidencia": str,
      "fonte": "curriculo"|"github"|"commits"|"historico_ia"|"triagem"
    }
  ],
  "tarefas_recentes": [
    {
      "tarefa": str,
      "skills": [str],
      "propriedade": "alta"|"media"|"baixa"|"desconhecida",
      "por_que": str,
      "pergunta_do_lider": str
    }
  ],
  "oportunidades_tarefa_atual": [
    {
      "skill_alvo": str,
      "como_praticar_com_agente": str,
      "evitar_delegacao_cega": str
    }
  ],
  "plano": [
    {
      "horizonte": "30 dias"|"90 dias"|"6 meses"|"12 meses",
      "acao": str,
      "uso_educado_da_ia": str,
      "sinal_de_progresso": str
    }
  ],
  "proximo_passo": str
}
Regras de quantidade: 6 skills (incluindo obrigatoriamente "Domain-Driven Design (DDD)",
"Programação Agêntica e Fluxo com IA", "Arquitetura .NET / Clean Architecture",
"Back-end C# / .NET e Integrações", "Front-end (JS / Razor / React)" e "Testes e Qualidade / SQL");
5 tarefas_recentes escolhidas entre os commits/sessões; 3 oportunidades_tarefa_atual; 3 itens no plano."""


@dataclass
class LLMResult:
    plan: dict
    raw: str
    seconds: float
    tokens_in: int
    tokens_out: int
    model: str


def build_prompt(payload: dict) -> str:
    return (
        'Evidências da triagem da pessoa desenvolvedora (já anonimizadas localmente por LGPD):\n'
        + json.dumps(payload, ensure_ascii=False, indent=1)
        + '\n\n' + SCHEMA_HINT
    )


def call_llm(prompt: str, model: str = MODEL) -> LLMResult:
    from google import genai
    from google.genai import types

    client = genai.Client(
        api_key=os.environ['GEMINI_API_KEY'],
        http_options=types.HttpOptions(timeout=25_000),
    )
    models = [model] + [m for m in ('gemini-2.5-flash', 'gemini-3.5-flash-lite') if m != model]
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
