"""Login do painel: toda rota protegida devolve 401 sem sessão válida (servidor em thread, sem modelo real)."""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from luzia import acesso, server

SENHA = 'senha-de-teste-123'
FONTE = Path(server.__file__).read_text(encoding='utf-8')


def _rotas_no_codigo() -> set[str]:
    """Todo caminho '/api/...' escrito em server.py: uma rota nova não escapa da lista (nem da proteção)."""
    return set(re.findall(r"""['"](/api/[a-z0-9/_-]*)['"]""", FONTE))


def test_toda_rota_do_codigo_esta_na_lista_do_servidor():
    listadas = set(server.ROTAS_GET) | set(server.ROTAS_POST) | set(server.ABERTAS_GET) | set(server.ABERTAS_POST)
    assert _rotas_no_codigo() <= listadas, _rotas_no_codigo() - listadas
    assert not (set(server.ROTAS_GET) & set(server.ABERTAS_GET))
    assert not (set(server.ROTAS_POST) & set(server.ABERTAS_POST))
    assert set(server.ABERTAS_GET) == {'/api/ping', '/api/acesso/estado'}
    assert set(server.ABERTAS_POST) == {'/api/acesso/criar', '/api/acesso/entrar', '/api/acesso/sair'}


def _todas_protegidas_401(cli, cookie=True):
    for rota in server.ROTAS_GET:
        c, r, _ = cli.pedir('GET', rota + '?id=1', cookie=cookie)
        assert c == 401 and r.get('login') is True, (rota, c, r)
    for rota in (*server.ROTAS_POST, '/index.html', '/'):
        c, r, _ = cli.pedir('POST', rota, {}, cookie=cookie)
        assert c == 401 and r.get('login') is True, (rota, c, r)
    for rota in ('/api/inventada', '/api/acesso/inventada', '/API/estado', '/api'):  # rota nova ou desconhecida
        assert cli.pedir('POST', '/' + rota, {}, cookie=cookie)[0] == 401, rota  # caminho torto também
        assert cli.pedir('GET', rota, cookie=cookie)[0] in (401, 404), rota
        assert cli.pedir('POST', rota, {}, cookie=cookie)[0] == 401, rota


def test_sem_cookie_toda_rota_protegida_devolve_401(servidor):
    _todas_protegidas_401(servidor)
    servidor.entrar(SENHA)
    _todas_protegidas_401(servidor, cookie=False)
    servidor.cookie = 'inventado-' + 'x' * 30
    _todas_protegidas_401(servidor)


def test_rotas_abertas_e_arquivos_do_painel_sem_login(servidor):
    assert servidor.pedir('GET', '/api/ping')[:2] == (200, {'ok': True})
    c, r, _ = servidor.pedir('GET', '/api/acesso/estado')
    assert c == 200 and r == {'senha_criada': False, 'sessao_valida': False, 'travado_s': 0, 'min_senha': 8}
    for arq in ('/', '/index.html', '/luzia.css', '/luzia.js', '/logo.svg'):
        assert servidor.pedir('GET', arq)[0] == 200, arq


def test_criar_senha_abre_sessao_com_cookie_httponly_samesite_strict(servidor, privado):
    c, r, cab = servidor.pedir('POST', '/api/acesso/criar', {'senha': SENHA, 'confirmacao': SENHA})
    assert c == 200 and r == {'ok': True}
    cookie = next(v for n, v in cab if n.lower() == 'set-cookie')
    partes = [p.strip() for p in cookie.split(';')]
    assert partes[0].startswith('luzia_sessao=') and len(partes[0]) > len('luzia_sessao=') + 40
    assert 'HttpOnly' in partes and 'SameSite=Strict' in partes and 'Path=/' in partes
    assert not any(p.lower() == 'secure' for p in partes)  # http://localhost
    assert servidor.pedir('GET', '/api/estado')[0] == 200
    assert servidor.pedir('GET', '/api/acesso/estado')[1]['sessao_valida'] is True
    # a resposta e o arquivo nunca trazem a senha; o hash fica só no arquivo privado
    bruto = (privado / 'acesso.json').read_text(encoding='utf-8')
    assert SENHA not in bruto and SENHA not in json.dumps(r)
    h = json.loads(bruto)['senha']['hash']
    assert h not in json.dumps(servidor.pedir('GET', '/api/acesso/estado')[1])


