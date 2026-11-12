"""Testes da Tarefa 12 — CLI, comandos, foco e vocabulário novo."""

from __future__ import annotations

import io
import json
import re
import sys
from contextlib import redirect_stdout
from pathlib import Path
from types import SimpleNamespace

import pytest

from luzia import acoes, banco, cli, entregas, jogo, observer, pedidos, pipeline, statusline, trajetoria

DDD = 'Domain-Driven Design (DDD)'
TESTES = 'Testes e Qualidade / SQL'

RE_TERMOS_ANTIGOS = re.compile(
    r'\b(feixes?|degraus?|trechos?(?!\s+d[eo]\s+c[óo]digo)|rota|cart[aã]o|cart[oõ]es)\b',
    re.IGNORECASE,
)


def rodar(monkeypatch, *argv: str) -> str:
    monkeypatch.setattr(sys, 'argv', ['luzia', *[str(a) for a in argv]])
    buf = io.StringIO()
    with redirect_stdout(buf):
        cli.main()
    return buf.getvalue()


def visivel(saida: str) -> str:
    return '\n'.join(l for l in saida.splitlines() if not l.startswith('LUZIA_'))


def botoes_de(saida: str) -> list[dict]:
    linha = next((x for x in saida.splitlines() if x.startswith('LUZIA_BOTOES=')), None)
    return json.loads(linha.split('=', 1)[1]) if linha else []


def tem_rodape_botoes(saida: str) -> bool:
    linhas = [l for l in saida.splitlines() if l.strip()]
    return (
        any(l.startswith('LUZIA_CLI=') for l in linhas)
        and any(l.startswith('LUZIA_PERGUNTA=') for l in linhas)
        and any(l.startswith('LUZIA_BOTOES=') for l in linhas)
        and len(botoes_de(saida)) >= 1
    )


def _semear_entrega(con) -> int:
    with banco.transacao(con):
        cur = con.execute(
            "INSERT INTO entrega (chave, titulo, inicio, fim, fonte, commits, arquivos, linhas, areas_json) "
            "VALUES ('pr:1', 'Separa agregado de agendamento', '2026-11-10T10:00:00', '2026-11-11T15:00:00', "
            "'merge-pr', 2, 4, 90, '[\"Back-end C# / .NET\"]')"
        )
        eid = int(cur.lastrowid)
        con.execute(
            'INSERT INTO entrega_prisma (entrega_id, prisma, termos_json) VALUES (?, ?, ?)',
            (eid, DDD, json.dumps(['aggregate', 'domain'])),
        )
    return eid


def test_toda_saida_termina_em_botoes(privado, monkeypatch):
    plan = pipeline.load_state()['plano']
    cat = jogo.sincronizar(plan)
    sugeridos = [k for k, f in cat.items() if f['estado'] == 'sugerido']
    f1, f2 = sugeridos[0], sugeridos[1]

    with trajetoria.abrir() as con:
        eid = _semear_entrega(con)
    monkeypatch.setattr(entregas, 'atualizar', lambda con, dias=90: {'novas': 0, 'atualizadas': 0})

    comandos = [
        ('hoje',),
        ('trajetoria',),
        ('rota',),
        ('next-level',),
        ('avancos',),
        ('acoes',),
        ('fila',),
        ('fazer', f1),
        ('registrar', f1, '--nota', '3', '--resumo', 'Explicou invariantes do agregado'),
        ('descartar', f2, '--motivo', 'agora_nao'),
        ('restaurar', f2),
        ('enviar', f2),
        ('guardar', DDD, '--pergunta', 'Como separar domínio e infraestrutura?'),
        ('cartao', DDD, '--acao', 'guardar'),
        ('subir', DDD),
        ('nivel', DDD, '2'),
        ('entregas',),
        ('entrega', str(eid)),
        ('dossie',),
        ('modo',),
        ('modo', 'passivo'),
        ('modelo',),
    ]
    for argv in comandos:
        s = rodar(monkeypatch, *argv)
        assert tem_rodape_botoes(s), f'Comando {argv} não terminou com botões válidos:\n{s}'


