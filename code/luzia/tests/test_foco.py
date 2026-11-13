"""Foco da Luzia: hooks (observer), linha de status e o comando `foco` para agentes sem hooks."""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from luzia import banco, observer, pipeline

CODE = Path(__file__).resolve().parents[2]
DDD = 'Domain-Driven Design (DDD)'
TESTES = 'Testes e Qualidade / SQL'


def _consulta(sql, *args):
    con = banco.conectar()
    try:
        return con.execute(sql, args).fetchall()
    finally:
        con.close()


def _script(privado, nome, entrada, extra_env=None):
    """Roda o arquivo como o harness roda; stdin e stdout em bytes UTF-8 (o pipe real não passa pela página de código)."""
    r = subprocess.run([sys.executable, str(CODE / 'luzia' / nome)], input=entrada.encode('utf-8'), capture_output=True,
                       env={**os.environ, 'LUZIA_PRIVATE': str(privado), **(extra_env or {})}, cwd=CODE.parent)
    return subprocess.CompletedProcess(r.args, r.returncode, r.stdout.decode('utf-8'), r.stderr.decode('utf-8', 'replace'))


# ------------------------------------------------------------------ B1
def test_statusline_roda_como_script(privado):
    """O Claude Code executa `python statusline.py`: sem pacote, só com o caminho do arquivo."""
    repo = json.loads((privado / 'observer.json').read_text(encoding='utf-8'))['autorizados'][0]
    r = _script(privado, 'statusline.py', json.dumps({'workspace': {'current_dir': repo}}))
    assert r.returncode == 0, r.stderr
    assert r.stdout.startswith('✦ Luzia · em foco'), r.stdout + r.stderr


def test_statusline_fora_do_repositorio_autorizado_nao_imprime(privado, tmp_path):
    r = _script(privado, 'statusline.py', json.dumps({'workspace': {'current_dir': str(tmp_path / 'outro')}}))
    assert r.returncode == 0, r.stderr
    assert r.stdout == ''


def test_statusline_como_modulo(privado):
    from luzia import statusline
    repo = json.loads((privado / 'observer.json').read_text(encoding='utf-8'))['autorizados'][0]
    assert statusline.linha({'workspace': {'current_dir': repo}}).startswith('✦ Luzia')


def test_observer_script_le_prompt_com_acentos_em_utf8(privado):
    """O pipe do Windows não pode estragar acentos do prompt: 'subdomínio' é palavra do prisma DDD."""
    repo = json.loads((privado / 'observer.json').read_text(encoding='utf-8'))['autorizados'][0]
    evento = {'hook_event_name': 'UserPromptSubmit', 'session_id': 's-acento', 'cwd': repo,
              'prompt': 'separe o subdomínio de cobrança'}
    r = _script(privado, 'observer.py', json.dumps(evento, ensure_ascii=False))
    assert r.returncode == 0, r.stderr
    assert 'luz própria' in json.loads(r.stdout)['hookSpecificOutput']['additionalContext']


# ------------------------------------------------------------------ B2 · o lampejo mostra os lúmens de verdade
def _evento(privado, conteudo='class Pedido : Aggregate { }', sessao='s-b2'):
    cfg = json.loads((privado / 'observer.json').read_text(encoding='utf-8'))
    return {'session_id': sessao, 'tool_name': 'Write', 'cwd': cfg['autorizados'][0],
            'tool_input': {'file_path': 'Pedido.cs', 'content': conteudo}}, cfg


def _encher_teto(prisma, lm):
    from luzia import jogo
    jogo.lancar(prisma, lm, 'refletida', 'passivo-refletida', 'antes')


def test_lampejo_mostra_os_lumens_reais_do_teto_do_dia(privado, capsys):
    _encher_teto(DDD, 35)  # sobram 5 lm hoje
    evento, cfg = _evento(privado)
    observer.ao_usar_ferramenta(evento, cfg)
    saida = json.loads(capsys.readouterr().out)['hookSpecificOutput']['additionalContext']
    assert '+5 lm' in saida and '+10 lm' not in saida


def test_sem_lumens_no_dia_nao_ha_card_nem_lampejo(privado, capsys):
    _encher_teto(DDD, 40)
    evento, cfg = _evento(privado)
    observer.ao_usar_ferramenta(evento, cfg)
    assert capsys.readouterr().out == ''
    assert _consulta('SELECT 1 FROM lampejo') == []
    assert [r['lm'] for r in _consulta('SELECT lm FROM sessao_evento')] == [0]  # o reconhecimento da sessão fica registrado


def test_card_de_reconhecimento_pendurado_nao_promete_lampejo(privado, monkeypatch, capsys):
    """Com o banco ocupado o valor é provisório e o lampejo pode nunca nascer: o card não convida a responder."""
    monkeypatch.setattr(banco, 'gravar_ou_pendurar', lambda *a, **k: False)
    evento, cfg = _evento(privado)
    observer.ao_usar_ferramenta(evento, cfg)
    saida = json.loads(capsys.readouterr().out)['hookSpecificOutput']['additionalContext']
    assert 'a confirmar' in saida
    assert 'AskUserQuestion' not in saida and 'Responder agora' not in saida


def test_lampejo_passa_para_o_proximo_prisma_se_o_primeiro_estava_no_teto(privado, capsys):
    _encher_teto(DDD, 40)
    evento, cfg = _evento(privado, conteudo='Aggregate e xunit Assert')
    observer.ao_usar_ferramenta(evento, cfg)
    saida = json.loads(capsys.readouterr().out)['hookSpecificOutput']['additionalContext']
    assert f'o prisma {TESTES}' in saida and f'Prisma {TESTES}' not in saida and '+10 lm' in saida
    assert [r['prisma'] for r in _consulta('SELECT prisma FROM lampejo')] == [TESTES]


# ------------------------------------------------------------------ B3 · palavras do banco
def test_prisma_incluido_por_pedido_ganha_lumens_pelas_palavras_do_banco(privado, capsys):
    con = banco.conectar()
    try:
        with banco.transacao(con):
            con.execute("INSERT INTO prisma (nome, palavras_json, nivel, meta, estado, origem) "
                        "VALUES ('Observabilidade', '[\"OpenTelemetry\", \"tracing\"]', 0, 3, 'ativo', 'pedido')")
    finally:
        con.close()
    evento, cfg = _evento(privado, conteudo='using OpenTelemetry; // sem nenhuma palavra dos outros prismas')
    observer.ao_usar_ferramenta(evento, cfg)
    saida = json.loads(capsys.readouterr().out)['hookSpecificOutput']['additionalContext']
    assert 'o prisma Observabilidade' in saida
    assert [(r['prisma'], r['lm']) for r in _consulta('SELECT prisma, lm FROM lumen')] == [('Observabilidade', 10)]


def test_prisma_arquivado_nao_ganha_lumens(privado, capsys):
    con = banco.conectar()
    try:
        with banco.transacao(con):
            con.execute("INSERT INTO prisma (nome, palavras_json, nivel, meta, estado, origem) "
                        "VALUES ('Observabilidade', '[\"OpenTelemetry\"]', 0, 3, 'arquivado', 'pedido')")
    finally:
        con.close()
    evento, cfg = _evento(privado, conteudo='using OpenTelemetry;')
    observer.ao_usar_ferramenta(evento, cfg)
    assert _consulta('SELECT 1 FROM lumen') == []