def test_criar_senha_so_uma_vez_e_regras(servidor):
    c, r, _ = servidor.pedir('POST', '/api/acesso/criar', {'senha': 'curta', 'confirmacao': 'curta'})
    assert c == 400 and '8' in r['erro']
    c, r, _ = servidor.pedir('POST', '/api/acesso/criar', {'senha': SENHA, 'confirmacao': SENHA + '1'})
    assert c == 400 and 'confirmação' in r['erro']
    c, r, _ = servidor.pedir('POST', '/api/acesso/criar', {'senha': 12345678, 'confirmacao': 12345678})
    assert c == 400
    assert servidor.pedir('POST', '/api/acesso/criar', {'senha': SENHA, 'confirmacao': SENHA})[0] == 200
    servidor.cookie = None
    c, r, _ = servidor.pedir('POST', '/api/acesso/criar', {'senha': 'outra-senha-boa', 'confirmacao': 'outra-senha-boa'})
    assert c == 409 and servidor.cookie is None
    assert acesso.conferir(SENHA) and not acesso.conferir('outra-senha-boa')


def test_entrar_certo_errado_e_sair(servidor):
    assert servidor.pedir('POST', '/api/acesso/entrar', {'senha': SENHA})[0] == 409  # ainda sem senha
    servidor.entrar(SENHA)
    servidor.pedir('POST', '/api/acesso/sair', {})
    assert servidor.cookie is None
    c, r, cab = servidor.pedir('POST', '/api/acesso/entrar', {'senha': 'errada-errada'})
    assert c == 401 and r['restantes'] == 4 and servidor.cookie is None
    assert not any(n.lower() == 'set-cookie' for n, _ in cab)
    c, r, _ = servidor.pedir('POST', '/api/acesso/entrar', {'senha': SENHA})
    assert c == 200 and servidor.cookie
    token = servidor.cookie
    assert servidor.pedir('GET', '/api/estado')[0] == 200
    c, _, cab = servidor.pedir('POST', '/api/acesso/sair', {})
    assert c == 200
    apaga = next(v for n, v in cab if n.lower() == 'set-cookie')
    assert 'Max-Age=0' in apaga and 'HttpOnly' in apaga and 'SameSite=Strict' in apaga
    servidor.cookie = token  # o token antigo, mesmo guardado, não vale mais
    assert servidor.pedir('GET', '/api/estado')[0] == 401


def test_trava_apos_5_erros_429_e_libera_apos_60_s(servidor, monkeypatch):
    relogio = [5000.0]
    monkeypatch.setattr(server.PORTARIA, 'relogio', lambda: relogio[0])
    servidor.entrar(SENHA)
    servidor.cookie = None
    for i in range(4):
        assert servidor.pedir('POST', '/api/acesso/entrar', {'senha': f'errada-{i}-xx'})[0] == 401
    c, r, cab = servidor.pedir('POST', '/api/acesso/entrar', {'senha': 'errada-5-xx'})
    assert c == 429 and r['segundos'] == 60
    c, r, cab = servidor.pedir('POST', '/api/acesso/entrar', {'senha': SENHA})
    assert c == 429 and r['segundos'] == 60 and servidor.cookie is None
    assert dict((n.lower(), v) for n, v in cab)['retry-after'] == '60'
    assert servidor.pedir('GET', '/api/acesso/estado')[1]['travado_s'] == 60
    relogio[0] += 60
    assert servidor.pedir('POST', '/api/acesso/entrar', {'senha': SENHA})[0] == 200


def test_sessao_expira_apos_30_min_sem_uso(servidor, monkeypatch):
    relogio = [5000.0]
    monkeypatch.setattr(server.PORTARIA, 'relogio', lambda: relogio[0])
    servidor.entrar(SENHA)
    relogio[0] += 20 * 60
    assert servidor.pedir('GET', '/api/estado')[0] == 200  # renova
    relogio[0] += 20 * 60
    assert servidor.pedir('GET', '/api/estado')[0] == 200
    relogio[0] += 30 * 60 + 1
    c, r, _ = servidor.pedir('GET', '/api/estado')
    assert c == 401 and r['login'] is True
    assert servidor.pedir('GET', '/api/acesso/estado')[1]['sessao_valida'] is False


