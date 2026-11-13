"""Leituras automáticas e do chat só cobrem o que a tela mostra, nunca o banco inteiro."""

import io
import json
import sys
from contextlib import redirect_stdout
from types import SimpleNamespace

import pytest

from luzia import banco, cli, leituras, modelo, pipeline, server

DDD = 'Domain-Driven Design (DDD)'


def _entregas(n):
    con = banco.conectar()
    try:
        with banco.transacao(con):
            for i in range(n):  # datas crescentes: a de maior i é a mais recente
                dia = f'2026-10-{(i % 28) + 1:02d}T10:00:00'
                cur = con.execute(
                    "INSERT INTO entrega (chave, titulo, inicio, fim, fonte, commits, arquivos, linhas, areas_json) "
                    "VALUES (?, ?, ?, ?, 'commit', 1, 1, 10, '[]')", (f'cm:{i}', f'Entrega {i}', dia, f'2026-{11 if i >= 28 else 10}-{(i % 28) + 1:02d}T10:00:00'))
                con.execute('INSERT INTO entrega_prisma (entrega_id, prisma, termos_json) VALUES (?, ?, ?)', (cur.lastrowid, DDD, '[]'))
    finally:
        con.close()


def _modelo(monkeypatch, chamadas):
    def fake(payload, **kw):
        chamadas.append([a['alvo'] for a in payload['alvos']])
        lt = [{'alvo': a['alvo'], 'texto': 'Leitura.'} for a in payload['alvos']]
        return SimpleNamespace(plan={'leituras': lt}, model='gemini/x'), {'quando': '2026-11-12T10:00:00', 'modelo': 'gemini/x'}
    monkeypatch.setattr(pipeline, 'run_plan', fake)
    monkeypatch.setattr(modelo, 'pronto', lambda: True)


def _rodar(monkeypatch, *argv):
    monkeypatch.setattr(sys, 'argv', ['luzia', *argv])
    buf = io.StringIO()
    with redirect_stdout(buf):
        cli.main()
    return buf.getvalue()


def test_vencidas_relevantes_sao_prismas_mais_as_n_entregas_recentes(privado):
    _entregas(40)
    con = banco.conectar()
    try:
        rel = leituras.vencidas(con, 10)
        assert len([a for a in rel if a[0] == 'entrega']) == 10 and len([a for a in rel if a[0] == 'prisma']) == 3
        assert len(leituras.vencidas(con)) == 43
        recentes = [str(r['id']) for r in con.execute('SELECT id FROM entrega ORDER BY fim DESC, id DESC LIMIT 10')]
        assert [a[1] for a in rel if a[0] == 'entrega'] == recentes
    finally:
        con.close()


def test_rodada_automatica_do_painel_so_gera_o_que_a_tela_mostra_em_ate_2_lotes(privado, monkeypatch):
    _entregas(40)
    chamadas = []
    _modelo(monkeypatch, chamadas)
    h = SimpleNamespace(_json=lambda corpo, codigo=200: resultado.update(corpo=corpo, codigo=codigo))
    resultado = {}
    estado = server.estado()
    assert estado['leituras_vencidas'] == 3 + 15  # exatamente o que a tela mostra
    server.Handler._post(h, '/api/leituras', {'auto': True})
    assert resultado['corpo']['geradas'] == 16 and len(chamadas) == 2 and all(len(c) <= 8 for c in chamadas)
    gerados = {a for c in chamadas for a in c}
    assert len(gerados) == 16 and all(a.startswith(('prisma:', 'entrega:')) for a in gerados)
    con = banco.conectar()
    try:
        assert len(leituras.vencidas(con)) == 43 - 16  # o resto do banco ficou intacto
    finally:
        con.close()


def test_botao_do_chat_conta_o_que_vai_gerar_e_todas_inclui_o_resto(privado, monkeypatch):
    _entregas(40)
    chamadas = []
    _modelo(monkeypatch, chamadas)
    assert cli.bt_leituras()['rotulo'] == 'Atualizar 13 análises'
    saida = _rodar(monkeypatch, 'leituras')
    assert '13 análises atualizadas' in saida and sum(len(c) for c in chamadas) == 13
    assert 'analises --todas' in saida and '30' in saida
    saida = _rodar(monkeypatch, 'leituras', '--todas')
    assert '30 análises atualizadas' in saida
