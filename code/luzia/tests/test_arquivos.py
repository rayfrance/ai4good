"""A pasta privada vem de LUZIA_PRIVATE e todos os módulos derivam seus caminhos dela."""

import json
import os
import subprocess
import sys
from pathlib import Path

from luzia.tests.conftest import REAL, caminhos_privados

CODE = Path(__file__).resolve().parents[2]


def test_private_vem_do_ambiente(privado):
    from luzia import arquivos, jogo

    assert arquivos.PRIVATE == Path(privado) == Path(os.environ['LUZIA_PRIVATE'])
    assert jogo.FEIXES.parent == Path(privado)


def test_sem_ambiente_usa_a_pasta_private_do_pacote():
    # Só calcula o caminho num processo separado: importar arquivos não abre a pasta.
    env = {k: v for k, v in os.environ.items() if k != 'LUZIA_PRIVATE'}
    out = subprocess.run([sys.executable, '-c', 'from luzia import arquivos; print(arquivos.PRIVATE)'],
                         cwd=CODE, env=env, capture_output=True, text=True, check=True).stdout.strip()
    assert Path(out) == REAL


def test_nenhum_caminho_aponta_para_a_pasta_real(privado):
    for nome, caminho in caminhos_privados().items():
        assert not Path(caminho).is_relative_to(REAL), nome


def test_observer_roda_como_script_na_pasta_do_ambiente(privado):
    """O hook real roda `python code/luzia/observer.py`: ele precisa importar e gravar na pasta de LUZIA_PRIVATE."""
    repo = json.loads((privado / 'observer.json').read_text(encoding='utf-8'))['autorizados'][0]
    evento = {'hook_event_name': 'PostToolUse', 'session_id': 's-script', 'cwd': repo, 'tool_name': 'Write',
              'tool_input': {'file_path': 'Pedido.cs', 'content': 'class Pedido : Aggregate { }'}}
    r = subprocess.run([sys.executable, str(CODE / 'luzia' / 'observer.py')], input=json.dumps(evento),
                       env={**os.environ, 'LUZIA_PRIVATE': str(privado)}, capture_output=True, text=True, check=True)
    assert 'luz refletida' in r.stdout
    assert (privado / 'lumens.jsonl').exists() and (privado / 'cartoes.json').exists()