def test_redefinir_senha_derruba_sessao_aberta(servidor):
    servidor.entrar(SENHA)
    assert servidor.pedir('GET', '/api/estado')[0] == 200
    acesso.apagar_senha()  # o que o comando `senha` faz, em outro processo
    assert servidor.pedir('GET', '/api/estado')[0] == 401
    assert servidor.pedir('GET', '/api/acesso/estado')[1] == {'senha_criada': False, 'sessao_valida': False,
                                                              'travado_s': 0, 'min_senha': 8}


def test_protecoes_de_host_origem_json_e_tamanho_valem_nas_rotas_de_acesso(servidor):
    corpo = {'senha': SENHA, 'confirmacao': SENHA}
    assert servidor.pedir('GET', '/api/acesso/estado', headers={'Host': 'evil.example'})[0] == 403
    assert servidor.pedir('POST', '/api/acesso/criar', corpo, headers={'Origin': 'http://evil.example'})[0] == 403
    assert servidor.pedir('POST', '/api/acesso/criar', corpo, headers={'Sec-Fetch-Site': 'cross-site'})[0] == 403
    assert servidor.pedir('POST', '/api/acesso/criar', corpo, headers={'Content-Type': 'text/plain'})[0] == 415
    assert servidor.pedir('POST', '/api/acesso/criar', corpo, headers={'Content-Length': '99999999'})[0] == 413
    assert servidor.pedir('POST', '/api/acesso/entrar', corpo=b'{nao e json')[0] == 400
    assert not acesso.tem_senha()
    servidor.entrar(SENHA)  # e nas protegidas, mesmo com sessão
    assert servidor.pedir('POST', '/api/modo', {'modo': 'passivo'}, headers={'Origin': 'http://evil.example'})[0] == 403
    assert servidor.pedir('GET', '/api/estado', headers={'Host': 'evil.example'})[0] == 403


def test_respostas_nunca_vazam_senha_nem_token_em_log(servidor, privado):
    servidor.entrar(SENHA)
    servidor.pedir('POST', '/api/acesso/entrar', {'senha': 'errada-errada'})
    erros = privado / 'erros.log'
    texto = erros.read_text(encoding='utf-8') if erros.exists() else ''
    assert SENHA not in texto and 'errada-errada' not in texto and (servidor.cookie or '') not in texto


def test_painel_nao_guarda_sessao_no_navegador_e_nao_busca_dados_antes_do_login():
    painel = Path(server.PAINEL)
    js = (painel / 'luzia.js').read_text(encoding='utf-8')
    html = (painel / 'index.html').read_text(encoding='utf-8')
    for proibido in ('localStorage', 'sessionStorage', 'document.cookie', 'indexedDB'):
        assert proibido not in js, proibido
    assert '<body class="fora">' in html  # trilho e telas escondidos até entrar
    linhas = [ln for ln in js.splitlines() if ln and not ln.startswith((' ', '}', '//', ')'))]
    chamadas_no_topo = [ln for ln in linhas if re.match(r'^[a-zA-Z_$][\w$]*\(.*\);$', ln)
                        and 'addEventListener' not in ln]
    assert chamadas_no_topo == ['acessoAoIniciar();']  # a única coisa que roda ao abrir é conferir o acesso
    assert 'polling = setInterval' in js and 'clearInterval(polling)' in js


# ------------------------------------------------------------------ redefinir pelo chat/CLI (`senha`)
def _cli(monkeypatch, *argv):
    import io
    import sys
    from contextlib import redirect_stdout
    from luzia import cli
    monkeypatch.setattr(sys, 'argv', ['luzia', *argv])
    buf = io.StringIO()
    with redirect_stdout(buf):
        cli.main()
    return buf.getvalue()


def _botoes(saida):
    linha = next(x for x in saida.splitlines() if x.startswith('LUZIA_BOTOES='))
    return json.loads(linha.split('=', 1)[1])


