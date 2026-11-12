"""Linha de status da Luzia no Claude Code (`statusLine` em ~/.claude/settings.json). Local, rápida, sem modelo.

Só aparece nos repositórios autorizados para o observador; fora deles fica em silêncio.
Mostra a skill mais perto do próximo degrau (ou a que está pronta para subir) e o que há para retomar.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from luzia import arquivos, jogo, trajetoria  # noqa: E402

LARANJA, LILAS, APAGADO, FIM = '\033[38;5;208m', '\033[38;5;183m', '\033[2m', '\033[0m'


def autorizado(cwd: str) -> bool:
    roots = arquivos.ler_json(arquivos.PRIVATE / 'observer.json', {}).get('autorizados') or []
    cwd_n = cwd.replace('\\', '/').lower()
    return any(cwd_n.startswith(r.replace('\\', '/').lower()) for r in roots)


def barra(lm: int, limiar: int, largura: int = 6) -> str:
    cheio = min(largura, round(largura * lm / limiar)) if limiar else 0
    return '▰' * cheio + '▱' * (largura - cheio)


def linha(evento: dict) -> str:
    cwd = (evento.get('workspace') or {}).get('current_dir') or evento.get('cwd') or ''
    if not autorizado(cwd):
        return ''
    plan = trajetoria.plano()
    if not plan:
        return f'{LARANJA}✦ Luzia{FIM} {APAGADO}rode /luzia:triage{FIM}'
    r = jogo.rota(plan)
    abertas = [s for s in r['skills'] if not s['na_meta']]
    pronta = next((s for s in abertas if s['pronto']), None)
    partes = [f'{LARANJA}✦ Luzia{FIM}']
    if pronta:
        partes.append(f"{LARANJA}{pronta['nome'].split('(')[0].strip()} pronta para subir{FIM} {APAGADO}/luzia:hoje{FIM}")
    elif abertas:
        s = max(abertas, key=lambda x: (x['lm'], -x['nivel']))
        cor = LARANJA if s['luz_propria'] >= 40 else LILAS
        partes.append(f"{s['nome'].split('(')[0].strip()} {cor}{barra(s['lm'], s['limiar'])}{FIM} {s['lm']}/{s['limiar']} lm")
    partes.append(f"{APAGADO}{r['degraus_feitos']}/{r['degraus_total']} degraus{FIM}")
    andamento = len(jogo.em_andamento())
    if andamento:
        partes.append(f'{APAGADO}{andamento} em andamento{FIM}')
    return ' · '.join(partes)


def main() -> None:
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    try:
        evento = json.load(sys.stdin)
    except Exception:
        evento = {}
    try:
        print(linha(evento))
    except Exception as e:  # a linha de status nunca pode quebrar o agente
        arquivos.registrar_erro('statusline', e)


if __name__ == '__main__':
    main()
