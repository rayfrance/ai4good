"""Entrada herdada do agente no painel: link de uso único, sessão de 30 dias e 401 em toda rota protegida sem sessão
(servidor em thread, sem modelo real)."""

from __future__ import annotations

import io
import json
import re
import sys
import time
from contextlib import redirect_stdout
from pathlib import Path

from luzia import acesso, cli, server

FONTE = Path(server.__file__).read_text(encoding='utf-8')
DIA = 24 * 3600
TRINTA_DIAS = 30 * DIA


def _rotas_no_codigo() -> set[str]:
    """Todo caminho '/api/...' escrito em server.py: uma rota nova não escapa da lista (nem da proteção)."""
    return set(re.findall(r"""['"](/api/[a-z0-9/_-]*)['"]""", FONTE))


def _cookie(cab) -> str:
    return next(v for n, v in cab if n.lower() == 'set-cookie')


def _relogio(monkeypatch):
    t = [time.time()]
    monkeypatch.setattr(server.PORTARIA, 'relogio', lambda: t[0])
    return t


# ------------------------------------------------------------------ rotas
def test_toda_rota_do_codigo_esta_na_lista_do_servidor():
    listadas = set(server.ROTAS_GET) | set(server.ROTAS_POST) | set(server.ABERTAS_GET) | set(server.ABERTAS_POST)
    assert _rotas_no_codigo() <= listadas, _rotas_no_codigo() - listadas
    assert not (set(server.ROTAS_GET) & set(server.ABERTAS_GET))
    assert not (set(server.ROTAS_POST) & set(server.ABERTAS_POST))
    assert set(server.ABERTAS_GET) == {'/api/ping', '/api/acesso/estado'}
    assert set(server.ABERTAS_POST) == {'/api/acesso/link', '/api/acesso/sair'}


def _todas_protegidas_401(cli_, cookie=True):
    for rota in server.ROTAS_GET:
        c, r, _ = cli_.pedir('GET', rota + '?id=1', cookie=cookie)
        assert c == 401 and r.get('login') is True, (rota, c, r)
    for rota in (*server.ROTAS_POST, '/index.html', '/'):
        c, r, _ = cli_.pedir('POST', rota, {}, cookie=cookie)
        assert c == 401 and r.get('login') is True, (rota, c, r)
    for rota in ('/api/inventada', '/api/acesso/inventada', '/API/estado', '/api', '/api/acesso/criar',
                 '/api/acesso/entrar'):  # rota nova, desconhecida ou da senha antiga
        assert cli_.pedir('POST', '/' + rota, {}, cookie=cookie)[0] == 401, rota  # caminho torto também
        assert cli_.pedir('GET', rota, cookie=cookie)[0] in (401, 404), rota
        assert cli_.pedir('POST', rota, {}, cookie=cookie)[0] == 401, rota


def test_sem_sessao_toda_rota_protegida_devolve_401(servidor):
    _todas_protegidas_401(servidor)
    servidor.entrar()
    _todas_protegidas_401(servidor, cookie=False)
    servidor.cookie = 'inventado-' + 'x' * 30
    _todas_protegidas_401(servidor)


def test_rotas_abertas_e_arquivos_do_painel_sem_sessao(servidor):
    assert servidor.pedir('GET', '/api/ping')[:2] == (200, {'ok': True})
    c, r, _ = servidor.pedir('GET', '/api/acesso/estado')
    assert c == 200 and r == {'sessao_valida': False}
    for arq in ('/', '/index.html', '/luzia.css', '/luzia.js', '/logo.svg'):
        assert servidor.pedir('GET', arq)[0] == 200, arq


# ------------------------------------------------------------------ link de uso único
def test_link_valido_entra_com_cookie_de_30_dias(servidor):
    token = acesso.emitir_link()
    c, r, cab = servidor.pedir('POST', '/api/acesso/link', {'token': token})
    assert c == 200 and r == {'ok': True}
    partes = [p.strip() for p in _cookie(cab).split(';')]
    assert partes[0].startswith('luzia_sessao=') and len(partes[0]) > len('luzia_sessao=') + 40
    assert {'HttpOnly', 'SameSite=Strict', 'Path=/', f'Max-Age={TRINTA_DIAS}'} <= set(partes)
    assert not any(p.lower() == 'secure' for p in partes)  # http://localhost
    assert token not in _cookie(cab) and token not in json.dumps(r)
    assert servidor.pedir('GET', '/api/estado')[0] == 200
    assert servidor.pedir('GET', '/api/acesso/estado')[1] == {'sessao_valida': True}


