"""Propriedade intelectual explicável: cada dimensão diz a nota, a base e a evidência.

"Propriedade" mede quanto de uma ENTREGA é seu (P1–P4). "Luz própria", no jogo, é outra coisa: a parcela
dos seus lúmens que veio de você e não do agente.

- P1 · direção no prompt: inferida pelo modelo a partir dos prompts recentes no projeto (com justificativa);
  é geral (a mesma em todas as entregas), porque os prompts não são ligados a um commit específico.
- P2 · coesão do commit: regra fixa sobre os metadados do git (conta visível).
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
    'P2 · coesão do commit: regra fixa sobre arquivos, linhas e áreas do commit; quanto mais focado, maior (calculado).',
    'P3 · aplicação conceitual: sobe só quando você explica o conceito naquela entrega numa ação da Luzia (evidência).',
    'P4 · domínio arquitetural: sobe só quando você defende a decisão e as alternativas numa ação (evidência).',
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


def find_commit(tarefa: dict, commits: list[dict]) -> dict | None:
    alvo = (tarefa.get('commit') or tarefa.get('tarefa') or '').strip().lower()
    if not alvo:
        return None
    for c in commits:
        if (c.get('mensagem') or '').strip().lower() == alvo:
            return c
    for c in commits:
        msg = (c.get('mensagem') or '').strip().lower()
        if msg and (msg[:40] in alvo or alvo[:40] in msg):
            return c
    return None


def entrega(tarefa: dict, commits: list[dict], p1: dict | None, evidencias: list[dict]) -> dict:
    """Dimensões, índice e base de uma entrega."""
    dims: dict[str, dict | None] = {}
    if p1 and p1.get('nota') is not None:
        dims['P1'] = {'nota': int(p1['nota']), 'tipo': 'inferido · geral', 'base': p1.get('base', '')}
    else:
        dims['P1'] = None
    dims['P2'] = p2_coesao(find_commit(tarefa, commits))
    for dim in ('P3', 'P4'):
        evs = [e for e in evidencias if e.get('entrega') == tarefa.get('tarefa') and e.get('dimensao') == dim]
        if evs:
            melhor = max(evs, key=lambda e: int(e.get('nota', 0)))
            n = int(melhor.get('nota', 0))
            dims[dim] = {
                'nota': n * 25, 'tipo': 'evidência',
                'base': f"{RUBRICA.get(n, '')} — “{melhor.get('resumo', '')}” ({melhor.get('quando', '')[:10]})",
            }
        else:
            dims[dim] = None
    com_base = [d['nota'] for d in dims.values() if d]
    indice = round(sum(com_base) / len(com_base)) if com_base else None
    return {'dimensoes': dims, 'indice': indice, 'base': f'{len(com_base)} de 4 dimensões'}
