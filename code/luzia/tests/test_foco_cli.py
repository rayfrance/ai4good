"""Comando `foco`: o mesmo reconhecimento dos hooks para agentes sem hooks (Antigravity, Codex, Cursor)."""

import io
import json
import os
import shlex
import subprocess
import sys
from contextlib import redirect_stdout
from pathlib import Path

import pytest

from luzia import banco, cli

CODE = Path(__file__).resolve().parents[2]
DDD = 'Domain-Driven Design (DDD)'


def _consulta(sql, *args):
    con = banco.conectar()
    try:
        return con.execute(sql, args).fetchall()
    finally:
        con.close()


def rodar(monkeypatch, *argv):
    monkeypatch.setattr(sys, 'argv', ['luzia', *[str(a) for a in argv]])
    buf = io.StringIO()
    with redirect_stdout(buf):
        cli.main()
    return buf.getvalue()


def botoes_de(saida):
    linha = next((x for x in saida.splitlines() if x.startswith('LUZIA_BOTOES=')), None)
    return json.loads(linha.split('=', 1)[1]) if linha else []


def _git(repo, *args):
    subprocess.run(['git', '-C', str(repo), '-c', 'user.name=Pessoa Teste', '-c', 'user.email=p@teste.local', *args],
                   check=True, capture_output=True)


@pytest.fixture
def repo(privado):
    pasta = Path(json.loads((privado / 'observer.json').read_text(encoding='utf-8'))['autorizados'][0])
    _git(pasta, 'init', '-q')
    (pasta / 'Pedido.cs').write_text('class Pedido { }\n', encoding='utf-8')
    _git(pasta, 'add', '.')
    _git(pasta, 'commit', '-q', '-m', 'init')
    return pasta


def _modo(privado, modo):
    cfg = json.loads((privado / 'observer.json').read_text(encoding='utf-8'))
    cfg['modo'] = modo
    (privado / 'observer.json').write_text(json.dumps(cfg), encoding='utf-8')


def _editar(repo, conteudo='class Pedido : Aggregate { }\n'):
    (repo / 'Pedido.cs').write_text(conteudo, encoding='utf-8')


def test_foco_arquivos_reconhece_luz_refletida_e_oferece_o_lampejo(privado, repo, monkeypatch):
    _editar(repo)
    saida = rodar(monkeypatch, 'foco', '--arquivos', 'Pedido.cs', '--cwd', repo, '--sessao', 's1')
    assert '✦ Centelha da sessão · DDD · +10 lm refletida' in saida
    bts = botoes_de(saida)
    assert [b['rotulo'] for b in bts] == ['Responder agora', 'Guardar']
    assert bts[0]['rodar'].startswith('lampejo --skill') and '--nota' in bts[0]['rodar']
    assert bts[1]['rodar'].startswith('guardar --skill')
    assert [(r['prisma'], r['lm'], r['luz']) for r in _consulta('SELECT * FROM lumen')] == [(DDD, 10, 'refletida')]
    assert [r['estado'] for r in _consulta('SELECT estado FROM lampejo')] == ['aberto']


def test_foco_nunca_guarda_codigo_nem_prompt(privado, repo, monkeypatch, tmp_path):
    _editar(repo, 'class Pedido : ZzAggregateSecreto { }\n')
    prompt = tmp_path / 'prompt.txt'
    prompt.write_text('quero um Aggregate chamado ZzPromptSecreto', encoding='utf-8')
    rodar(monkeypatch, 'foco', '--arquivos', 'Pedido.cs', '--cwd', repo, '--sessao', 's1')
    rodar(monkeypatch, 'foco', '--prompt-arquivo', prompt, '--cwd', repo, '--sessao', 's1')
    assert _consulta('SELECT 1 FROM lumen')  # os dois reconhecimentos aconteceram
    for arquivo in privado.rglob('*'):
        if arquivo.is_file():
            dados = arquivo.read_bytes()
            assert b'ZzAggregateSecreto' not in dados and b'ZzPromptSecreto' not in dados, arquivo.name


def test_foco_prompt_reconhece_luz_propria(privado, repo, monkeypatch, tmp_path):
    prompt = tmp_path / 'prompt.txt'
    prompt.write_text('modele o Aggregate de pedido separando o subdomínio', encoding='utf-8')
    saida = rodar(monkeypatch, 'foco', '--prompt-arquivo', prompt, '--cwd', repo, '--sessao', 's2')
    assert f'o prisma "{DDD}"' in saida and 'Luzia · DDD: você dirigiu' in saida and '+20 lm própria' in saida
    assert [(r['lm'], r['luz'], r['fonte']) for r in _consulta('SELECT * FROM lumen')] == [(20, 'propria', 'passivo-prompt')]
    assert _consulta('SELECT 1 FROM lampejo') == []  # o prompt dirigido não abre lampejo
    assert 'LUZIA_BOTOES=' in saida


def test_foco_uma_vez_por_prisma_por_sessao_e_teto_do_dia(privado, repo, monkeypatch):
    _editar(repo)
    rodar(monkeypatch, 'foco', '--arquivos', 'Pedido.cs', '--cwd', repo, '--sessao', 's3')
    repetido = rodar(monkeypatch, 'foco', '--arquivos', 'Pedido.cs', '--cwd', repo, '--sessao', 's3')
    assert 'Centelha da sessão' not in repetido and 'LUZIA_BOTOES=' in repetido
    assert len(_consulta('SELECT 1 FROM lumen')) == 1
    for sessao in ('s4', 's5', 's6'):  # 4 sessões × 10 lm = 40; a quinta não rende
        rodar(monkeypatch, 'foco', '--arquivos', 'Pedido.cs', '--cwd', repo, '--sessao', sessao)
    ultimo = rodar(monkeypatch, 'foco', '--arquivos', 'Pedido.cs', '--cwd', repo, '--sessao', 's7')
    assert sum(r['lm'] for r in _consulta('SELECT lm FROM lumen')) == 40
    assert 'Centelha da sessão' not in ultimo


