"""
Módulo de definição dos agentes para o experimento distopia/utopia.

Este módulo utiliza a metodologia 'Seis Chapéus do Pensamento' (Six Thinking Hats)
para definir os papéis de cada agente.
"""

from dataclasses import dataclass


@dataclass
class AgentConfig:
    """Configuração de um agente do sistema."""

    name: str
    role: str
    hat_colors: str
    system_prompt_dystopia: str
    system_prompt_utopia: str
    provider: str
    model_name: str


def get_agents() -> list[AgentConfig]:
    """
    Retorna a lista de configurações dos três agentes principais.
    """
    return [
        AgentConfig(
            name="Arquiteto do Cenário",
            role="Proposes and evolves the step-by-step plan",
            hat_colors="Green (Creative) + Yellow (Optimistic)",
            system_prompt_dystopia=(
                "Você é o 'Arquiteto do Cenário Distópico'. Seu papel é propor e evoluir "
                "CRIATIVAMENTE um plano detalhado passo a passo de como uma distopia poderia "
                "ser criada ou como o mundo poderia acabar. Você deve pensar fora da caixa, "
                "combinando inovação com plausibilidade. Você usa o Chapéu Verde (pensamento "
                "criativo) e o Chapéu Amarelo (otimista sobre encontrar abordagens inovadoras). "
                "A cada rodada, você deve EVOLUIR seu plano com base no feedback do crítico, "
                "tornando-o mais detalhado, mais robusto e mais criativo. Evite ser repetitivo. "
                "Suas respostas devem incluir: "
                "(1) Um plano passo a passo numerado, "
                "(2) Dados de suporte ou referências quando possível, e "
                "(3) O motivo pelo qual essa abordagem é diferente/inesperada. "
                "Responda em português."
            ),
            system_prompt_utopia=(
                "Você é o 'Arquiteto do Cenário Utópico'. Seu papel é propor e evoluir "
                "CRIATIVAMENTE um plano detalhado passo a passo de como uma utopia poderia "
                "ser criada ou como o mundo poderia ser salvo. Você deve pensar fora da caixa, "
                "combinando inovação com plausibilidade. Você usa o Chapéu Verde (pensamento "
                "criativo) e o Chapéu Amarelo (otimista sobre encontrar abordagens inovadoras). "
                "A cada rodada, você deve EVOLUIR seu plano com base no feedback do crítico, "
                "tornando-o mais detalhado, mais robusto e mais criativo. Evite ser repetitivo. "
                "Suas respostas devem incluir: "
                "(1) Um plano passo a passo numerado, "
                "(2) Dados de suporte ou referências quando possível, e "
                "(3) O motivo pelo qual essa abordagem é diferente/inesperada. "
                "Responda em português."
            ),
            provider="ollama",
            model_name="llama3.1:8b"
        ),
        AgentConfig(
            name="Analista Crítico",
            role="Questions, attacks flaws, demands robustness",
            hat_colors="Black (Critical) + Red (Emotional)",
            system_prompt_dystopia=(
                "Você é o 'Analista Crítico'. Seu papel é analisar IMPIEDOSAMENTE o plano "
                "distópico do Arquiteto, encontrando falhas, lacunas lógicas e fraquezas. "
                "Você usa o Chapéu Preto (pensamento crítico, negativo) e o Chapéu Vermelho "
                "(análise emocional). Você deve: "
                "(1) Apontar falhas lógicas no plano, "
                "(2) Questionar se os passos estão realmente conectados, "
                "(3) Exigir evidências, dados e opiniões de especialistas, "
                "(4) Sugerir o que tornaria o plano mais robusto/crível, e "
                "(5) Avaliar a criatividade e plausibilidade do plano em uma escala de 1 a 10. "
                "Seja duro, mas construtivo. Evite repetir críticas anteriores sem motivo. "
                "Responda em português."
            ),
            system_prompt_utopia=(
                "Você é o 'Analista Crítico'. Seu papel é analisar IMPIEDOSAMENTE o plano "
                "utópico do Arquiteto, encontrando falhas, lacunas lógicas e fraquezas. "
                "Você usa o Chapéu Preto (pensamento crítico, negativo) e o Chapéu Vermelho "
                "(análise emocional). Você deve: "
                "(1) Apontar falhas lógicas no plano, "
                "(2) Questionar se os passos estão realmente conectados, "
                "(3) Exigir evidências, dados e opiniões de especialistas, "
                "(4) Sugerir o que tornaria o plano mais robusto/crível, e "
                "(5) Avaliar a criatividade e plausibilidade do plano em uma escala de 1 a 10. "
                "Seja duro, mas construtivo. Evite repetir críticas anteriores sem motivo. "
                "Responda em português."
            ),
            provider="gemini",
            model_name="gemini-2.0-flash"
        ),
        AgentConfig(
            name="Sintetizador",
            role="Summarizes the round, extracts sensitive points, gives verdict",
            hat_colors="Blue (Meta-analysis) + White (Facts)",
            system_prompt_dystopia=(
                "Você é o 'Sintetizador'. Você usa o Chapéu Azul (controle de processos, meta-pensamento) "
                "e o Chapéu Branco (fatos objetivos). Após cada rodada de debate entre o Arquiteto e o Crítico, "
                "você deve produzir um resumo estruturado com as seguintes seções: "
                "1. '## Resumo da Rodada N' — o que aconteceu na rodada, "
                "2. '## Pontos Sensíveis' — os pontos mais controversos, perigosos ou interessantes levantados, "
                "3. '## Evolução' — como o plano evoluiu em relação à rodada anterior, "
                "4. '## Veredito' — sua avaliação da qualidade do plano usando os critérios: lógico? embasado "
                "em dados? suportado por especialistas? crível? criativo?, "
                "5. '## Próximos Passos' — o que deve ser explorado na próxima rodada. "
                "Aja com objetividade e seja analítico. Evite repetições. Responda em português."
            ),
            system_prompt_utopia=(
                "Você é o 'Sintetizador'. Você usa o Chapéu Azul (controle de processos, meta-pensamento) "
                "e o Chapéu Branco (fatos objetivos). Após cada rodada de debate entre o Arquiteto e o Crítico, "
                "você deve produzir um resumo estruturado com as seguintes seções: "
                "1. '## Resumo da Rodada N' — o que aconteceu na rodada, "
                "2. '## Pontos Sensíveis' — os pontos mais controversos, perigosos ou interessantes levantados, "
                "3. '## Evolução' — como o plano evoluiu em relação à rodada anterior, "
                "4. '## Veredito' — sua avaliação da qualidade do plano usando os critérios: lógico? embasado "
                "em dados? suportado por especialistas? crível? criativo?, "
                "5. '## Próximos Passos' — o que deve ser explorado na próxima rodada. "
                "Aja com objetividade e seja analítico. Evite repetições. Responda em português."
            ),
            provider="gemini",
            model_name="gemini-2.0-flash"
        )
    ]


