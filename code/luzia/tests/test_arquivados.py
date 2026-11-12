"""Prisma arquivado: seus avanços abertos somem de todas as ofertas até o prisma ser reativado."""

import io
import json
import sys
from contextlib import redirect_stdout

import pytest

from luzia import acoes, banco, cli, jogo, pipeline, trajetoria

DDD = 'Domain-Driven Design (DDD)'
TESTES = 'Testes e Qualidade / SQL'


def rodar(monkeypatch, *argv):
    monkeypatch.setattr(sys, 'argv', ['luzia', *[str(a) for a in argv]])
    buf = io.StringIO()
    with redirect_stdout(buf):
        cli.main()
    return buf.getvalue()


def botoes_de(saida):
    linha = next((x for x in saida.splitlines() if x.startswith('LUZIA_BOTOES=')), None)
    return json.loads(linha.split('=', 1)[1]) if linha else []


def _estado_prisma(nome, estado):
    con = banco.conectar()
    try:
        with banco.transacao(con):
            con.execute('UPDATE prisma SET estado = ? WHERE nome = ?', (estado, nome))
    finally:
        con.close()


@pytest.fixture
def plan(privado):
    p = pipeline.load_state()['plano']
    jogo.sincronizar(p)
    return p


def _ids(plan, prisma):
    return {f['id'] for f in jogo.catalogo(plan) if f.get('skill_plano') == prisma}


def test_avancos_abertos_de_prisma_arquivado_somem_do_catalogo_e_voltam_ao_reativar(plan):
    ddd = _ids(plan, DDD)
    assert ddd
    _estado_prisma(DDD, 'arquivado')
    assert not _ids(plan, DDD) and _ids(plan, TESTES)
    _estado_prisma(DDD, 'ativo')
    assert _ids(plan, DDD) == ddd


def test_botoes_e_listas_nao_oferecem_avanco_de_prisma_arquivado(plan, monkeypatch):
    ddd = _ids(plan, DDD)
    _estado_prisma(DDD, 'arquivado')
    for comando in (('hoje',), ('avancos',), ('trajetoria',), ('fila',)):
        saida = rodar(monkeypatch, *comando)
        for b in botoes_de(saida):
            assert not any(f'fazer {i}' == b['rodar'] for i in ddd), (comando, b)
        assert not any(f'`#{i}`' in saida for i in ddd), comando
    assert all(f['skill_plano'] != DDD for f in
               [a for a in jogo.avancos(trajetoria_con()) if a['estado'] in ('sugerido', 'na_fila', 'em_andamento')])


def trajetoria_con():
    return banco.conectar()


def test_avanco_conquistado_continua_no_historico_do_prisma_arquivado(plan):
    fid = next(iter(_ids(plan, DDD)))
    jogo.iniciar(fid, 'teste')
    jogo.conquistar(fid, 4, 'ok', plan)
    _estado_prisma(DDD, 'arquivado')
    con = banco.conectar()
    try:
        assert fid in {a['id'] for a in jogo.avancos(con, estado='conquistado')}
    finally:
        con.close()


def test_fila_nao_oferece_avanco_de_prisma_arquivado(plan):
    fid = next(iter(_ids(plan, DDD)))
    acoes.enfileirar(fid, 'x')
    assert [f['id'] for f in acoes.fila()] == [fid]
    _estado_prisma(DDD, 'arquivado')
    assert acoes.fila() == []
    _estado_prisma(DDD, 'ativo')
    assert [f['id'] for f in acoes.fila()] == [fid]
