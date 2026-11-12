"""Base dos testes da Luzia: cada teste roda numa pasta privada temporária, com dados sintéticos.

Os testes nunca leem nem escrevem `code/luzia/private/` (dados pessoais reais, LGPD):
- antes de qualquer módulo da Luzia ser importado, LUZIA_PRIVATE já aponta para uma pasta sentinela temporária;
- a fixture `privado` confere que todo caminho privado dos módulos ficou dentro da pasta do teste.
"""

from __future__ import annotations

import importlib
import json
import os
import shutil
import tempfile
from pathlib import Path

import pytest

REAL = Path(__file__).resolve().parents[1] / 'private'  # só para comparar caminhos: nunca é aberta
_SENTINELA = Path(tempfile.mkdtemp(prefix='luzia-sentinela-'))
os.environ['LUZIA_PRIVATE'] = str(_SENTINELA)

# Módulos que calculam caminhos privados ao serem importados, na ordem de recarga (arquivos primeiro).
MODULOS_COM_CAMINHOS = ('arquivos', 'modelo', 'jogo', 'acoes', 'pipeline', 'observer', 'statusline')

SKILLS = [
    {'nome': 'Domain-Driven Design (DDD)', 'autoavaliacao': None, 'luzia_sugere': 1, 'alvo': 4,
     'evidencia': 'Entidades e repositórios aparecem nos commits, sem agregados explícitos.',
     'palavras_chave': ['Aggregate', 'ValueObject']},
    {'nome': 'Testes e Qualidade / SQL', 'autoavaliacao': None, 'luzia_sugere': 2, 'alvo': 4,
     'evidencia': 'Poucos testes automatizados nos commits recentes.',
     'palavras_chave': ['xunit', 'Assert']},
    {'nome': 'Front-end (JS / Razor / React)', 'autoavaliacao': None, 'luzia_sugere': 3, 'alvo': 4,
     'evidencia': 'Telas entregues com componentes reutilizados.',
     'palavras_chave': ['useState', 'componente']},
]


def _acao(titulo: str, skill: str, duracao: int) -> dict:
    return {'titulo': titulo, 'tipo': 'praticar', 'skill': skill, 'dimensao': None,
            'por_que': f'Fechar a lacuna de {skill}.', 'conceitos': [skill],
            'como': ['Escolha um trecho do código.', 'Explique a decisão com suas palavras.'],
            'onde_explorar': 'Uma mudança recente do repositório.',
            'prompt': f'Me faça uma pergunta sobre {skill} e espere minha resposta.', 'duracao_min': duracao}


def estado_sintetico() -> dict:
    """career_state.json fictício: 3 skills, 1 trecho de plano com 3 ações e 2 entregas recentes."""
    return {
        'atualizado_em': '2026-11-01T10:00:00',
        'plano': {
            'onde_esta': {'resumo': 'Pessoa desenvolvedora fictícia no nível Júnior 3.'},
            'aonde_quer_chegar': {'resumo': 'Chegar a Plena.', 'lacuna_principal': 'Modelagem de domínio.'},
            'skills': SKILLS,
            'tarefas_recentes': [
                {'tarefa': 'feat: cadastro de exemplo', 'skills': ['Domain-Driven Design (DDD)'], 'indice_propriedade': 60,
                 'p1_direcao_prompt': 65, 'p2_coesao_commit': 80, 'p3_aplicacao_conceitual': 40,
                 'p4_dominio_arquitetural': 30, 'risco_debito_tecnico': 'medio', 'passos_para_100': []},
                {'tarefa': 'test: cobertura do relatório de exemplo', 'skills': ['Testes e Qualidade / SQL'],
                 'indice_propriedade': 55, 'p1_direcao_prompt': 65, 'p2_coesao_commit': 70, 'p3_aplicacao_conceitual': 35,
                 'p4_dominio_arquitetural': 25, 'risco_debito_tecnico': 'baixo', 'passos_para_100': []},
            ],
            'p1_direcao_prompt': {'nota': 65},
            'plano': [{
                'horizonte': '3 meses', 'titulo': 'Primeiro trecho da rota',
                'acoes': [_acao('Modelar um agregado de exemplo', 'Domain-Driven Design (DDD)', 15),
                          _acao('Escrever um teste de unidade guiado', 'Testes e Qualidade / SQL', 20),
                          _acao('Extrair um componente de tela', 'Front-end (JS / Razor / React)', 10)],
            }],
        },
        'payload_anonimizado': {
            'triagem': {'nivel_atual_declarado': 'Júnior nível 3', 'objetivo_declarado': 'quero chegar a Plena',
                        'horizonte': '12 meses'},
            'commits_recentes': [],
        },
    }


def pytest_unconfigure(config):
    shutil.rmtree(_SENTINELA, ignore_errors=True)


def caminhos_privados() -> dict[str, Path]:
    """Todo caminho de dado pessoal que os módulos calculam ao serem importados."""
    from luzia import acoes, arquivos, jogo, modelo, observer, pipeline
    out = {f'arquivos.{n}': getattr(arquivos, n) for n in ('PRIVATE', 'ERROS', 'ESTADO')}
    out.update({f'jogo.{n}': getattr(jogo, n) for n in ('PRIVATE', 'FEIXES', 'LUMENS', 'DEGRAUS', 'AUTOAVAL', 'CARTOES', 'DOSSIES')})
    out.update({f'acoes.{n}': getattr(acoes, n) for n in ('PRIVATE', 'EVID', 'SALVAS', 'FILA')})
    out.update({f'pipeline.{n}': getattr(pipeline, n) for n in ('PRIVATE', 'STATE_FILE', 'AUTOAVAL', 'OBSERVER_CFG', 'SESSION_LOG')})
    out.update({f'observer.{n}': getattr(observer, n) for n in ('PRIVATE', 'CFG', 'LOG', 'SEEN')})
    out['modelo.CFG'] = modelo.CFG
    return out


def _escrever(path: Path, dados) -> None:
    path.write_text(json.dumps(dados, ensure_ascii=False, indent=2), encoding='utf-8')


@pytest.fixture
def privado(tmp_path, monkeypatch) -> Path:
    """Pasta privada temporária (LUZIA_PRIVATE) com dados sintéticos; recarrega os módulos que guardam caminhos."""
    pasta = tmp_path / 'private'
    repo = tmp_path / 'repo'
    pasta.mkdir()
    repo.mkdir()
    _escrever(pasta / 'entrada.json', {'repo': str(repo), 'author': 'Pessoa Teste', 'horizonte': '12 meses'})
    _escrever(pasta / 'observer.json', {'modo': 'ativo', 'autorizados': [str(repo)]})
    _escrever(pasta / 'career_state.json', estado_sintetico())

    monkeypatch.setenv('LUZIA_PRIVATE', str(pasta))
    for nome in MODULOS_COM_CAMINHOS:
        importlib.reload(importlib.import_module(f'luzia.{nome}'))
    fora = {n: c for n, c in caminhos_privados().items() if not Path(c).is_relative_to(pasta)}
    if fora:
        pytest.fail(f'caminhos privados fora da pasta do teste: {sorted(fora)}')

    from luzia import arquivos, modelo, pipeline
    # Nada versionado nem segredo entra no teste: sem foto do seminário, sem runs.jsonl real, sem .env.
    monkeypatch.setattr(arquivos, 'ESTADO_LEGADO', tmp_path / 'sem-foto.json')
    monkeypatch.setattr(pipeline, 'RUNS', tmp_path / 'runs.jsonl')
    monkeypatch.setattr(modelo, 'ENVS', [])
    return pasta
