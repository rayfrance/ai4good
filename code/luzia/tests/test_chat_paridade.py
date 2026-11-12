"""Paridade chat/painel: modelo, agente, pedidos (ajustar/arquivar) e os arquivos de comando."""

import io
import json
import re
import sys
from contextlib import redirect_stdout
from pathlib import Path
from types import SimpleNamespace

import pytest

from luzia import cli, modelo, pedidos, pipeline, trajetoria

COMANDOS = Path(__file__).resolve().parents[1] / 'commands'
DDD = 'Domain-Driven Design (DDD)'


def rodar(monkeypatch, *argv):
    monkeypatch.setattr(sys, 'argv', ['luzia', *[str(a) for a in argv]])
    buf = io.StringIO()
    with redirect_stdout(buf):
        cli.main()
    return buf.getvalue()


def botoes_de(saida):
    linha = next((x for x in saida.splitlines() if x.startswith('LUZIA_BOTOES=')), None)
    return json.loads(linha.split('=', 1)[1]) if linha else []


def visivel(saida):
    return '\n'.join(l for l in saida.splitlines() if not l.startswith('LUZIA_'))


def _modelo_falso(monkeypatch):
    chamadas = []

    def fake(payload, **kw):
        chamadas.append(payload)
        ped = payload.get('pedido') or {}
        nv = ped.get('nivel_solicitado') if ped.get('nivel_solicitado') is not None else 1
        mt = ped.get('meta_solicitada') if ped.get('meta_solicitada') is not None else 3
        res = {'nivel_partida': nv, 'meta': mt, 'palavras_chave': ['tracing'], 'acoes': [], 'analise': f'Nível {nv}, meta {mt}.'}
        return SimpleNamespace(plan=res, model='m/x'), {'quando': '2026-11-12T15:00:00', 'modelo': 'm/x'}

    monkeypatch.setattr(pipeline, 'run_plan', fake)
    return chamadas


# ------------------------------------------------------------------ modelo e agente
def test_modelo_usar_troca_provedor_e_modelo_sem_pedir_chave(privado, monkeypatch):
    saida = rodar(monkeypatch, 'modelo', 'usar', 'anthropic', 'claude-sonnet-5-5')
    assert modelo.config()['provedor'] == 'anthropic' and modelo.config()['modelo'] == 'claude-sonnet-5-5'
    assert 'claude-sonnet-5-5' in saida and 'painel' in saida and '.env' in saida
    assert botoes_de(saida)


def test_modelo_usar_recusa_provedor_invalido_e_chave_no_chat(privado, monkeypatch):
    antes = modelo.config()
    saida = rodar(monkeypatch, 'modelo', 'usar', 'inventado', 'x')
    assert 'provedor' in visivel(saida) and botoes_de(saida) and modelo.config() == antes
    saida = rodar(monkeypatch, 'modelo', 'usar', 'gemini', 'gemini-2.5-flash', '--chave', 'SEGREDO123')
    assert 'SEGREDO123' not in saida and 'chave' in visivel(saida) and modelo.config() == antes
    assert not any('SEGREDO123' in a.read_text(encoding='utf-8', errors='ignore') for a in privado.rglob('*') if a.is_file())


def test_agente_mostra_e_troca(privado, monkeypatch):
    saida = rodar(monkeypatch, 'agente')
    assert 'claude-code' in saida and botoes_de(saida)
    saida = rodar(monkeypatch, 'agente', 'antigravity')
    assert json.loads((privado / 'observer.json').read_text(encoding='utf-8'))['agente'] == 'antigravity'
    assert 'antigravity' in visivel(saida)
    saida = rodar(monkeypatch, 'agente', 'inventado')
    assert 'desconhecido' in visivel(saida) and json.loads((privado / 'observer.json').read_text(encoding='utf-8'))['agente'] == 'antigravity'
    assert botoes_de(saida)


# ------------------------------------------------------------------ pedidos
def test_ajustar_sem_valores_pergunta_nivel_e_meta_em_vez_de_reenviar_os_mesmos(privado, monkeypatch):
    chamadas = _modelo_falso(monkeypatch)
    abrir = rodar(monkeypatch, 'pedido', 'abrir', 'incluir', 'Observabilidade')
    ajustar = next(b for b in botoes_de(abrir) if 'Ajustar' in b['rotulo'])
    assert '--nivel' not in ajustar['rodar'] and '--meta' not in ajustar['rodar']
    n = len(chamadas)
    saida = rodar(monkeypatch, *ajustar['rodar'].split())
    assert len(chamadas) == n  # nada foi recalculado com os mesmos valores
    v = visivel(saida)
    assert 'nível' in v and 'meta' in v and '--nivel' in v and '--meta' in v
    assert botoes_de(saida)
    saida = rodar(monkeypatch, 'pedido', 'ajustar', '1', '--nivel', '2', '--meta', '4')
    assert len(chamadas) == n + 1 and 'Nível 2, meta 4' in saida


def test_arquivar_e_reativar_nao_oferecem_ajustar_com_valores_inventados(privado, monkeypatch):
    _modelo_falso(monkeypatch)
    saida = rodar(monkeypatch, 'pedido', 'abrir', 'arquivar', DDD, '--motivo', 'teste')
    rotulos = [b['rotulo'] for b in botoes_de(saida)]
    assert any('Aceitar' in r for r in rotulos) and any('Recusar' in r for r in rotulos)
    assert not any('Ajustar' in r for r in rotulos)
    assert not any('--nivel' in b['rodar'] for b in botoes_de(saida))
    saida = rodar(monkeypatch, 'pedido', 'ajustar', '1')
    assert 'não tem nível' in visivel(saida) and botoes_de(saida)


# ------------------------------------------------------------------ arquivos de comando
@pytest.mark.parametrize('arquivo', sorted(COMANDOS.glob('*.md')), ids=lambda p: p.name)
def test_description_dos_comandos_entre_aspas(arquivo):
    topo = arquivo.read_text(encoding='utf-8').split('---')[1]
    linha = next(l for l in topo.splitlines() if l.startswith('description:'))
    assert re.fullmatch(r'description: ".*"', linha), f'{arquivo.name}: {linha}'
    for dica in (l[len('argument-hint:'):].strip() for l in topo.splitlines() if l.startswith('argument-hint:')):
        if dica.startswith('"'):  # entre aspas: as internas precisam estar escapadas, senão o YAML não abre
            interno = dica[1:-1].replace(chr(92) + '"', '')
            assert dica.endswith('"') and '"' not in interno, f'{arquivo.name}: {dica}'
        else:  # sem aspas: não pode ter aspas no meio
            assert '"' not in dica, f'{arquivo.name}: {dica}'


def test_trajetoria_repassa_os_argumentos():
    texto = (COMANDOS / 'trajetoria.md').read_text(encoding='utf-8')
    assert '$ARGUMENTS' in texto and 'argument-hint' in texto


@pytest.mark.parametrize('nome', ['identidade', 'leituras', 'acender-entrega'])
def test_comandos_novos_do_lote_a_tem_arquivo_de_comando(nome):
    texto = (COMANDOS / f'{nome}.md').read_text(encoding='utf-8')
    assert f'python -m luzia.cli {nome}' in texto and 'LUZIA_BOTOES' in texto
