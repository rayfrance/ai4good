"""O agente só entrega o link de entrada ao painel verdadeiro: 127.0.0.1, porta exclusiva e prova do segredo privado.

Também: painel antigo é reiniciado, link bom entra mesmo sob tentativas ruins, instalador limpa comandos velhos,
máquina sem tela recebe o link no chat e banco bloqueado vira 503 claro. Sem modelo real; servidores em thread.
"""

from __future__ import annotations

import io
import json
import os
import socket
import sys
import threading
from contextlib import redirect_stdout
from http.server import BaseHTTPRequestHandler

import pytest

from luzia import acesso, arquivos, banco, cli, instalar, server


def _cli(monkeypatch, *argv):
    monkeypatch.setattr(sys, 'argv', ['luzia', *argv])
    buf = io.StringIO()
    with redirect_stdout(buf):
        cli.main()
    return buf.getvalue()


def _links() -> int:
    con = banco.conectar()
    try:
        return con.execute('SELECT COUNT(*) FROM acesso_link').fetchone()[0]
    finally:
        con.close()


@pytest.fixture
def navegador(monkeypatch):
    import webbrowser
    abertos: list[str] = []
    monkeypatch.setattr(webbrowser, 'open', lambda url, *a, **k: abertos.append(url) or True)
    monkeypatch.setattr(cli, '_sem_tela', lambda: False)
    return abertos


@pytest.fixture
def painel_real(servidor, monkeypatch):
    """O servidor de teste publica a identidade (como `server.main`) e o chat aponta para ele."""
    server.publicar_identidade()
    monkeypatch.setattr(cli, 'PAINEL', f'http://127.0.0.1:{servidor.port}')
    monkeypatch.setattr(cli, 'start_panel', lambda: pytest.fail('não devia ligar outro painel'))
    return servidor


class _Impostor(BaseHTTPRequestHandler):
    def log_message(self, *_):
        pass

    def do_GET(self):  # responde ao ping como a Luzia, mas sem saber o segredo
        corpo = json.dumps({'ok': True, 'prova': '00' * 32, 'versao': arquivos.versao_codigo(),
                            'esquema': banco.ESQUEMA_VERSAO, 'pid': 1}).encode()
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(corpo)))
        self.end_headers()
        self.wfile.write(corpo)


@pytest.fixture
def impostor(privado, monkeypatch):
    httpd = server.ThreadingHTTPServer(('127.0.0.1', 0), _Impostor)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    monkeypatch.setattr(cli, 'PAINEL', f'http://127.0.0.1:{httpd.server_address[1]}')
    yield httpd
    httpd.shutdown()
    httpd.server_close()


# ------------------------------------------------------------------ 127.0.0.1 e porta exclusiva
def test_painel_so_em_127_0_0_1():
    assert cli.PAINEL == 'http://127.0.0.1:8501'
    assert server.HOSTS_OK == {'127.0.0.1:8501'} and server.ORIGENS_OK == {'http://127.0.0.1:8501'}


def test_porta_do_painel_e_exclusiva(privado):
    httpd = server.ServidorPainel(('127.0.0.1', 0), server.Handler)
    try:
        assert httpd.allow_reuse_address is False
        porta = httpd.server_address[1]
        intruso = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            intruso.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)  # o truque de quem quer ocupar a porta
            with pytest.raises(OSError):
                intruso.bind(('127.0.0.1', porta))
        finally:
            intruso.close()
    finally:
        httpd.server_close()