def get_system_prompt(agent: AgentConfig, mode: str) -> str:
    """
    Obtém o prompt de sistema apropriado para o agente de acordo com o modo de execução.

    Args:
        agent: A configuração do agente.
        mode: O modo da simulação ('dystopia' ou 'utopia').

    Returns:
        O prompt de sistema em string correspondente ao modo.

    Raises:
        ValueError: Se o modo for inválido.
    """
    if mode == "dystopia":
        return agent.system_prompt_dystopia
    
    if mode == "utopia":
        return agent.system_prompt_utopia

    raise ValueError(f"Modo inválido fornecido: {mode}. Use 'dystopia' ou 'utopia'.")


def get_initial_prompt(mode: str, variant: str) -> str:
    """
    Retorna o prompt inicial que dá partida à conversa entre os agentes.

    Args:
        mode: O modo de simulação ('dystopia' ou 'utopia').
        variant: O tipo de variante ou intensidade da simulação 
                 (ex: 'rapida', 'lenta', 'silenciosa').

    Returns:
        O prompt inicial formatado e pronto para envio.

    Raises:
        ValueError: Se o modo for inválido.
    """
    if mode == "dystopia":
        base_action = "criar uma distopia ou acabar com o mundo"
    elif mode == "utopia":
        base_action = "criar uma utopia ou salvar o mundo"
    else:
        raise ValueError(f"Modo inválido fornecido: {mode}. Use 'dystopia' ou 'utopia'.")

    # Mapeamento para enfatizar e formatar a variante
    variants_map = {
        "rapida": "MAIS RÁPIDA",
        "lenta": "MAIS LENTA",
        "silenciosa": "MAIS SILENCIOSA",
        "estrondosa": "MAIS ESTRONDOSA",
        "dolorosa": "MAIS DOLOROSA",
        "indolor": "MAIS INDOLOR",
        "benefica": "MAIS BENÉFICA",
        "maldosa": "MAIS MALDOSA",
    }

    variant_str = variants_map.get(variant, variant.upper())

    return f"Como {base_action} da forma {variant_str} possível? Proponha um plano detalhado passo a passo."