def test_link_usado_de_novo_ou_errado_devolve_401(servidor):
    token = acesso.emitir_link()
    assert servidor.pedir('POST', '/api/acesso/link', {'token': token})[0] == 200
    servidor.cookie = None
    c, r, cab = servidor.pedir('POST', '/api/acesso/link', {'token': token})
    assert c == 401 and 'agente' in r['erro'] and not any(n.lower() == 'set-cookie' for n, _ in cab)
    assert servidor.pedir('POST', '/api/acesso/link', {'token': 'inventado-' + 'y' * 30})[0] == 401
    assert servidor.pedir('POST', '/api/acesso/link', {})[0] == 401
    assert servidor.cookie is None


def test_link_expirado_devolve_401_e_e_consumido(servidor, monkeypatch):
    t = _relogio(monkeypatch)
    token = acesso.emitir_link(agora=t[0])
    t[0] += acesso.LINK_S + 1
    assert servidor.pedir('POST', '/api/acesso/link', {'token': token})[0] == 401
    t[0] -= acesso.LINK_S + 1
    assert servidor.pedir('POST', '/api/acesso/link', {'token': token})[0] == 401


def test_muitos_links_errados_devolvem_429(servidor):
    for i in range(acesso.LIMITE_LINKS):
        assert servidor.pedir('POST', '/api/acesso/link', {'token': f'errado-{i}-' + 'z' * 30})[0] == 401
    c, r, cab = servidor.pedir('POST', '/api/acesso/link', {'token': 'mais-um-errado-' + 'z' * 30})
    assert c == 429 and r['segundos'] > 0 and 'retry-after' in {n.lower() for n, _ in cab}


# ------------------------------------------------------------------ sessão
def test_sessao_sobrevive_a_reinicio_do_servidor(servidor, monkeypatch):
    servidor.entrar()
    monkeypatch.setattr(server, 'PORTARIA', acesso.Portaria())  # servidor reiniciado: nada em memória
    assert servidor.pedir('GET', '/api/estado')[0] == 200


def test_30_dias_sem_uso_saem_e_o_uso_renova_o_cookie(servidor, monkeypatch):
    t = _relogio(monkeypatch)
    servidor.entrar()
    t[0] += 29 * DIA
    c, _, cab = servidor.pedir('GET', '/api/estado')
    assert c == 200 and f'Max-Age={TRINTA_DIAS}' in _cookie(cab)  # uso real: renova servidor e cookie
    t[0] += 29 * DIA
    assert servidor.pedir('GET', '/api/estado')[0] == 200
    t[0] += TRINTA_DIAS + 1
    c, r, _ = servidor.pedir('GET', '/api/estado')
    assert c == 401 and r['login'] is True


def test_polling_automatico_nao_renova_a_sessao(servidor, monkeypatch):
    """Aba esquecida aberta: o polling (cabeçalho X-Luzia-Auto) não segura a sessão além de 30 dias sem uso."""
    t = _relogio(monkeypatch)
    servidor.entrar()
    auto = {'X-Luzia-Auto': '1'}
    for _ in range(29):
        t[0] += DIA
        c, _, cab = servidor.pedir('GET', '/api/estado', headers=auto)
        assert c == 200 and not any(n.lower() == 'set-cookie' for n, _ in cab)
    t[0] += DIA + 1
    assert servidor.pedir('GET', '/api/estado', headers=auto)[0] == 401
    assert servidor.pedir('GET', '/api/estado')[0] == 401  # e não volta com um clique


def test_leituras_automaticas_tambem_nao_renovam(servidor, monkeypatch):
    t = _relogio(monkeypatch)
    servidor.entrar()
    t[0] += 20 * DIA
    assert servidor.pedir('POST', '/api/leituras', {'auto': True}, headers={'X-Luzia-Auto': '1'})[0] == 200
    t[0] += 11 * DIA
    assert servidor.pedir('GET', '/api/estado')[0] == 401


def test_sair_encerra_so_a_sessao_atual(servidor):
    servidor.entrar()
    outra = servidor.cookie
    servidor.cookie = None
    servidor.entrar()
    atual = servidor.cookie
    c, _, cab = servidor.pedir('POST', '/api/acesso/sair', {})
    assert c == 200 and servidor.cookie is None
    apaga = _cookie(cab)
    assert 'Max-Age=0' in apaga and 'HttpOnly' in apaga and 'SameSite=Strict' in apaga
    servidor.cookie = atual
    assert servidor.pedir('GET', '/api/estado')[0] == 401
    servidor.cookie = outra
    assert servidor.pedir('GET', '/api/estado')[0] == 200


