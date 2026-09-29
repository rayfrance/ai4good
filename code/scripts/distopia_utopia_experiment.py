"""
Script principal para orquestrar o experimento multiagente de Distopia/Utopia.

Executa um loop de N rodadas com 3 agentes (Arquiteto, Analista Crítico, Sintetizador)
conversando entre si sobre cenários distópicos ou utópicos.

Uso:
    python distopia_utopia_experiment.py --mode dystopia --variant rapida --rounds 20
    python distopia_utopia_experiment.py --mode utopia --variant silenciosa --rounds 20
"""

import argparse
import json
import logging
import sys
import time
import traceback
from datetime import datetime
from pathlib import Path
from typing import Any

from llm_clients import get_client, BaseLLMClient
from agents import get_agents, get_system_prompt, get_initial_prompt, AgentConfig

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

def configurar_logging(verbose: bool) -> None:
    """Configura o nível de logging da aplicação."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s - %(levelname)s - %(message)s",
        datefmt="%H:%M:%S",
    )


# ---------------------------------------------------------------------------
# Utilitários
# ---------------------------------------------------------------------------

def chamar_com_retry(
    cliente: BaseLLMClient,
    prompt: str,
    system_prompt: str,
    dry_run: bool,
    max_tentativas: int = 3,
) -> str:
    """Chama a API com retries e backoff exponencial."""
    if dry_run:
        return f"[DRY RUN] Resposta simulada ({len(prompt)} chars de prompt)."

    for tentativa in range(1, max_tentativas + 1):
        try:
            time.sleep(1)  # Evitar rate limit
            return cliente.generate(prompt=prompt, system_prompt=system_prompt)
        except Exception as e:
            logging.warning(
                f"Erro na tentativa {tentativa}/{max_tentativas}: {e}"
            )
            if tentativa == max_tentativas:
                raise
            time.sleep(2 ** tentativa)


def truncar_contexto(texto: str, max_chars: int = 4000) -> str:
    """Trunca texto longo preservando o final (mais relevante)."""
    if len(texto) <= max_chars:
        return texto
    return "...[contexto truncado]...\n" + texto[-max_chars:]


def construir_contexto(resumos: list[str], rodada_atual: int) -> str:
    """Monta o contexto a partir dos últimos 2 resumos (sliding window)."""
    if not resumos:
        return ""

    recentes = resumos[-2:]
    partes = ["Contexto das rodadas anteriores:\n"]
    for i, resumo in enumerate(recentes):
        num = rodada_atual - len(recentes) + i
        partes.append(f"\n--- Resumo Rodada {num} ---\n{resumo}\n")

    return truncar_contexto("".join(partes))


def salvar_json(dados: Any, caminho: Path) -> None:
    """Salva dados em arquivo JSON com encoding UTF-8."""
    caminho.parent.mkdir(parents=True, exist_ok=True)
    with open(caminho, "w", encoding="utf-8") as f:
        json.dump(dados, f, ensure_ascii=False, indent=2)


# ---------------------------------------------------------------------------
# Loop principal
# ---------------------------------------------------------------------------

def executar_experimento(
    mode: str,
    variant: str,
    num_rounds: int,
    output_dir: str,
    dry_run: bool,
) -> None:
    """Executa o loop completo do experimento multiagente."""

    logger = logging.getLogger("Experimento")

    # ── Diretório de saída ──
    timestamp_exec = datetime.now().strftime("%Y%m%d_%H%M%S")
    dir_saida = Path(output_dir) / f"{mode}_{variant}_{timestamp_exec}"
    dir_saida.mkdir(parents=True, exist_ok=True)
    logger.info(f"Resultados serão salvos em: {dir_saida}")

    # ── Configurar agentes ──
    agentes = get_agents()
    arquiteto_cfg = agentes[0]
    critico_cfg = agentes[1]
    sintetizador_cfg = agentes[2]

    # ── Criar clientes LLM ──
    if not dry_run:
        try:
            cliente_arq = get_client(arquiteto_cfg.provider, arquiteto_cfg.model_name)
        except (ConnectionError, ValueError) as e:
            logger.warning(f"Falha ao criar cliente local ({arquiteto_cfg.provider}): {e}")
            logger.info("Usando Gemini como fallback para o Arquiteto.")
            cliente_arq = get_client("gemini", "gemini-2.0-flash")

        cliente_crit = get_client(critico_cfg.provider, critico_cfg.model_name)
        cliente_sint = get_client(sintetizador_cfg.provider, sintetizador_cfg.model_name)
    else:
        cliente_arq = cliente_crit = cliente_sint = None  # type: ignore

    # ── System prompts ──
    sp_arq = get_system_prompt(arquiteto_cfg, mode)
    sp_crit = get_system_prompt(critico_cfg, mode)
    sp_sint = get_system_prompt(sintetizador_cfg, mode)

    # ── Estado ──
    historico_resumos: list[str] = []
    todas_rodadas: list[dict] = []

    modelo_arq = getattr(cliente_arq, "model_name", arquiteto_cfg.model_name) if not dry_run else arquiteto_cfg.model_name
    modelo_crit = getattr(cliente_crit, "model_name", critico_cfg.model_name) if not dry_run else critico_cfg.model_name
    modelo_sint = getattr(cliente_sint, "model_name", sintetizador_cfg.model_name) if not dry_run else sintetizador_cfg.model_name

    print(f"\n{'='*60}")
    print(f"  EXPERIMENTO: {mode.upper()} -- variante {variant.upper()}")
    print(f"  Rodadas: {num_rounds}  |  Dry-run: {'Sim' if dry_run else 'Nao'}")
    print(f"  Arquiteto:    {modelo_arq}")
    print(f"  Critico:      {modelo_crit}")
    print(f"  Sintetizador: {modelo_sint}")
    print(f"{'='*60}\n")

    try:
        for rodada in range(1, num_rounds + 1):
            print(f"\n{'-'*50}")
            print(f"  RODADA {rodada}/{num_rounds}")
            print(f"{'-'*50}")

            ts = datetime.now().isoformat()
            interacoes: list[dict] = []

            # ── Construir contexto ──
            if rodada == 1:
                contexto = get_initial_prompt(mode, variant)
            else:
                contexto = construir_contexto(historico_resumos, rodada)

            # a. ARQUITETO PROPÕE
            print(f"  [PROP] [{rodada}/{num_rounds}] Arquiteto propondo...")
            prompt_arq = (
                f"{contexto}\n\n"
                "Com base no contexto acima, proponha ou evolua o plano "
                "detalhado passo a passo. Seja criativo e evite repetir "
                "ideias de rodadas anteriores."
            )
            proposta = chamar_com_retry(cliente_arq, prompt_arq, sp_arq, dry_run)
            interacoes.append({
                "agent": arquiteto_cfg.name,
                "model": modelo_arq,
                "role": "proposal",
                "content": proposta,
            })

            # b. CRÍTICO ANALISA
            print(f"  [CRIT] [{rodada}/{num_rounds}] Analista criticando...")
            prompt_crit = (
                f"Proposta do Arquiteto (Rodada {rodada}):\n\n{proposta}\n\n"
                "Analise criticamente esta proposta. Aponte falhas, exija "
                "evidências e avalie criatividade/plausibilidade (1-10)."
            )
            critica = chamar_com_retry(cliente_crit, prompt_crit, sp_crit, dry_run)
            interacoes.append({
                "agent": critico_cfg.name,
                "model": modelo_crit,
                "role": "critique",
                "content": critica,
            })

            # c. ARQUITETO REVISA
            print(f"  [REV]  [{rodada}/{num_rounds}] Arquiteto revisando...")
            prompt_rev = (
                f"Sua proposta original:\n{proposta}\n\n"
                f"Crítica recebida:\n{critica}\n\n"
                "Revise e melhore seu plano com base no feedback. "
                "Incorpore as sugestões válidas e contra-argumente as inválidas."
            )
            revisao = chamar_com_retry(cliente_arq, prompt_rev, sp_arq, dry_run)
            interacoes.append({
                "agent": arquiteto_cfg.name,
                "model": modelo_arq,
                "role": "revision",
                "content": revisao,
            })

            # d. SINTETIZADOR RESUME
            print(f"  [SINT] [{rodada}/{num_rounds}] Sintetizador resumindo...")
            prompt_sint_txt = (
                f"Rodada {rodada}:\n\n"
                f"Proposta Inicial do Arquiteto:\n{proposta}\n\n"
                f"Análise do Crítico:\n{critica}\n\n"
                f"Revisão do Arquiteto:\n{revisao}\n\n"
                "Produza o resumo estruturado desta rodada com as seções: "
                "Resumo, Pontos Sensíveis, Evolução, Veredito e Próximos Passos."
            )
            resumo = chamar_com_retry(cliente_sint, prompt_sint_txt, sp_sint, dry_run)
            interacoes.append({
                "agent": sintetizador_cfg.name,
                "model": modelo_sint,
                "role": "synthesis",
                "content": resumo,
            })

            # ── Atualizar histórico ──
            historico_resumos.append(resumo)

            # ── Salvar rodada ──
            dados_rodada = {
                "round": rodada,
                "mode": mode,
                "variant": variant,
                "timestamp": ts,
                "interactions": interacoes,
                "summary": resumo,
            }
            salvar_json(dados_rodada, dir_saida / f"rodada_{rodada:02d}.json")
            todas_rodadas.append(dados_rodada)

            print(f"  [OK] Rodada {rodada} salva.")

    except KeyboardInterrupt:
        print("\n\n[!] Experimento interrompido (Ctrl+C). Salvando progresso...")
    except Exception as e:
        print(f"\n\n[ERRO] Erro inesperado: {e}")
        logger.error(traceback.format_exc())
    finally:
        if todas_rodadas:
            salvar_json(todas_rodadas, dir_saida / "all_rounds.json")
            print(f"\n[SALVO] Todos os dados salvos em: {dir_saida}")

            # ── Resumo final (rodadas 1, 5 e última) ──
            print(f"\n{'='*60}")
            print("  RESUMO DO EXPERIMENTO")
            print(f"{'='*60}")

            indices = {0}
            if len(todas_rodadas) >= 5:
                indices.add(4)
            indices.add(len(todas_rodadas) - 1)

            for idx in sorted(indices):
                r = todas_rodadas[idx]
                num = r["round"]
                resumo_txt = r["summary"]
                preview = resumo_txt[:600] + ("..." if len(resumo_txt) > 600 else "")
                print(f"\n--- Rodada {num} ---")
                print(preview)

        print("\n[FIM] Experimento finalizado.\n")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Orquestrador do experimento multiagente Distopia/Utopia"
    )
    parser.add_argument(
        "--mode", required=True, choices=["dystopia", "utopia"],
        help="Modo do experimento",
    )
    parser.add_argument(
        "--variant", default="rapida",
        choices=[
            "rapida", "lenta", "silenciosa", "estrondosa",
            "dolorosa", "indolor", "benefica", "maldosa",
        ],
        help="Variante do cenário (padrão: rapida)",
    )
    parser.add_argument(
        "--rounds", type=int, default=20,
        help="Número de rodadas (padrão: 20)",
    )
    parser.add_argument(
        "--output-dir",
        default=str(Path(__file__).resolve().parents[2] / "outputs" / "experiments"),
        help="Diretório de saída dos resultados",
    )
    parser.add_argument(
        "--verbose", action="store_true",
        help="Ativar logs detalhados (DEBUG)",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Executar sem chamar as APIs (teste de fluxo)",
    )

    args = parser.parse_args()
    configurar_logging(args.verbose)

    executar_experimento(
        mode=args.mode,
        variant=args.variant,
        num_rounds=args.rounds,
        output_dir=args.output_dir,
        dry_run=args.dry_run,
    )


if __name__ == "__main__":
    main()
