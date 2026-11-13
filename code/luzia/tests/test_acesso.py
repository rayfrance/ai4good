"""Entrada herdada do agente (`acesso.py`): link de uso único e sessões de 30 dias no banco privado; relógio injetável."""

from __future__ import annotations

import hashlib
import json

import pytest

from luzia import acesso, banco

DIA = 24 * 3600


class Relogio:
    def __init__(self, t: float = 1_800_000_000.0):
        self.t = t

    def __call__(self) -> float:
        return self.t


@pytest.fixture
def relogio(privado):
    return Relogio()


@pytest.fixture
def portaria(relogio):
    return acesso.Portaria(relogio=relogio)


def _linhas(tabela: str) -> list[dict]:
    con = banco.conectar()
    try:
        return [dict(r) for r in con.execute(f'SELECT * FROM {tabela}')]
    finally:
        con.close()


def test_link_guarda_so_o_hash_e_vale_uma_vez(portaria, relogio, privado):
    token = acesso.emitir_link(agora=relogio())
    assert len(token) >= 40
    links = _linhas('acesso_link')
    assert [l['hash'] for l in links] == [hashlib.sha256(token.encode()).hexdigest()]
    assert token not in json.dumps(links) and not (privado / 'acesso.json').exists()
    sessao = portaria.entrar_por_link(token)
    assert sessao.token and portaria.valida(sessao.token)
    assert portaria.entrar_por_link(token).token is None  # uso único
    assert _linhas('acesso_link') == []


def test_link_expirado_nao_entra_e_e_consumido(portaria, relogio):
    token = acesso.emitir_link(agora=relogio())
    relogio.t += acesso.LINK_S + 1
    assert portaria.entrar_por_link(token).token is None
    relogio.t -= acesso.LINK_S + 1  # nem voltando o relógio: já foi consumido
    assert portaria.entrar_por_link(token).token is None


def test_varios_links_pendentes_convivem(portaria, relogio):
    a, b = acesso.emitir_link(agora=relogio()), acesso.emitir_link(agora=relogio())
    assert portaria.entrar_por_link(b).token and portaria.entrar_por_link(a).token


def test_token_errado_e_limite_de_tentativas(portaria, relogio):
    bom = acesso.emitir_link(agora=relogio())
    for i in range(acesso.LIMITE_LINKS):
        r = portaria.entrar_por_link(f'inventado-{i}-' + 'x' * 30)
        assert r.token is None and r.limitado_s == 0
    r = portaria.entrar_por_link('mais-um-errado-' + 'x' * 30)  # 11ª errada no mesmo minuto: 429
    assert r.token is None and r.limitado_s > 0
    assert portaria.entrar_por_link(bom).token  # o link bom entra mesmo assim (o limite só vale para erros)


def test_sessao_dura_30_dias_sem_uso_e_renova_com_uso(portaria, relogio):
    token = portaria.entrar_por_link(acesso.emitir_link(agora=relogio())).token
    relogio.t += 29 * DIA
    assert portaria.valida(token)  # usou: renova
    relogio.t += 29 * DIA
    assert portaria.valida(token, renovar=False)  # chamada automática: confere sem renovar
    relogio.t += 1 * DIA + 1
    assert not portaria.valida(token)  # 30 dias desde o último uso real
    assert _linhas('acesso_sessao') == []


def test_sessao_sobrevive_a_reinicio_do_servidor(portaria, relogio):
    token = portaria.entrar_por_link(acesso.emitir_link(agora=relogio())).token
    nova = acesso.Portaria(relogio=relogio)  # outro processo do servidor
    assert nova.valida(token)


def test_sair_encerra_so_a_atual_e_sair_de_todos_encerra_todas(portaria, relogio):
    a = portaria.entrar_por_link(acesso.emitir_link(agora=relogio())).token
    b = portaria.entrar_por_link(acesso.emitir_link(agora=relogio())).token
    portaria.fechar(a)
    assert not portaria.valida(a) and portaria.valida(b)
    c = portaria.entrar_por_link(acesso.emitir_link(agora=relogio())).token
    assert acesso.sessoes_ativas(agora=relogio()) == 2
    assert acesso.encerrar_todas() == 2
    assert not portaria.valida(b) and not portaria.valida(c)


def test_banco_nunca_guarda_token_em_claro(portaria, relogio, privado):
    link = acesso.emitir_link(agora=relogio())
    sessao = portaria.entrar_por_link(link).token
    acesso.emitir_link(agora=relogio())
    for arq in privado.glob('luzia.db*'):
        bruto = arq.read_bytes()
        assert link.encode() not in bruto and sessao.encode() not in bruto
    assert [s['hash'] for s in _linhas('acesso_sessao')] == [hashlib.sha256(sessao.encode()).hexdigest()]


def test_acesso_json_antigo_com_senha_e_apagado_sem_erro(portaria, relogio, privado):
    (privado / 'acesso.json').write_text(json.dumps({'versao': 3, 'senha': {'algoritmo': 'pbkdf2_sha256',
                                                                            'iteracoes': 600000, 'sal': '00' * 16,
                                                                            'hash': 'ab' * 32}}), encoding='utf-8')
    token = portaria.entrar_por_link(acesso.emitir_link(agora=relogio())).token
    assert token and portaria.valida(token)
    assert not (privado / 'acesso.json').exists()  # o hash da senha antiga não fica largado


def test_banco_ocupado_vira_acesso_indisponivel_sem_apagar_a_sessao(portaria, relogio, monkeypatch):
    import sqlite3
    token = portaria.entrar_por_link(acesso.emitir_link(agora=relogio())).token
    original = acesso._abrir

    def ocupado():
        raise sqlite3.OperationalError('database is locked')

    monkeypatch.setattr(acesso, '_abrir', ocupado)
    with pytest.raises(acesso.AcessoIndisponivel):
        portaria.valida(token)
    assert portaria.entrar_por_link('qualquer-' + 'x' * 30).indisponivel
    monkeypatch.setattr(acesso, '_abrir', original)
    assert portaria.valida(token)


def test_tokens_estranhos_nao_quebram(portaria):
    for ruim in (None, '', 12, 'x' * 300, ['lista']):
        assert portaria.entrar_por_link(ruim).token is None
        assert not portaria.valida(ruim)
