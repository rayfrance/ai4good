"""Linha de status da Luzia no rodapé do Claude Code.

Lê o JSON da sessão no stdin e devolve uma linha curta:
  ✦ Luzia · em foco · 3/6 níveis · 62% luz própria · #a3f2 em andamento
Só aparece nos repositórios autorizados; fora deles, não imprime nada.
"""

from __future__ import annotations

import json
import sys

from . import acoes, banco, jogo, observer, trajetoria


def linha(dados: dict) -> str:
    cfg = observer.config()
    cwd = str((dados.get('workspace') or {}).get('current_dir') or dados.get('cwd') or '')
    if cfg['modo'] == 'sob_demanda':
        return '✦ Luzia · fora de foco (/luzia:hoje)'
    if cwd and not observer.autorizado(cwd, cfg):
        return ''
    plan = trajetoria.plano(banco.ESPERA_CURTA_MS)
    if not plan:
        return '✦ Luzia · rode /luzia:triage'
    try:
        with trajetoria.abrir(banco.ESPERA_CURTA_MS) as con:
            r = jogo.rota(plan, con)
            andamento = jogo.avancos(con, estado='em_andamento', historico=False)
        pendentes = acoes.fila(banco.ESPERA_CURTA_MS)
    except Exception:
        return '✦ Luzia · em foco (/luzia:hoje)'
    pronto = next((s for s in r['skills'] if s['pronto'] and not s['na_meta']), None)
    foco_curto = 'em foco' if cfg['modo'] in ('ativo', 'passivo') else 'fora de foco'
    partes = [f"✦ Luzia · {foco_curto} · {r['niveis_feitos']}/{r['niveis_total']} níveis"]
    if r['lm_total']:
        partes.append(f"{r['luz_propria']}% luz própria")
    if pronto:
        partes.append(f"nível pronto: Prisma {pronto['nome'][:18]}")
    elif andamento:
        partes.append(f"#{andamento[0]['id']} em andamento")
    elif pendentes:
        partes.append(f"{len(pendentes)} na fila")
    return ' · '.join(partes)


def main() -> None:
    try:
        cru = sys.stdin.read()
        dados = json.loads(cru) if cru.strip() else {}
    except json.JSONDecodeError:
        dados = {}
    out = linha(dados)
    if out:
        print(out)


if __name__ == '__main__':
    main()
