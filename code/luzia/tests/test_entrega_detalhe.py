"""Detalhe da entrega ligada ao jogo (Tarefa 9): fatos, P1–P4, avanços feitos/úteis e lúmens ligados."""

import json
from datetime import datetime, timedelta

import pytest

from luzia import acoes, banco, entregas, jogo, pipeline, propriedade

DDD = 'Domain-Driven Design (DDD)'
TESTES = 'Testes e Qualidade / SQL'
FRONT = 'Front-end (JS / Razor / React)'


@pytest.fixture
def con(privado):
    c = banco.conectar()
    yield c
    c.close()


def _data(dias: int, hora: int = 12) -> str:
    d = (datetime.now() - timedelta(days=dias)).replace(hour=hora, minute=0, second=0, microsecond=0)
    return d.isoformat(timespec='seconds')


def _criar_entrega(con, chave='pr-abc', titulo='Ajusta agregado de pedido', inicio=None, fim=None,
                   commits_dados=None, prismas_termos=None) -> int:
    inicio = inicio or _data(10)
    fim = fim or _data(8)
    commits_dados = commits_dados or [
        ('h1', inicio, 'feat: cria Aggregate de pedido', 4, 80, ['C#/.NET', 'SQL']),
        ('h2', fim, 'refactor: extrai ValueObject', 5, 130, ['C#/.NET', 'JavaScript']),
    ]
    prismas_termos = prismas_termos if prismas_termos is not None else {DDD: ['Aggregate', 'ValueObject']}
    with banco.transacao(con):
        cur = con.execute(
            'INSERT INTO entrega (chave, titulo, inicio, fim, commits, arquivos, linhas, areas_json, ids_privados_json, fonte) '
            'VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
            (chave, titulo, inicio, fim, len(commits_dados),
             sum(c[3] for c in commits_dados), sum(c[4] for c in commits_dados),
             json.dumps(['C#/.NET', 'SQL', 'JavaScript'], ensure_ascii=False),
             json.dumps(['42']), 'merge-pr'),
        )
        eid = cur.lastrowid
        for h, dt, msg, arqs, lns, areas in commits_dados:
            con.execute(
                'INSERT INTO commit_ (hash, entrega_id, data, mensagem, arquivos, linhas, areas_json) '
                'VALUES (?, ?, ?, ?, ?, ?, ?)',
                (h, eid, dt, msg, arqs, lns, json.dumps(areas, ensure_ascii=False)),
            )
        for nome, termos in prismas_termos.items():
            con.execute(
                'INSERT INTO entrega_prisma (entrega_id, prisma, termos_json) VALUES (?, ?, ?)',
                (eid, nome, json.dumps(termos, ensure_ascii=False)),
            )
    return eid


def test_p2_sobre_entrega(con):
    assert propriedade.p2_entrega([]) is None
    commits = [
        {'arquivos': 4, 'linhas': 80, 'areas': ['C#/.NET', 'SQL']},
        {'arquivos': 5, 'linhas': 130, 'areas': ['C#/.NET', 'JavaScript']},
    ]
    p2 = propriedade.p2_entrega(commits)
    # 9 arquivos → pen_arq = (9-5)*4 = 16; 210 linhas → pen_lin = ((210-150)//50)*5 = 5; 3 áreas → pen_area = (3-2)*10 = 10
    assert p2 == {
        'nota': 69,
        'tipo': 'calculado',
        'base': '100 − 16 (9 arquivos) − 5 (210 linhas) − 10 (3 áreas) = 69',
    }

    eid = _criar_entrega(con)
    # Registra um avanço concluído para esta entrega acendendo P3 com nota 4 (100)
    with banco.transacao(con):
        con.execute(
            "INSERT INTO avanco (id, prisma, tipo, titulo, conteudo_json, duracao_min, valor_lm, origem, entrega_id, "
            "dimensao, estado, nota, lm_ganho, criado_em) VALUES (?, ?, 'explicar', 'Explicar invariantes do agregado', "
            "?, 15, 45, 'entrega', ?, 'P3', 'conquistado', 4, 45, ?)",
            ('av-e1', DDD, json.dumps({'resumo': 'Explicou invariantes e fronteira transacional'}), eid, _data(7)),
        )
    det = entregas.detalhe(con, eid)
    assert det['fatos']['commits'] == 2
    assert det['fatos']['arquivos'] == 9
    assert det['fatos']['linhas'] == 210
    assert det['fatos']['duracao_dias'] == 2
    dims = det['propriedade']['dimensoes']
    assert dims['P1']['nota'] == 65  # da fixture privado
    assert dims['P2'] == p2
    assert dims['P3']['nota'] == 100 and 'invariantes' in dims['P3']['base']
    assert dims['P4'] is None
    assert det['propriedade']['indice'] == round((65 + 69 + 100) / 3)
    assert det['propriedade']['base'] == '3 de 4 dimensões'