def test_avancos_filtros(privado, monkeypatch):
    plan = pipeline.load_state()['plano']
    jogo.sincronizar(plan)

    s_ddd = rodar(monkeypatch, 'avancos', '--estado', 'sugerido', '--prisma', DDD)
    v_ddd = visivel(s_ddd)
    assert 'Modelar um agregado de exemplo' in v_ddd
    assert 'Escrever um teste de unidade guiado' not in v_ddd
    assert tem_rodape_botoes(s_ddd)

    s_testes = rodar(monkeypatch, 'avancos', '--prisma', TESTES, '--tipo', 'praticar')
    v_testes = visivel(s_testes)
    assert 'Escrever um teste de unidade guiado' in v_testes
    assert 'Modelar um agregado de exemplo' not in v_testes


def test_pedido_fluxo_completo_pelo_chat(privado, monkeypatch):
    def fake_run_plan(payload, schema=None, intro='', **kw):
        nivel = payload.get('nivel_sugerido_pela_pessoa') or 1
        meta = payload.get('meta_sugerida_pela_pessoa') or 3
        res = {
            'nivel_partida': nivel,
            'meta': meta,
            'palavras_chave': ['opentelemetry', 'tracing', 'metrics'],
            'analise': f'Partida no nível {nivel} rumo à meta {meta} com foco em telemetria.',
            'acoes': [
                {
                    'titulo': 'Instrumentar endpoint crítico com tracing',
                    'tipo': 'praticar',
                    'skill': 'Observabilidade',
                    'dimensao': None,
                    'por_que': 'Dar visibilidade à latência real.',
                    'conceitos': ['tracing', 'span'],
                    'como': ['Escolher endpoint.', 'Adicionar span e medir.'],
                    'onde_explorar': 'Camada de entrada HTTP.',
                    'prompt': 'Me guie na instrumentação de um endpoint com tracing.',
                    'duracao_min': 20,
                }
            ],
        }
        reg = {
            'quando': '2026-11-12T15:00:00',
            'tempo_total_s': 0.5,
            'pico_memoria_mib': 10.0,
            'tokens_entrada': 50,
            'tokens_saida': 40,
            'versao': 'test',
            'modelo': 'gemini-2.5-flash',
        }
        return SimpleNamespace(plan=res), reg

    monkeypatch.setattr(pipeline, 'run_plan', fake_run_plan)

    s_abrir = rodar(monkeypatch, 'pedido', 'abrir', 'incluir', 'Observabilidade', '--motivo', 'Monitorar serviços')
    assert tem_rodape_botoes(s_abrir)
    botoes = botoes_de(s_abrir)
    rotulos = [b['rotulo'].lower() for b in botoes]
    assert any('aceitar' in r for r in rotulos)
    assert any('ajustar' in r for r in rotulos)
    assert any('recusar' in r for r in rotulos)

    with trajetoria.abrir() as con:
        lista = pedidos.listar(con)
        assert len(lista) == 1
        pid = lista[0]['id']

    s_ajustar = rodar(monkeypatch, 'pedido', 'ajustar', str(pid), '--nivel', '2', '--meta', '4')
    assert tem_rodape_botoes(s_ajustar)
    assert '2' in visivel(s_ajustar) and '4' in visivel(s_ajustar)

    s_aceitar = rodar(monkeypatch, 'pedido', 'aceitar', str(pid))
    assert tem_rodape_botoes(s_aceitar)
    assert 'Observabilidade' in visivel(s_aceitar)

    s_traj = rodar(monkeypatch, 'trajetoria')
    v_traj = visivel(s_traj)
    assert 'Observabilidade' in v_traj
    assert '▰' in v_traj