# ------------------------------------------------------------------ prova do segredo
def test_ping_com_desafio_prova_o_segredo_sem_revelar(painel_real, privado):
    ident = json.loads((privado / 'painel.json').read_text(encoding='utf-8'))
    assert ident['pid'] == os.getpid() and len(bytes.fromhex(ident['segredo'])) == 32
    c, r, _ = painel_real.pedir('GET', '/api/ping?desafio=' + 'ab' * 16)
    assert c == 200 and r['prova'] and ident['segredo'] not in json.dumps(r)
    assert r['versao'] == arquivos.versao_codigo() and r['esquema'] == banco.ESQUEMA_VERSAO
    assert painel_real.pedir('GET', '/api/ping')[1] == {'ok': True}  # sem desafio: nada além de ok
    estado, info = cli.identidade_do_painel()
    assert estado == 'ok' and info['pid'] == os.getpid()


def test_impostor_na_porta_nao_recebe_link(impostor, privado, navegador, monkeypatch):
    (privado / 'painel.json').write_text(json.dumps({'segredo': 'cd' * 32, 'pid': 1}), encoding='utf-8')
    monkeypatch.setattr(cli, 'start_panel', lambda: pytest.fail('não devia ligar outro painel'))
    assert cli.identidade_do_painel()[0] == 'estranho'
    saida = _cli(monkeypatch, 'career-map')
    assert navegador == [] and _links() == 0 and '#entrar=' not in saida
    assert 'não gerei o link' in saida and 'LUZIA_BOTOES=' in saida


def test_impostor_sem_arquivo_de_identidade_tambem_nao_recebe(impostor, privado, navegador, monkeypatch):
    monkeypatch.setattr(cli, 'start_panel', lambda: pytest.fail('não devia ligar outro painel'))
    saida = _cli(monkeypatch, 'career-map')
    assert navegador == [] and _links() == 0 and '#entrar=' not in saida


def test_painel_verdadeiro_recebe_o_link_em_127(painel_real, navegador, monkeypatch):
    saida = _cli(monkeypatch, 'career-map')
    assert len(navegador) == 1 and navegador[0].startswith(cli.PAINEL + '/#entrar=') and '?' not in navegador[0]
    assert navegador[0].split('#entrar=')[1] not in saida


def test_sem_painel_liga_e_confere_antes_do_link(servidor, privado, navegador, monkeypatch):
    porta_livre = socket.socket()
    porta_livre.bind(('127.0.0.1', 0))
    vazia = porta_livre.getsockname()[1]
    porta_livre.close()
    monkeypatch.setattr(cli, 'PAINEL', f'http://127.0.0.1:{vazia}')
    ligados = []

    def ligar():  # "liga" apontando o chat para o servidor de teste, já com identidade
        ligados.append(1)
        server.publicar_identidade()
        monkeypatch.setattr(cli, 'PAINEL', f'http://127.0.0.1:{servidor.port}')

    monkeypatch.setattr(cli, 'start_panel', ligar)
    _cli(monkeypatch, 'career-map')
    assert ligados == [1] and len(navegador) == 1


# ------------------------------------------------------------------ painel de versão antiga
def test_painel_de_versao_antiga_e_reiniciado(painel_real, navegador, monkeypatch):
    monkeypatch.setattr(server, 'VERSAO', 'versao-velha')
    encerrados, ligados = [], []

    def encerrar(pid):
        encerrados.append(pid)
        monkeypatch.setattr(server, 'VERSAO', arquivos.versao_codigo())  # o "novo" servidor sobe com o código atual

    monkeypatch.setattr(cli, '_encerrar_painel', encerrar)
    monkeypatch.setattr(cli, 'start_panel', lambda: ligados.append(1))
    _cli(monkeypatch, 'career-map')
    assert encerrados == [os.getpid()] and ligados == [1] and len(navegador) == 1


def test_encerrar_nunca_mata_o_proprio_processo_nem_pid_invalido(monkeypatch):
    mortos = []
    monkeypatch.setattr(os, 'kill', lambda pid, sinal: mortos.append(pid))
    monkeypatch.setattr(cli, 'identidade_do_painel', lambda: ('ausente', {}))
    for pid in (os.getpid(), 0, -1, None, 'x'):
        cli._encerrar_painel(pid)
    assert mortos == []
    cli._encerrar_painel(424242)
    assert mortos == [424242]