def test_senha_no_cli_pede_confirmacao_antes_de_apagar(servidor, monkeypatch, privado):
    servidor.entrar(SENHA)
    saida = _cli(monkeypatch, 'senha')
    assert acesso.tem_senha() and servidor.pedir('GET', '/api/estado')[0] == 200  # só perguntou
    assert 'LUZIA_PERGUNTA=' in saida and any(b['rodar'] == 'senha apagar' for b in _botoes(saida))
    texto = (privado / 'acesso.json').read_text(encoding='utf-8')
    assert json.loads(texto)['senha']['hash'] not in saida and SENHA not in saida


def test_senha_apagar_no_cli_derruba_as_sessoes_e_o_painel_pede_senha_nova(servidor, monkeypatch):
    servidor.entrar(SENHA)
    saida = _cli(monkeypatch, 'senha', 'apagar')
    assert 'apagada' in saida and 'LUZIA_BOTOES=' in saida
    assert not acesso.tem_senha()
    assert servidor.pedir('GET', '/api/estado')[0] == 401
    assert servidor.pedir('GET', '/api/acesso/estado')[1]['senha_criada'] is False
    nova = 'outra-senha-boa'
    assert servidor.pedir('POST', '/api/acesso/criar', {'senha': nova, 'confirmacao': nova})[0] == 200
    assert servidor.pedir('GET', '/api/estado')[0] == 200
    saida = _cli(monkeypatch, 'senha')
    assert 'existe' in saida


def test_senha_sem_senha_criada_explica_como_criar(privado, monkeypatch):
    saida = _cli(monkeypatch, 'senha', 'apagar')
    assert 'ainda não' in saida.lower() and 'LUZIA_BOTOES=' in saida
    assert acesso.versao() == 0


def test_comando_senha_tem_arquivo_com_description_entre_aspas():
    texto = (Path(server.HERE) / 'commands' / 'senha.md').read_text(encoding='utf-8')
    assert re.search(r'^description: ".*"$', texto, re.MULTILINE)
    assert 'python -m luzia.cli senha' in texto and 'LUZIA_BOTOES' in texto


# ------------------------------------------------------------------ rodada de correções 1
def test_polling_automatico_nao_renova_a_sessao(servidor, monkeypatch):
    """Aba esquecida aberta: o polling de 4 s (cabeçalho X-Luzia-Auto) não segura a sessão além de 30 min sem uso."""
    relogio = [5000.0]
    monkeypatch.setattr(server.PORTARIA, 'relogio', lambda: relogio[0])
    servidor.entrar(SENHA)
    auto = {'X-Luzia-Auto': '1'}
    for _ in range(7):  # 28 min só de polling
        relogio[0] += 4 * 60
        assert servidor.pedir('GET', '/api/estado', headers=auto)[0] == 200
    relogio[0] += 3 * 60  # 31 min desde o último gesto da pessoa
    c, r, _ = servidor.pedir('GET', '/api/estado', headers=auto)
    assert c == 401 and r['login'] is True
    assert servidor.pedir('GET', '/api/estado')[0] == 401  # e não volta com um clique


def test_leituras_automaticas_tambem_nao_renovam(servidor, monkeypatch):
    relogio = [5000.0]
    monkeypatch.setattr(server.PORTARIA, 'relogio', lambda: relogio[0])
    servidor.entrar(SENHA)
    relogio[0] += 20 * 60
    assert servidor.pedir('POST', '/api/leituras', {'auto': True}, headers={'X-Luzia-Auto': '1'})[0] == 200
    relogio[0] += 11 * 60
    assert servidor.pedir('GET', '/api/estado')[0] == 401


def test_painel_marca_polling_e_leituras_automaticas_como_automaticos():
    js = (Path(server.PAINEL) / 'luzia.js').read_text(encoding='utf-8')
    assert "'X-Luzia-Auto': '1'" in js
    assert "api('/api/leituras', { auto: true }, true)" in js and 'await carregar(true);' in js
    corpo = js[js.index('async function atualizarSozinho'):]
    assert "api('/api/estado', null, true)" in corpo[:400]