def test_vocabulario_sem_termos_antigos(privado, monkeypatch):
    plan = pipeline.load_state()['plano']
    cat = jogo.sincronizar(plan)
    f1 = next(k for k, f in cat.items() if f['estado'] == 'sugerido')

    with trajetoria.abrir() as con:
        eid = _semear_entrega(con)
    monkeypatch.setattr(entregas, 'atualizar', lambda con, dias=90: {'novas': 0, 'atualizadas': 0})

    saidas = [
        rodar(monkeypatch, 'hoje'),
        rodar(monkeypatch, 'trajetoria'),
        rodar(monkeypatch, 'avancos'),
        rodar(monkeypatch, 'fila'),
        rodar(monkeypatch, 'fazer', f1),
        rodar(monkeypatch, 'registrar', f1, '--nota', '3', '--resumo', 'Explicou bem'),
        rodar(monkeypatch, 'subir', DDD),
        rodar(monkeypatch, 'nivel', DDD, '2'),
        rodar(monkeypatch, 'entregas'),
        rodar(monkeypatch, 'entrega', str(eid)),
        rodar(monkeypatch, 'dossie'),
        rodar(monkeypatch, 'modo'),
    ]
    for s in saidas:
        texto = visivel(s)
        achado = RE_TERMOS_ANTIGOS.search(texto)
        assert achado is None, f'Termo antigo "{achado.group(0)}" encontrado na saída visível:\n{texto}'

    v_traj = visivel(rodar(monkeypatch, 'trajetoria'))
    assert 'prisma (skill)' in v_traj.lower()
    assert '▰' in v_traj or '▱' in v_traj

    v_modo = visivel(rodar(monkeypatch, 'modo'))
    assert 'em foco, com lampejos' in v_modo.lower()

    # Verifica também o lampejo do observador e a linha de status
    cartao = observer.cartao_refletida(DDD, 'Como isolar o domínio?')
    assert '✦ Lampejo da Luzia · Prisma Domain-Driven Design (DDD)' in cartao
    assert RE_TERMOS_ANTIGOS.search(cartao) is None

    linha_st = statusline.linha({'workspace': {'current_dir': str(privado)}})
    assert RE_TERMOS_ANTIGOS.search(linha_st) is None


def test_dossie_formal(privado, monkeypatch):
    plan = pipeline.load_state()['plano']
    cat = jogo.sincronizar(plan)
    f1 = next(k for k, f in cat.items() if f['estado'] == 'sugerido' and f.get('skill_plano') == DDD)

    # Declara nível em TESTES (não deve entrar em "Níveis conquistados")
    rodar(monkeypatch, 'nivel', TESTES, '3')

    # Conquista nível em DDD
    rodar(monkeypatch, 'fazer', f1)
    rodar(monkeypatch, 'registrar', f1, '--nota', '4', '--resumo', 'Modelou agregado com invariantes claras')
    jogo.lancar(DDD, 160, 'propria', 'feixe', 'extra')
    rodar(monkeypatch, 'subir', DDD)

    # Pedido de mudança aceito (arquivar e reativar sem modelo)
    with trajetoria.abrir() as con:
        p = pedidos.abrir(con, 'arquivar', TESTES, 'Pausa temporária')
        pedidos.aceitar(con, p['id'])

    s = rodar(monkeypatch, 'dossie')
    assert tem_rodape_botoes(s)
    m = re.search(r'(C:[^\n]+dossie-[^\n]+\.md|/[^\n]+dossie-[^\n]+\.md)', visivel(s))
    assert m, f'Caminho do dossiê não encontrado em:\n{s}'
    conteudo = Path(m.group(1).strip()).read_text(encoding='utf-8')

    assert '## Níveis conquistados' in conteudo
    assert '## Ações concluídas' in conteudo
    assert '## Pedidos de mudança aceitos' in conteudo
    assert 'pontos de evidência' in conteudo
    assert 'autoria própria' in conteudo
    # O nível declarado não entra na seção de níveis conquistados
    secao_conq = conteudo.split('## Níveis conquistados')[1].split('## Ações concluídas')[0]
    assert DDD in secao_conq
    assert TESTES not in secao_conq
    assert 'Pausa temporária' in conteudo
