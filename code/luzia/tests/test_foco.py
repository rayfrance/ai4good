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