def test_banco_ocupado_responde_503_sem_derrubar_a_sessao(servidor, monkeypatch):
    import sqlite3
    servidor.entrar()
    original, quebrado = acesso._abrir, [True]

    def abrir():
        if quebrado[0]:
            raise sqlite3.OperationalError('database is locked')
        return original()

    monkeypatch.setattr(acesso, '_abrir', abrir)
    c, r, _ = servidor.pedir('GET', '/api/estado')
    assert c == 503 and not r.get('login')
    assert servidor.pedir('GET', '/api/acesso/estado')[0] == 503
    assert servidor.pedir('POST', '/api/acesso/link', {'token': 'x' * 43})[0] == 503
    quebrado[0] = False
    assert servidor.pedir('GET', '/api/estado')[0] == 200  # a sessão seguiu valendo


def test_protecoes_de_host_origem_json_e_tamanho_valem_nas_rotas_de_acesso(servidor):
    corpo = {'token': acesso.emitir_link()}
    assert servidor.pedir('GET', '/api/acesso/estado', headers={'Host': 'evil.example'})[0] == 403
    assert servidor.pedir('POST', '/api/acesso/link', corpo, headers={'Origin': 'http://evil.example'})[0] == 403
    assert servidor.pedir('POST', '/api/acesso/link', corpo, headers={'Sec-Fetch-Site': 'cross-site'})[0] == 403
    assert servidor.pedir('POST', '/api/acesso/link', corpo, headers={'Content-Type': 'text/plain'})[0] == 415
    # Content-Length enorme com corpo mínimo: recusa pelo tamanho declarado, sem ler (como em test_server.py)
    assert servidor.pedir('POST', '/api/acesso/link', corpo=b'{}', headers={'Content-Length': '99999999'})[0] == 413
    assert servidor.pedir('POST', '/api/acesso/link', corpo=b'{nao e json')[0] == 400
    assert servidor.pedir('POST', '/api/acesso/sair', {}, headers={'Origin': 'http://evil.example'})[0] == 403
    assert servidor.pedir('POST', '/api/acesso/link', corpo)[0] == 200  # recusas acima não gastaram o link
    assert servidor.pedir('POST', '/api/modo', {'modo': 'passivo'}, headers={'Origin': 'http://evil.example'})[0] == 403
    assert servidor.pedir('GET', '/api/estado', headers={'Host': 'evil.example'})[0] == 403


def test_log_nunca_guarda_token(servidor, privado):
    link = acesso.emitir_link()
    servidor.pedir('POST', '/api/acesso/link', {'token': link})
    servidor.pedir('POST', '/api/acesso/link', {'token': 'errado-' + 'w' * 30})
    erros = privado / 'erros.log'
    texto = erros.read_text(encoding='utf-8') if erros.exists() else ''
    assert link not in texto and 'errado-' not in texto and (servidor.cookie or 'x' * 99) not in texto


# ------------------------------------------------------------------ painel
def test_painel_entra_pelo_fragmento_e_nao_guarda_sessao_no_navegador():
    painel = Path(server.PAINEL)
    js = (painel / 'luzia.js').read_text(encoding='utf-8')
    html = (painel / 'index.html').read_text(encoding='utf-8')
    for proibido in ('localStorage', 'sessionStorage', 'document.cookie', 'indexedDB', 'location.search',
                     '/api/acesso/criar', '/api/acesso/entrar', 'ac-senha', 'new-password', 'senha'):
        assert proibido not in js, proibido
    assert '<body class="fora">' in html  # trilho e telas escondidos até entrar
    assert '#entrar=' in js and 'history.replaceState' in js and "'/api/acesso/link'" in js
    assert 'Abra pelo seu agente' in js and '/luzia:career-map' in js
    linhas = [ln for ln in js.splitlines() if ln and not ln.startswith((' ', '}', '//', ')'))]
    chamadas_no_topo = [ln for ln in linhas if re.match(r'^[a-zA-Z_$][\w$]*\(.*\);$', ln)
                        and 'addEventListener' not in ln]
    assert chamadas_no_topo == ['acessoAoIniciar();']  # a única coisa que roda ao abrir é conferir o acesso
    assert 'polling = setInterval' in js and 'clearInterval(polling)' in js


def test_painel_marca_polling_e_leituras_automaticas_como_automaticos():
    js = (Path(server.PAINEL) / 'luzia.js').read_text(encoding='utf-8')
    assert "'X-Luzia-Auto': '1'" in js
    assert "api('/api/leituras', { auto: true }, true)" in js and 'await carregar(true);' in js
    corpo = js[js.index('async function atualizarSozinho'):]
    assert "api('/api/estado', null, true)" in corpo[:400]


