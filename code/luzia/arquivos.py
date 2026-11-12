"""Leitura e gravação seguras dos arquivos locais da Luzia (hook, CLI e painel escrevem ao mesmo tempo).

- Gravação atômica: escreve num temporário na mesma pasta e troca com `os.replace`, então nunca fica meio arquivo.
- Leitura que não apaga: se um arquivo existe mas está corrompido, uma cópia vai para `<nome>.corrompido-<data>`
  antes de a Luzia seguir com o valor padrão, e o erro vai para `private/erros.log`.
- O log guarda só onde e o tipo do erro: nunca texto de prompt, código ou caminhos de trabalho.
"""

from __future__ import annotations

import json
import os
import shutil
import tempfile
import time
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
# Pasta dos dados pessoais (fora do git). LUZIA_PRIVATE troca o lugar (os testes apontam para uma pasta temporária).
PRIVATE = Path(os.environ['LUZIA_PRIVATE']) if os.environ.get('LUZIA_PRIVATE') else HERE / 'private'
ERROS = PRIVATE / 'erros.log'
# Estado vivo da carreira (plano, entregas, trechos): privado, muda a cada chamada.
ESTADO = PRIVATE / 'career_state.json'
# Foto congelada do seminário sem2 (versionada); só serve para migrar quem ainda não tem o estado privado.
ESTADO_LEGADO = HERE.parents[1] / 'outputs' / 'sem2' / 'career_state.json'
# Como qualquer agente chama a CLI da Luzia, a partir de onde ela está instalada (sem caminho fixo).
CLI = f'cd "{HERE.parent.as_posix()}" && python -m luzia.cli'


def registrar_erro(onde: str, erro: BaseException | str) -> None:
    try:
        PRIVATE.mkdir(parents=True, exist_ok=True)
        tipo = erro if isinstance(erro, str) else type(erro).__name__
        with ERROS.open('a', encoding='utf-8') as f:
            f.write(json.dumps({'quando': datetime.now().isoformat(timespec='seconds'), 'onde': onde, 'erro': tipo},
                               ensure_ascii=False) + '\n')
    except Exception:
        pass  # o log de erro nunca pode derrubar quem chamou


def _guardar_corrompido(path: Path) -> str:
    """Copia o arquivo ruim uma vez (o nome usa a data da última alteração, então não repete a cada leitura)."""
    try:
        marca = datetime.fromtimestamp(path.stat().st_mtime).strftime('%Y%m%d-%H%M%S')
        copia = path.with_name(f'{path.name}.corrompido-{marca}')
        if not copia.exists():
            shutil.copy2(path, copia)
        return copia.name
    except OSError:
        return 'sem cópia'


def ler_json(path: Path, padrao):
    try:
        texto = path.read_text(encoding='utf-8')
    except FileNotFoundError:
        return padrao
    except OSError as e:
        registrar_erro(f'ler {path.name}', e)
        return padrao
    try:
        return json.loads(texto)
    except ValueError as e:
        registrar_erro(f'ler {path.name} (cópia em {_guardar_corrompido(path)})', e)
        return padrao


def gravar_texto(path: Path, texto: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=f'.{path.name}.', suffix='.tmp', dir=path.parent)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8', newline='') as f:
            f.write(texto)
            f.flush()
            os.fsync(f.fileno())
        for tentativa in range(6):
            try:
                os.replace(tmp, path)
                return
            except PermissionError:  # Windows: outro processo está lendo o arquivo neste instante
                time.sleep(0.05 * (tentativa + 1))
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def gravar_json(path: Path, dados, indent: int | None = 2) -> None:
    gravar_texto(path, json.dumps(dados, ensure_ascii=False, indent=indent))


def ler_estado() -> dict:
    """Estado vivo da carreira. Na primeira vez, copia a foto do sem2 para a pasta privada."""
    if not ESTADO.exists() and ESTADO_LEGADO.exists():
        PRIVATE.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ESTADO_LEGADO, ESTADO)
    return ler_json(ESTADO, {})