def test_foco_sem_sessao_usa_um_id_diario_por_pasta(privado, repo, monkeypatch):
    _editar(repo)
    rodar(monkeypatch, 'foco', '--arquivos', 'Pedido.cs', '--cwd', repo)
    rodar(monkeypatch, 'foco', '--arquivos', 'Pedido.cs', '--cwd', repo)
    assert len(_consulta('SELECT 1 FROM lumen')) == 1


def test_foco_arquivo_novo_sem_commit_tambem_e_lido_pelo_git_diff(privado, repo, monkeypatch):
    (repo / 'Novo.cs').write_text('class Novo : Aggregate { }\n', encoding='utf-8')
    saida = rodar(monkeypatch, 'foco', '--arquivos', 'Novo.cs', '--cwd', repo, '--sessao', 's8')
    assert 'Centelha da sessão' in saida


def test_foco_em_silencio_registra_sem_lampejo(privado, repo, monkeypatch):
    _modo(privado, 'passivo')
    _editar(repo)
    saida = rodar(monkeypatch, 'foco', '--arquivos', 'Pedido.cs', '--cwd', repo, '--sessao', 's9')
    assert 'Centelha da sessão' not in saida and 'em silêncio' in saida
    assert len(_consulta('SELECT 1 FROM lumen')) == 1 and _consulta('SELECT 1 FROM lampejo') == []


def test_foco_fora_de_foco_e_repositorio_nao_autorizado_nao_observam(privado, repo, monkeypatch, tmp_path):
    _editar(repo)
    outro = tmp_path / 'outro'
    outro.mkdir()
    saida = rodar(monkeypatch, 'foco', '--arquivos', 'Pedido.cs', '--cwd', outro, '--sessao', 'sa')
    assert 'não está autorizada' in saida and 'LUZIA_BOTOES=' in saida
    _modo(privado, 'sob_demanda')
    saida = rodar(monkeypatch, 'foco', '--arquivos', 'Pedido.cs', '--cwd', repo, '--sessao', 'sb')
    assert 'fora de foco' in saida and 'LUZIA_BOTOES=' in saida
    assert _consulta('SELECT 1 FROM lumen') == []


def test_foco_sem_argumentos_explica_o_uso(privado, repo, monkeypatch):
    saida = rodar(monkeypatch, 'foco', '--cwd', repo)
    assert '--prompt-arquivo' in saida and '--arquivos' in saida and 'LUZIA_BOTOES=' in saida


def test_foco_fora_de_repositorio_git_avisa_sem_gravar(privado, repo, monkeypatch, tmp_path):
    cfg = json.loads((privado / 'observer.json').read_text(encoding='utf-8'))
    pasta = tmp_path / 'semgit'
    pasta.mkdir()
    cfg['autorizados'].append(str(pasta))
    (privado / 'observer.json').write_text(json.dumps(cfg), encoding='utf-8')
    (pasta / 'a.cs').write_text('Aggregate', encoding='utf-8')
    saida = rodar(monkeypatch, 'foco', '--arquivos', 'a.cs', '--cwd', pasta, '--sessao', 'sc')
    assert 'git' in saida.lower() and 'LUZIA_BOTOES=' in saida
    assert _consulta('SELECT 1 FROM lumen') == []


def test_botoes_do_foco_chamam_guardar_e_converter(privado, repo, monkeypatch):
    _editar(repo)
    bts = botoes_de(rodar(monkeypatch, 'foco', '--arquivos', 'Pedido.cs', '--cwd', repo, '--sessao', 'sd'))
    _editar(repo, 'class Pedido : Aggregate { int x; }' + chr(10))  # outra sessão, outro lampejo
    botoes_de(rodar(monkeypatch, 'foco', '--arquivos', 'Pedido.cs', '--cwd', repo, '--sessao', 'se'))
    guardar = rodar(monkeypatch, *shlex.split(bts[1]['rodar']))
    assert 'Guardada como centelha' in guardar
    converter = bts[0]['rodar'].replace('<0-4>', '4').replace('<1 linha do que a pessoa explicou>', 'separei o agregado')
    saida = rodar(monkeypatch, *shlex.split(converter))
    assert '** própria' in saida and '+30 lm' in saida
    assert sorted(r['estado'] for r in _consulta('SELECT estado FROM lampejo')) == ['convertido', 'guardado']


def test_foco_roda_como_a_cli_real(privado, repo):
    """A CLI é chamada de outra pasta (`cd code && python -m luzia.cli`): o projeto vem de --cwd."""
    _editar(repo)
    r = subprocess.run([sys.executable, '-m', 'luzia.cli', 'foco', '--arquivos', 'Pedido.cs', '--cwd', str(repo), '--sessao', 'sf'],
                       cwd=CODE, capture_output=True, env={**os.environ, 'LUZIA_PRIVATE': str(privado)})
    saida = r.stdout.decode('utf-8')
    assert r.returncode == 0, r.stderr.decode('utf-8', 'replace')
    assert 'Centelha da sessão' in saida and 'LUZIA_BOTOES=' in saida