# ------------------------------------------------------------------ chat / CLI
def _cli(monkeypatch, *argv):
    monkeypatch.setattr(sys, 'argv', ['luzia', *argv])
    buf = io.StringIO()
    with redirect_stdout(buf):
        cli.main()
    return buf.getvalue()


def _botoes(saida):
    linha = next(x for x in saida.splitlines() if x.startswith('LUZIA_BOTOES='))
    return json.loads(linha.split('=', 1)[1])


def _painel_de_teste(servidor, monkeypatch):
    server.publicar_identidade()
    monkeypatch.setattr(cli, 'PAINEL', f'http://127.0.0.1:{servidor.port}')
    monkeypatch.setattr(cli, '_sem_tela', lambda: False)


def test_career_map_abre_o_navegador_com_link_no_fragmento_e_nao_imprime_o_token(servidor, monkeypatch):
    import webbrowser
    abertos = []
    _painel_de_teste(servidor, monkeypatch)
    monkeypatch.setattr(webbrowser, 'open', lambda url, *a, **k: abertos.append(url) or True)
    saida = _cli(monkeypatch, 'career-map')
    assert len(abertos) == 1
    url = abertos[0]
    assert url.startswith(cli.PAINEL + '/#entrar=') and '?' not in url
    token = url.split('#entrar=', 1)[1]
    assert token not in saida and 'LUZIA_BOTOES=' in saida
    servidor.cookie = None
    assert servidor.pedir('POST', '/api/acesso/link', {'token': token})[0] == 200  # o link do navegador entra


def test_career_map_sem_navegador_imprime_o_link_uma_vez_com_aviso(servidor, monkeypatch):
    import webbrowser
    _painel_de_teste(servidor, monkeypatch)
    monkeypatch.setattr(webbrowser, 'open', lambda *a, **k: False)
    saida = _cli(monkeypatch, 'career-map')
    links = re.findall(r'http://127\.0\.0\.1:\d+/#entrar=[\w-]+', saida)
    assert len(links) == 1 and saida.count(links[0].split('#entrar=')[1]) == 1
    assert '2 minutos' in saida and 'uma vez' in saida


def test_acesso_sair_de_todos_pede_confirmacao_e_encerra_todas(servidor, monkeypatch):
    servidor.entrar()
    a = servidor.cookie
    servidor.cookie = None
    servidor.entrar()
    saida = _cli(monkeypatch, 'acesso')
    assert '2 sessão' in saida or '2 sessões' in saida
    saida = _cli(monkeypatch, 'acesso', 'sair-de-todos')
    assert servidor.pedir('GET', '/api/estado')[0] == 200  # só perguntou
    assert any(b['rodar'] == 'acesso sair-de-todos confirmar' for b in _botoes(saida))
    saida = _cli(monkeypatch, 'acesso', 'sair-de-todos', 'confirmar')
    assert 'encerrada' in saida and 'LUZIA_BOTOES=' in saida
    assert servidor.pedir('GET', '/api/estado')[0] == 401
    servidor.cookie = a
    assert servidor.pedir('GET', '/api/estado')[0] == 401


def test_senha_saiu_do_chat_e_acesso_tem_comando():
    assert 'senha' not in cli.COMANDOS and 'acesso' in cli.COMANDOS
    comandos = Path(server.HERE) / 'commands'
    assert not (comandos / 'senha.md').exists()
    texto = (comandos / 'acesso.md').read_text(encoding='utf-8')
    assert re.search(r'^description: ".*"$', texto, re.MULTILINE) and 'python -m luzia.cli acesso' in texto
    assert 'já entra' in (comandos / 'career-map.md').read_text(encoding='utf-8')
    fonte = (Path(server.HERE) / 'acesso.py').read_text(encoding='utf-8')
    assert 'pbkdf2' not in fonte.lower() and 'senha' not in fonte.lower()


def test_instrucoes_ao_agente_nao_proibem_os_nomes_da_dona_dos_dados():
    """Decisão da dona: dados reais visíveis para ela; o resumo vai só ao banco privado e ao dossiê local."""
    raiz = Path(server.HERE)
    arquivos_ = [*raiz.glob('commands/*.md'), *raiz.glob('skills/*/SKILL.md'), raiz / 'harness' / 'REGRAS.md',
                 raiz / 'observer.py', raiz / 'cli.py', raiz / 'acoes.py']
    for arq in arquivos_:
        texto = arq.read_text(encoding='utf-8').lower()
        for proibido in ('sem nomes da empresa', 'nunca escreva nomes', 'nunca cite nomes', 'nem cite nomes'):
            assert proibido not in texto, (arq.name, proibido)