# ------------------------------------------------------------------ demais itens da revisão
def test_link_bom_entra_mesmo_depois_de_muitas_tentativas_ruins(servidor):
    for i in range(acesso.LIMITE_LINKS + 3):
        c, _, _ = servidor.pedir('POST', '/api/acesso/link', {'token': f'ruim-{i}-' + 'q' * 30})
        assert c in (401, 429)
    assert servidor.pedir('POST', '/api/acesso/link', {'token': 'ruim-de-novo-' + 'q' * 30})[0] == 429
    assert servidor.pedir('POST', '/api/acesso/link', {'token': acesso.emitir_link()})[0] == 200


def test_link_novo_encerra_a_sessao_do_cookie_que_chegou(servidor):
    servidor.entrar()
    antiga = servidor.cookie
    assert servidor.pedir('POST', '/api/acesso/link', {'token': acesso.emitir_link()})[0] == 200
    nova = servidor.cookie
    assert nova != antiga
    servidor.cookie = antiga
    assert servidor.pedir('GET', '/api/estado')[0] == 401
    servidor.cookie = nova
    assert servidor.pedir('GET', '/api/estado')[0] == 200


def test_instalador_apaga_comandos_que_sairam_da_luzia(privado, tmp_path, monkeypatch):
    claude = tmp_path / 'casa' / '.claude'
    monkeypatch.setattr(instalar, 'CLAUDE', claude)
    destino = claude / 'commands' / 'luzia'
    destino.mkdir(parents=True)
    (destino / 'senha.md').write_text('antigo', encoding='utf-8')
    (destino / 'anotacao.txt').write_text('da pessoa', encoding='utf-8')
    vizinho = claude / 'commands' / 'outro'
    vizinho.mkdir()
    (vizinho / 'senha.md').write_text('de outro plugin', encoding='utf-8')
    instalar.comandos()
    assert not (destino / 'senha.md').exists() and (destino / 'acesso.md').exists()
    assert (destino / 'anotacao.txt').exists() and (vizinho / 'senha.md').exists()


def test_maquina_sem_tela_recebe_o_link_no_chat_mesmo_se_o_navegador_diz_que_abriu(painel_real, monkeypatch):
    import webbrowser
    monkeypatch.setattr(webbrowser, 'open', lambda *a, **k: True)
    monkeypatch.setattr(cli, '_sem_tela', lambda: True)
    saida = _cli(monkeypatch, 'career-map')
    assert saida.count('#entrar=') == 1 and '2 minutos' in saida


def test_sem_tela_detecta_posix_sem_display_e_ssh(monkeypatch):
    for var in ('DISPLAY', 'WAYLAND_DISPLAY', 'SSH_CONNECTION', 'SSH_TTY'):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setattr(sys, 'platform', 'linux')
    assert cli._sem_tela() is True
    monkeypatch.setenv('DISPLAY', ':0')
    assert cli._sem_tela() is False
    monkeypatch.setenv('SSH_CONNECTION', '1 2 3 4')
    assert cli._sem_tela() is True
    monkeypatch.delenv('SSH_CONNECTION')
    monkeypatch.setattr(sys, 'platform', 'win32')
    assert cli._sem_tela() is False


def test_banco_bloqueado_na_migracao_vira_503_claro(servidor, monkeypatch):
    def bloqueado():
        raise RuntimeError('migração bloqueada: veja private/erros.log')

    servidor.entrar()
    monkeypatch.setattr(acesso, '_abrir', bloqueado)
    c, r, _ = servidor.pedir('GET', '/api/acesso/estado')
    assert c == 503 and 'migração bloqueada' in r['erro']
    c, r, _ = servidor.pedir('GET', '/api/estado')
    assert c == 503 and 'migração bloqueada' in r['erro']
    assert servidor.pedir('POST', '/api/acesso/link', {'token': 'x' * 43})[0] == 503
