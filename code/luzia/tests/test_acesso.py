"""Senha local do painel e sessões em memória (`acesso.py`): só dados sintéticos, relógio injetável."""

from __future__ import annotations

import json

import pytest

from luzia import acesso

SENHA = 'senha-de-teste-123'


class Relogio:
    def __init__(self, t: float = 1000.0):
        self.t = t

    def __call__(self) -> float:
        return self.t


@pytest.fixture
def portaria(privado):
    return acesso.Portaria(relogio=Relogio())


def test_criar_senha_grava_so_o_hash_pbkdf2(privado):
    assert not acesso.tem_senha()
    acesso.criar_senha(SENHA, SENHA)
    bruto = (privado / 'acesso.json').read_text(encoding='utf-8')
    assert SENHA not in bruto
    dados = json.loads(bruto)
    s = dados['senha']
    assert s['algoritmo'] == 'pbkdf2_sha256' and s['iteracoes'] >= 600_000
    assert len(bytes.fromhex(s['sal'])) == 16 and len(bytes.fromhex(s['hash'])) == 32
    assert SENHA.encode().hex() not in bruto
    assert acesso.tem_senha() and acesso.conferir(SENHA) and not acesso.conferir(SENHA + 'x')


def test_criar_senha_so_uma_vez_minimo_8_e_confirmacao(privado, monkeypatch):
    monkeypatch.setattr(acesso, 'ITERACOES', 1000)
    with pytest.raises(ValueError, match='8'):
        acesso.criar_senha('curta12', 'curta12')
    with pytest.raises(ValueError, match='confirma'):
        acesso.criar_senha(SENHA, SENHA + '!')
    assert not acesso.tem_senha()
    acesso.criar_senha(SENHA, SENHA)
    with pytest.raises(acesso.SenhaJaExiste):
        acesso.criar_senha('outra-senha-boa', 'outra-senha-boa')
    assert acesso.conferir(SENHA)


def test_sal_diferente_a_cada_senha(privado, monkeypatch):
    monkeypatch.setattr(acesso, 'ITERACOES', 1000)
    acesso.criar_senha(SENHA, SENHA)
    primeiro = json.loads((privado / 'acesso.json').read_text(encoding='utf-8'))['senha']
    acesso.apagar_senha()
    acesso.criar_senha(SENHA, SENHA)
    segundo = json.loads((privado / 'acesso.json').read_text(encoding='utf-8'))['senha']
    assert primeiro['sal'] != segundo['sal'] and primeiro['hash'] != segundo['hash']


def test_arquivo_corrompido_bloqueia_criar_e_entrar(privado):
    (privado / 'acesso.json').write_text('{isto não é json', encoding='utf-8')
    assert acesso.tem_senha()  # o mais seguro: não deixa criar outra por cima; `senha` no chat redefine
    assert not acesso.conferir(SENHA)
    with pytest.raises(acesso.SenhaJaExiste):
        acesso.criar_senha(SENHA, SENHA)
    acesso.apagar_senha()
    assert not acesso.tem_senha()


def test_entrar_certo_e_errado(portaria, monkeypatch):
    monkeypatch.setattr(acesso, 'ITERACOES', 1000)
    acesso.criar_senha(SENHA, SENHA)
    r = portaria.entrar('errada-errada')
    assert r.token is None and r.restantes == 4 and r.travado_s == 0
    r = portaria.entrar(SENHA)
    assert r.token and portaria.valida(r.token)
    assert not portaria.valida('token-inventado') and not portaria.valida('')


def test_trava_apos_5_erros_e_libera_apos_60_s(portaria, monkeypatch):
    monkeypatch.setattr(acesso, 'ITERACOES', 1000)
    acesso.criar_senha(SENHA, SENHA)
    for _ in range(5):
        assert portaria.entrar('errada-errada').token is None
    r = portaria.entrar(SENHA)  # travado: nem a senha certa entra, e o hash nem é calculado
    assert r.token is None and r.travado_s == 60
    portaria.relogio.t += 59
    assert portaria.entrar(SENHA).travado_s == 1
    portaria.relogio.t += 1
    r = portaria.entrar(SENHA)
    assert r.token and r.travado_s == 0


def test_depois_da_trava_um_erro_trava_de_novo(portaria, monkeypatch):
    monkeypatch.setattr(acesso, 'ITERACOES', 1000)
    acesso.criar_senha(SENHA, SENHA)
    for _ in range(5):
        portaria.entrar('errada-errada')
    portaria.relogio.t += 60
    r = portaria.entrar('errada-de-novo')
    assert r.token is None and r.travado_s == 60  # o contador só zera com a senha certa
    portaria.relogio.t += 60
    assert portaria.entrar(SENHA).token
    assert portaria.entrar('errada-errada').restantes == 4


def test_sessao_expira_apos_30_min_sem_uso_e_renova_com_uso(portaria, monkeypatch):
    monkeypatch.setattr(acesso, 'ITERACOES', 1000)
    acesso.criar_senha(SENHA, SENHA)
    token = portaria.entrar(SENHA).token
    portaria.relogio.t += 29 * 60
    assert portaria.valida(token)  # usou: renova
    portaria.relogio.t += 29 * 60
    assert portaria.valida(token)
    portaria.relogio.t += 30 * 60 + 1
    assert not portaria.valida(token)
    assert not portaria.valida(token)  # expirada some de vez


def test_sair_invalida_so_aquela_sessao(portaria, monkeypatch):
    monkeypatch.setattr(acesso, 'ITERACOES', 1000)
    acesso.criar_senha(SENHA, SENHA)
    a, b = portaria.entrar(SENHA).token, portaria.entrar(SENHA).token
    portaria.fechar(a)
    assert not portaria.valida(a) and portaria.valida(b)


def test_apagar_senha_derruba_todas_as_sessoes(portaria, monkeypatch):
    monkeypatch.setattr(acesso, 'ITERACOES', 1000)
    acesso.criar_senha(SENHA, SENHA)
    token = portaria.entrar(SENHA).token
    v = acesso.versao()
    acesso.apagar_senha()
    assert acesso.versao() == v + 1 and not acesso.tem_senha()
    assert not portaria.valida(token)
    acesso.criar_senha(SENHA, SENHA)  # mesma senha de novo: a sessão antiga continua morta
    assert not portaria.valida(token)


def test_token_nao_fica_guardado_em_claro(portaria, monkeypatch):
    monkeypatch.setattr(acesso, 'ITERACOES', 1000)
    acesso.criar_senha(SENHA, SENHA)
    token = portaria.entrar(SENHA).token
    assert len(token) >= 40
    assert token not in repr(portaria.__dict__)
