"""Instala a Luzia num agente.

Jeito recomendado no Claude Code (plugin, sem caminho fixo):
    claude plugin marketplace add <pasta do repositório>
    claude plugin install luzia@ai4good

Sem o sistema de plugins (ou para outros agentes):
    python -m luzia.instalar               copia os comandos /luzia:* para ~/.claude/commands/luzia (caminhos resolvidos)
    python -m luzia.instalar --hooks       também registra o observador em ~/.claude/settings.json (com backup)
    python -m luzia.instalar --statusline  também liga a linha de status da Luzia (com backup; não troca uma que já exista)
    python -m luzia.instalar --regras      imprime o bloco de regras para Codex, Cursor ou Antigravity, com o caminho certo

Não use o modo manual junto com o plugin: os hooks rodariam duas vezes.
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from datetime import datetime
from pathlib import Path

from . import arquivos

HERE = Path(__file__).resolve().parent
CLAUDE = Path.home() / '.claude'
SETTINGS = CLAUDE / 'settings.json'
OBSERVER = f'"{Path(sys.executable).as_posix()}" "{(HERE / "observer.py").as_posix()}"'
STATUS = f'"{Path(sys.executable).as_posix()}" "{(HERE / "statusline.py").as_posix()}"'


def resolver(texto: str) -> str:
    return texto.replace('${CLAUDE_PLUGIN_ROOT}', HERE.as_posix())


def comandos() -> int:
    destino = CLAUDE / 'commands' / 'luzia'
    destino.mkdir(parents=True, exist_ok=True)
    fontes = sorted((HERE / 'commands').glob('*.md'))
    for velho in destino.glob('*.md'):  # comando que saiu da Luzia (ex.: senha.md) não fica quebrado no agente
        if velho.name not in {md.name for md in fontes}:
            velho.unlink()
    n = 0
    for md in fontes:
        (destino / md.name).write_text(resolver(md.read_text(encoding='utf-8')), encoding='utf-8')
        n += 1
    for skill in ('luzia-mentor', 'luzia-observador'):
        pasta = CLAUDE / 'skills' / skill
        pasta.mkdir(parents=True, exist_ok=True)
        (pasta / 'SKILL.md').write_text(resolver((HERE / 'skills' / skill / 'SKILL.md').read_text(encoding='utf-8')), encoding='utf-8')
    return n


def _settings() -> dict:
    dados = arquivos.ler_json(SETTINGS, {})
    if SETTINGS.exists():
        shutil.copy2(SETTINGS, SETTINGS.with_name(f'settings.json.antes-luzia-{datetime.now():%Y%m%d-%H%M%S}'))
    return dados


def hooks() -> list[str]:
    dados = _settings()
    feitos = []
    for evento, matcher in (('SessionStart', None), ('UserPromptSubmit', None), ('PostToolUse', 'Edit|Write|MultiEdit|Bash')):
        lista = dados.setdefault('hooks', {}).setdefault(evento, [])
        if any('observer.py' in h.get('command', '') for g in lista for h in g.get('hooks', [])):
            continue
        grupo = {'hooks': [{'type': 'command', 'command': OBSERVER, 'timeout': 10}]}
        if matcher:
            grupo = {'matcher': matcher, **grupo}
        lista.append(grupo)
        feitos.append(evento)
    arquivos.gravar_json(SETTINGS, dados)
    return feitos


def statusline() -> str:
    dados = _settings()
    atual = (dados.get('statusLine') or {}).get('command', '')
    if atual and 'statusline.py' not in atual:
        return 'já existe outra linha de status; deixei a sua como está'
    dados['statusLine'] = {'type': 'command', 'command': STATUS, 'padding': 0}
    arquivos.gravar_json(SETTINGS, dados)
    return 'linha de status ligada'


def regras() -> str:
    return resolver((HERE / 'harness' / 'REGRAS.md').read_text(encoding='utf-8')).replace('<LUZIA_CLI>', arquivos.CLI)


def main() -> None:
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    ap = argparse.ArgumentParser(description='Instala a Luzia sem o sistema de plugins')
    ap.add_argument('--hooks', action='store_true')
    ap.add_argument('--statusline', action='store_true')
    ap.add_argument('--regras', action='store_true')
    a = ap.parse_args()
    if a.regras:
        print(regras())
        return
    print(f'✦ {comandos()} comandos /luzia:* e 2 skills em {CLAUDE}')
    if a.hooks:
        feitos = hooks()
        print(f"✦ hooks: {', '.join(feitos) if feitos else 'já estavam registrados'}")
    if a.statusline:
        print(f'✦ {statusline()}')


if __name__ == '__main__':
    main()
