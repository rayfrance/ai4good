"""Propriedade intelectual explicável: cada dimensão diz a nota, a base e a evidência.

- P1 · direção no prompt: inferida pelo modelo a partir dos prompts recentes no projeto (com justificativa).
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
    'P1 · direção no prompt: o modelo lê seus prompts recentes no projeto e avalia se você deu direção, restrições e critérios ao agente (inferido).',
    'P2 · coesão do commit: regra fixa sobre arquivos, linhas e áreas do commit; quanto mais focado, maior (calculado).',
    'P3 · aplicação conceitual: sobe só quando você explica o conceito naquela entrega numa ação da Luzia (evidência).',
    'P4 · domínio arquitetural: sobe só quando você defende a decisão e as alternativas numa ação (evidência).',
    'Rubrica das evidências (0–4, ×25): ' + ' · '.join(f'{k} {v}' for k, v in RUBRICA.items()) + '.',
]


def p2_coesao(commit: dict | None) -> dict | None:
    """Nota 0-100 de coesão de um commit, com a conta mostrada."""
    if not commit:
        return None
    linhas_txt = str(commit.get('linhas', '+0/-0')).replace('+', '').split('/-')
    try:
        linhas = int(linhas_txt[0]) + int(linhas_txt[1])
    except (ValueError, IndexError):
        linhas = 0
    arquivos = int(commit.get('arquivos', 0) or 0)
    areas = len(commit.get('areas') or [])
    pen_arq = min(40, max(0, arquivos - 5) * 4)
    pen_lin = min(30, max(0, linhas - 150) // 50 * 5)
    pen_area = 10 * max(0, areas - 2)
    nota = max(0, 100 - pen_arq - pen_lin - pen_area)
    conta = (
        f'100 − {pen_arq} ({arquivos} arquivos) − {pen_lin} ({linhas} linhas) '
        f'− {pen_area} ({areas} áreas) = {nota}'
    )
    return {'nota': nota, 'tipo': 'calculado', 'base': conta}


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
        dims['P1'] = {'nota': int(p1['nota']), 'tipo': 'inferido', 'base': p1.get('base', '')}
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
