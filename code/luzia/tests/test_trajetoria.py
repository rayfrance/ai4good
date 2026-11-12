"""Prismas, perfil e versões da trajetória no banco (Tarefa 5)."""

import json

import pytest

from luzia import banco, jogo, pipeline, trajetoria

DDD = 'Domain-Driven Design (DDD)'
TESTES = 'Testes e Qualidade / SQL'
FRONT = 'Front-end (JS / Razor / React)'


@pytest.fixture
def con(privado):
    c = banco.conectar()
    yield c
    c.close()


def _lumen(con, prisma, lm, luz='propria'):
    with banco.transacao(con):
        con.execute("INSERT INTO lumen (quando, prisma, lm, luz, fonte, ref) VALUES ('2026-11-10T10:00:00', ?, ?, ?, 'feixe', 'x')",
                    (prisma, lm, luz))


def test_declarar_nivel_registra_origem(con):
    antes = {p['nome']: p for p in trajetoria.prismas(con)}
    assert antes[DDD]['nivel'] == 1
    trajetoria.declarar_nivel(con, DDD, 3)
    depois = {p['nome']: p for p in trajetoria.prismas(con)}
    assert depois[DDD]['nivel'] == 3
    ultimo = con.execute('SELECT * FROM nivel_registro WHERE prisma = ? ORDER BY quando, id DESC', (DDD,)).fetchall()
    ult = max(ultimo, key=lambda r: r['id'])
    assert (ult['origem'], ult['de'], ult['para']) == ('declarado', 1, 3)
    assert trajetoria.desde(con, DDD) == ult['quando']  # "lm desde o último nível" parte do último registro, qualquer origem
    assert jogo.niveis(pipeline.load_state()['plano'])[DDD]['nivel'] == 3
    with pytest.raises(ValueError):
        trajetoria.declarar_nivel(con, 'Inexistente', 2)


def test_arquivado_fora_da_trajetoria_mas_lumens_contam(con):
    _lumen(con, DDD, 60)
    _lumen(con, TESTES, 40, 'refletida')
    antes = trajetoria.resumo(con)
    # DDD: 1 → 4 (3 níveis), Testes: 2 → 4 (2), Front: 3 → 4 (1)
    assert antes['niveis_total'] == 6 and antes['lm_total'] == 100 and antes['luz_propria'] == 60
    with banco.transacao(con):
        con.execute("UPDATE prisma SET estado = 'arquivado' WHERE nome = ?", (DDD,))
    depois = trajetoria.resumo(con)
    assert depois['niveis_total'] == 3
    assert depois['lm_total'] == 100 and depois['luz_propria'] == 60  # lúmens do arquivado continuam
    assert DDD not in [p['nome'] for p in trajetoria.prismas(con)]
    assert DDD in [p['nome'] for p in trajetoria.prismas(con, incluir_arquivados=True)]
    assert DDD not in jogo.niveis(pipeline.load_state()['plano'])
    with banco.transacao(con):  # reativar devolve tudo
        con.execute("UPDATE prisma SET estado = 'ativo' WHERE nome = ?", (DDD,))
    assert trajetoria.resumo(con) == antes


def test_nova_versao_guarda_foto(con):
    n1 = trajetoria.versoes(con)[-1]['numero']  # a migração já gravou a nº 1 (triagem)
    trajetoria.declarar_nivel(con, DDD, 2)
    with banco.transacao(con):
        con.execute("UPDATE prisma SET estado = 'arquivado' WHERE nome = ?", (TESTES,))
    n2 = trajetoria.nova_versao(con, 'pedido', None)
    assert n2 == n1 + 1
    foto = trajetoria.versoes(con)[-1]
    assert foto['origem'] == 'pedido' and foto['numero'] == n2
    nomes = {p['nome']: p for p in foto['prismas']}
    assert set(nomes) == {DDD, FRONT} and nomes[DDD]['nivel'] == 2 and nomes[DDD]['meta'] == 4
    assert trajetoria.versoes(con)[0]['numero'] == n1  # as antigas ficam como estavam
    assert len(trajetoria.versoes(con)[0]['prismas']) == 3


def test_rota_compat(privado):
    plan = pipeline.load_state()['plano']
    r = jogo.rota(plan)
    for chave in ('degraus_total', 'degraus_feitos', 'niveis_total', 'niveis_feitos', 'marcos', 'skills', 'lm_total',
                  'luz_propria', 'pct'):
        assert chave in r
    assert r['degraus_total'] == r['niveis_total'] == 6 and r['degraus_feitos'] == r['niveis_feitos'] == 0
    s = r['skills'][0]
    for chave in ('nome', 'nivel', 'meta', 'proximo', 'na_meta', 'lm', 'propria', 'refletida', 'luz_propria', 'limiar',
                  'feixes', 'falta', 'pronto'):
        assert chave in s
    assert jogo.garantir_base(plan)['base'][DDD] == 1
    assert pipeline.rotulos(pipeline.load_state()) == ('Júnior 3', 'Plena')


def test_estado_vive_no_perfil(privado):
    estado = pipeline.load_state()
    assert estado['plano']['skills'][0]['nome'] == DDD
    pipeline.update_state({'trechos': ['a']}, {'quando': '2026-11-12T09:00:00'})
    assert pipeline.load_state()['plano']['trechos'] == ['a']
    with trajetoria.abrir() as con:
        assert trajetoria.perfil_ler(con, 'plano')['trechos'] == ['a']


def test_log_run_grava_chamada_modelo(privado):
    pipeline.log_run({'quando': '2026-11-12T09:00:00', 'rotulo': 'demo', 'modelo': 'm', 'tempo_modelo_s': 1.5,
                      'tokens_entrada': 10, 'tokens_saida': 5})
    with trajetoria.abrir() as con:
        r = con.execute('SELECT * FROM chamada_modelo').fetchone()
    assert (r['rotulo'], r['modelo'], r['segundos'], r['tokens_in'], r['tokens_out']) == ('demo', 'm', 1.5, 10, 5)
    assert json.loads(r['registro_json'])['rotulo'] == 'demo'
    assert pipeline.RUNS.exists()