def test_lumens_ligados_janela_e_prisma(con):
    eid = _criar_entrega(con, inicio=_data(10, 14), fim=_data(8, 16))
    with banco.transacao(con):
        con.execute(
            "INSERT INTO avanco (id, prisma, tipo, titulo, estado, entrega_id, valor_lm, lm_ganho, criado_em) "
            "VALUES ('av-da-entrega', ?, 'explicar', 'Avanço da entrega', 'conquistado', ?, 40, 40, ?)",
            (DDD, eid, _data(2)),
        )
        # 1. Lúmen do avanço da própria entrega (mesmo fora da janela de datas, entra por ref)
        con.execute(
            "INSERT INTO lumen (quando, prisma, lm, luz, fonte, ref) VALUES (?, ?, 40, 'propria', 'feixe', 'av-da-entrega')",
            (_data(2), DDD),
        )
        # 2. Lúmen com ref direto da entrega
        con.execute(
            "INSERT INTO lumen (quando, prisma, lm, luz, fonte, ref) VALUES (?, ?, 25, 'propria', 'feixe', ?)",
            (_data(3), DDD, str(eid)),
        )
        # 3. Passivos e conversão do mesmo prisma (DDD) dentro da janela [inicio - 1 dia, fim + 1 dia] = [_data(11), _data(7)]
        con.execute(
            "INSERT INTO lumen (quando, prisma, lm, luz, fonte, ref) VALUES (?, ?, 10, 'refletida', 'passivo-refletida', 's1')",
            (_data(11, 9), DDD),
        )
        con.execute(
            "INSERT INTO lumen (quando, prisma, lm, luz, fonte, ref) VALUES (?, ?, 20, 'propria', 'passivo-prompt', 's2')",
            (_data(9, 15), DDD),
        )
        con.execute(
            "INSERT INTO lumen (quando, prisma, lm, luz, fonte, ref) VALUES (?, ?, 30, 'propria', 'passivo-conversao', 's3')",
            (_data(7, 20), DDD),
        )
        # 4. Fora da janela (inicio - 2 dias e fim + 2 dias): NÃO entram
        con.execute(
            "INSERT INTO lumen (quando, prisma, lm, luz, fonte, ref) VALUES (?, ?, 10, 'refletida', 'passivo-refletida', 's0')",
            (_data(12, 10), DDD),
        )
        con.execute(
            "INSERT INTO lumen (quando, prisma, lm, luz, fonte, ref) VALUES (?, ?, 20, 'propria', 'passivo-prompt', 's4')",
            (_data(6, 10), DDD),
        )
        # 5. Outro prisma (TESTES) dentro da janela: NÃO entra
        con.execute(
            "INSERT INTO lumen (quando, prisma, lm, luz, fonte, ref) VALUES (?, ?, 20, 'propria', 'passivo-prompt', 's5')",
            (_data(9, 12), TESTES),
        )
        # 6. Avanço de outra coisa dentro da janela: NÃO entra
        con.execute(
            "INSERT INTO lumen (quando, prisma, lm, luz, fonte, ref) VALUES (?, ?, 50, 'propria', 'feixe', 'av-outro')",
            (_data(9, 12), DDD),
        )

    det = entregas.detalhe(con, eid)
    ligados = det['lumens_ligados']
    assert sorted(l['lm'] for l in ligados) == [10, 20, 25, 30, 40]
    assert all(l['prisma'] == DDD for l in ligados)


def test_avancos_uteis_mesmos_prismas(con, privado):
    plan = pipeline.load_state()['plano']
    jogo.sincronizar(plan)
    eid = _criar_entrega(con, prismas_termos={DDD: ['Aggregate']})

    with banco.transacao(con):
        # Avanço feito para a própria entrega: vai em avancos_feitos, não repete em avancos_uteis
        con.execute(
            "INSERT INTO avanco (id, prisma, tipo, titulo, estado, entrega_id, valor_lm, criado_em) "
            "VALUES ('feito-1', ?, 'explicar', 'Feito para a entrega', 'em_andamento', ?, 60, ?)",
            (DDD, eid, _data(5)),
        )
        # 4 avanços abertos do mesmo prisma (DDD) + 1 conquistado + 1 descartado + 1 de outro prisma
        for i, (est, val) in enumerate([('em_andamento', 50), ('na_fila', 80), ('sugerido', 75), ('sugerido', 30)], 1):
            con.execute(
                "INSERT INTO avanco (id, prisma, tipo, titulo, estado, valor_lm, criado_em) "
                "VALUES (?, ?, 'praticar', ?, ?, ?, ?)",
                (f'util-{i}', DDD, f'Útil {i}', est, val, _data(4)),
            )
        con.execute(
            "INSERT INTO avanco (id, prisma, tipo, titulo, estado, valor_lm, criado_em) "
            "VALUES ('conq-ddd', ?, 'estudar', 'Já conquistado', 'conquistado', 90, ?)",
            (DDD, _data(4)),
        )
        con.execute(
            "INSERT INTO avanco (id, prisma, tipo, titulo, estado, valor_lm, criado_em) "
            "VALUES ('desc-ddd', ?, 'estudar', 'Descartado', 'descartado', 95, ?)",
            (DDD, _data(4)),
        )
        con.execute(
            "INSERT INTO avanco (id, prisma, tipo, titulo, estado, valor_lm, criado_em) "
            "VALUES ('util-front', ?, 'praticar', 'Outro prisma', 'em_andamento', 99, ?)",
            (FRONT, _data(4)),
        )

    det = entregas.detalhe(con, eid)
    assert [a['id'] for a in det['avancos_feitos']] == ['feito-1']
    uteis = det['avancos_uteis']
    assert len(uteis) == 3
    assert [a['id'] for a in uteis] == ['util-1', 'util-2', 'util-3']
    assert all((a.get('skill_plano') or a.get('prisma')) == DDD for a in uteis)
    assert all(a['estado'] in ('em_andamento', 'na_fila', 'sugerido') for a in uteis)

    lista = entregas.listar(con)
    assert len(lista) == 1 and lista[0]['id'] == eid
    texto_dump = json.dumps(det, ensure_ascii=False)
    assert 'h1' not in texto_dump  # hash de commit nunca sai do banco
    assert det['ids'] == ['42'] and lista[0]['ids'] == ['42']  # o número do PR/ticket fica visível para a dona
