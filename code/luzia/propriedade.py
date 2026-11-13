"""Propriedade intelectual explicável: cada dimensão diz a nota, a base e a evidência.

"Propriedade" mede quanto de uma ENTREGA é seu (P1–P4). "Luz própria", no jogo, é outra coisa: a parcela
dos seus lúmens que veio de você e não do agente.

- P1 · direção no prompt: inferida pelo modelo a partir dos prompts recentes no projeto (com justificativa);
  é geral (a mesma em todas as entregas), porque os prompts não são ligados a um commit específico.
- P2 · coesão da entrega: regra fixa sobre arquivos, linhas e áreas somados da entrega no git (conta visível).
- P3 · aplicação conceitual: só existe com evidência registrada (ações "explicar/praticar" concluídas).
- P4 · domínio arquitetural: só existe com evidência registrada (ações de defesa da decisão).

Sem base, a dimensão fica sem número. O índice da entrega é a média das dimensões que têm base.
"""

from __future__ import annotations

RUBRICA = {
    0: 'não explicou',
    1: 'descreveu o que o código faz',
    2: 'explicou o porquê da decisão',
    3: 'comparou com uma alternativa',
    4: 'ligou ao conceito e aos trade-offs',
}

COMO_E_MEDIDO = [
    'P1 · direção no prompt: o modelo lê seus prompts recentes no projeto e avalia se você deu direção, restrições e critérios ao agente (inferido, geral: vale para todas as entregas).',
    'P2 · coesão: regra fixa sobre arquivos, linhas e áreas somados da entrega; quanto mais focada, maior (calculado).',
    'P3 · aplicação de conceito: sobe só quando você explica o conceito daquela entrega numa centelha da Luzia (evidência).',
    'P4 · decisão de arquitetura: sobe só quando você defende a decisão e as alternativas numa centelha (evidência).',
    'Rubrica das evidências (0–4, ×25): ' + ' · '.join(f'{k} {v}' for k, v in RUBRICA.items()) + '.',
]


def _linhas(valor) -> int:
    if isinstance(valor, (int, float)) and not isinstance(valor, bool):
        return int(valor)
    linhas_txt = str(valor if valor is not None else '+0/-0').replace('+', '').split('/-')
    try:
        return sum(int(p) for p in linhas_txt if p.strip())
    except ValueError:
        return 0


def _areas(commit: dict) -> list[str]:
    bruto = commit.get('areas')
    if bruto is None and commit.get('areas_json'):
        import json
        try:
            bruto = json.loads(commit['areas_json'])
        except ValueError:
            bruto = []
    return [str(a) for a in (bruto or []) if a]


def p2_coesao(commit: dict | None) -> dict | None:
    """Nota 0-100 de coesão de um commit, com a conta mostrada."""
    if not commit:
        return None
    linhas = _linhas(commit.get('linhas', '+0/-0'))
    arquivos = int(commit.get('arquivos', 0) or 0)
    areas = len(_areas(commit))
    pen_arq = min(40, max(0, arquivos - 5) * 4)
    pen_lin = min(30, max(0, linhas - 150) // 50 * 5)
    pen_area = 10 * max(0, areas - 2)
    nota = max(0, 100 - pen_arq - pen_lin - pen_area)
    conta = (
        f'100 − {pen_arq} ({arquivos} arquivos) − {pen_lin} ({linhas} linhas) '
        f'− {pen_area} ({areas} áreas) = {nota}'
    )
    return {'nota': nota, 'tipo': 'calculado', 'base': conta}


def p2_entrega(commits: list[dict] | None) -> dict | None:
    """Nota 0-100 de coesão aplicada à soma de arquivos e linhas e à união de áreas da entrega (conta visível)."""
    if not commits:
        return None
    arquivos = sum(int(c.get('arquivos', 0) or 0) for c in commits)
    linhas = sum(_linhas(c.get('linhas', 0)) for c in commits)
    areas = list(dict.fromkeys(a for c in commits for a in _areas(c)))
    return p2_coesao({'arquivos': arquivos, 'linhas': linhas, 'areas': areas})
