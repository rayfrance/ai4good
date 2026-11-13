"""Leituras da Luzia com base, modelo e data (Tarefa 10): geração em lote, invalidação por hash e falha limpa."""

import json
from datetime import datetime, timedelta

import pytest

from luzia import banco, entregas, jogo, pipeline, planner, trajetoria

DDD = 'Domain-Driven Design (DDD)'
TESTES = 'Testes e Qualidade / SQL'
FRONT = 'Front-end (JS / Razor / React)'


@pytest.fixture
def con(privado):
    (privado / 'termos.txt').write_text('# sintético\nProdutoZeta\nClienteAlfa\n', encoding='utf-8')
    c = banco.conectar()
    yield c
    c.close()


def _criar_entrega(con) -> int:
    agora = datetime.now().replace(microsecond=0).isoformat(timespec='seconds')
    with banco.transacao(con):
        cur = con.execute(
            "INSERT INTO entrega (chave, titulo, inicio, fim, commits, arquivos, linhas, areas_json, ids_privados_json, fonte) "
            "VALUES ('pr-1', 'Ajusta agregado', ?, ?, 2, 4, 90, '[\"C#/.NET\"]', '[\"42\"]', 'merge-pr')",
            (agora, agora),
        )
        eid = cur.lastrowid
        con.execute(
            "INSERT INTO commit_ (hash, entrega_id, data, mensagem, arquivos, linhas, areas_json) "
            "VALUES ('abcdef123456', ?, ?, 'feat: cria Aggregate', 4, 90, '[\"C#/.NET\"]')",
            (eid, agora),
        )
        con.execute(
            "INSERT INTO entrega_prisma (entrega_id, prisma, termos_json) VALUES (?, ?, '[\"Aggregate\"]')",
            (eid, DDD),
        )
    return eid


def _simular_modelo(monkeypatch, chamadas: list):
    def falso_run_plan(payload, prep_seconds=0.0, label='demo', hits=None, save_current_state=False, schema=None, intro=None):
        chamadas.append({'payload': payload, 'schema': schema, 'label': label})
        alvos = payload.get('alvos', [])
        leituras_out = [
            {'alvo': a['alvo'], 'texto': f"Leitura sintetizada sobre {a['id']} com base em {len(a['fatos'])} grupos de fatos."}
            for a in alvos
        ]
        res = planner.LLMResult(
            plan={'leituras': leituras_out},
            raw=json.dumps({'leituras': leituras_out}, ensure_ascii=False),
            seconds=0.4,
            tokens_in=200,
            tokens_out=80,
            model='gemini/gemini-3.5-flash-lite',
        )
        rec = {'quando': datetime.now().isoformat(timespec='seconds'), 'modelo': res.model}
        return res, rec

    monkeypatch.setattr(pipeline, 'run_plan', falso_run_plan)


def test_lote_uma_chamada(con, monkeypatch):
    from luzia import leituras

    eid = _criar_entrega(con)
    chamadas = []
    _simular_modelo(monkeypatch, chamadas)

    venc = leituras.vencidas(con)
    assert ('prisma', DDD) in venc
    assert ('prisma', TESTES) in venc
    assert ('prisma', FRONT) in venc
    assert ('entrega', str(eid)) in venc

    n = leituras.gerar(con)
    assert n == len(venc) == 4
    assert len(chamadas) == 1  # todas geradas numa única chamada em lote

    l_ddd = leituras.obter(con, 'prisma', DDD)
    assert l_ddd is not None
    assert l_ddd['modelo'] == 'gemini/gemini-3.5-flash-lite'
    assert l_ddd['criado_em']
    assert l_ddd['base']['nivel'] == 1 and l_ddd['base']['meta'] == 4
    assert l_ddd['vencida'] is False

    det = entregas.detalhe(con, eid)
    assert det['leitura'] is not None
    assert det['leitura']['texto'] == leituras.obter(con, 'entrega', str(eid))['texto']


def test_nao_regenera_sem_mudar_base(con, monkeypatch):
    from luzia import leituras

    _criar_entrega(con)
    chamadas = []
    _simular_modelo(monkeypatch, chamadas)

    assert leituras.gerar(con) == 4
    assert len(chamadas) == 1
    assert leituras.vencidas(con) == []
    assert leituras.gerar(con) == 0
    assert len(chamadas) == 1  # nenhuma chamada nova se o hash da base não mudou


def test_regenera_quando_nivel_sobe(con, monkeypatch):
    from luzia import leituras

    chamadas = []
    _simular_modelo(monkeypatch, chamadas)
    assert leituras.gerar(con) == 3
    assert leituras.obter(con, 'prisma', DDD)['vencida'] is False

    trajetoria.declarar_nivel(con, DDD, 2)
    assert leituras.obter(con, 'prisma', DDD)['vencida'] is True
    assert leituras.vencidas(con) == [('prisma', DDD)]

    assert leituras.gerar(con) == 1
    assert len(chamadas) == 2
    assert leituras.obter(con, 'prisma', DDD)['vencida'] is False
    assert leituras.obter(con, 'prisma', DDD)['base']['nivel'] == 2


def test_falha_no_meio_nao_grava_nada(con, monkeypatch):
    from luzia import leituras

    # 1. Exceção na chamada ao modelo → nada gravado
    def quebrar(*a, **k):
        raise RuntimeError('modelo fora do ar')

    monkeypatch.setattr(pipeline, 'run_plan', quebrar)
    assert leituras.gerar(con) == 0
    assert con.execute('SELECT COUNT(*) FROM leitura').fetchone()[0] == 0

    # 2. Resposta parcial (só 1 de 3 alvos devolvido) → nada gravado
    def parcial(payload, *a, **k):
        primeiro = payload['alvos'][0]['alvo']
        res = planner.LLMResult(
            plan={'leituras': [{'alvo': primeiro, 'texto': 'Só uma leitura veio.'}]},
            raw='{}', seconds=0.1, tokens_in=10, tokens_out=5, model='gemini/gemini-3.5-flash-lite',
        )
        return res, {'quando': '2026-11-12T10:00:00', 'modelo': res.model}

    monkeypatch.setattr(pipeline, 'run_plan', parcial)
    assert leituras.gerar(con) == 0
    assert con.execute('SELECT COUNT(*) FROM leitura').fetchone()[0] == 0


def test_sem_modelo_devolve_none(con):
    from luzia import leituras

    # Na fixture `privado`, modelo.ENVS está vazio e não há chave configurada → chamar o modelo falha sem quebrar
    eid = _criar_entrega(con)
    assert leituras.gerar(con) == 0
    assert leituras.obter(con, 'prisma', DDD) is None
    det = entregas.detalhe(con, eid)
    assert det['leitura'] is None
    assert det['fatos']['commits'] == 2


def test_base_mostra_os_dados_reais_para_a_dona(con, privado):
    """A base aparece na tela de quem entrou: fica real. O que vai ao modelo é testado em test_mascarar_modelo.py."""
    from luzia import leituras

    plano = trajetoria.perfil_ler(con, 'plano')
    plano['skills'][0]['evidencia'] = 'Trabalhou no ProdutoZeta para ClienteAlfa no PR #42 (AB#99).'
    plano['diagnostico_fontes'] = {'conflito_curriculo_vs_realidade': 'No ProdutoZeta faz integração com ClienteAlfa.'}
    with banco.transacao(con):
        trajetoria.perfil_gravar(con, 'plano', plano)
    eid = _criar_entrega(con)

    b_prisma = json.dumps(leituras.base(con, 'prisma', DDD), ensure_ascii=False)
    b_entrega = json.dumps(leituras.base(con, 'entrega', str(eid)), ensure_ascii=False)
    for real in ('ProdutoZeta', 'ClienteAlfa', '#42', 'AB#99'):
        assert real in b_prisma
    assert 'abcdef123456' not in b_prisma and 'abcdef123456' not in b_entrega  # hash de commit nunca na base


def _muitas_entregas(con, n):
    agora = datetime.now().replace(microsecond=0).isoformat(timespec='seconds')
    with banco.transacao(con):
        for i in range(n):
            cur = con.execute(
                "INSERT INTO entrega (chave, titulo, inicio, fim, commits, arquivos, linhas, areas_json, ids_privados_json, fonte) "
                "VALUES (?, ?, ?, ?, 1, 1, 10, '[]', '[]', 'commit')", (f'cm-{i}', f'Entrega {i}', agora, agora))
            con.execute("INSERT INTO entrega_prisma (entrega_id, prisma, termos_json) VALUES (?, ?, '[]')", (cur.lastrowid, DDD))


def test_lotes_de_no_maximo_8_alvos_por_chamada(con, monkeypatch):
    from luzia import leituras

    _muitas_entregas(con, 17)  # 17 entregas + 3 prismas = 20 alvos
    chamadas = []
    _simular_modelo(monkeypatch, chamadas)
    assert leituras.gerar(con) == 20
    assert [len(c['payload']['alvos']) for c in chamadas] == [8, 8, 4]
    assert leituras.vencidas(con) == []


def test_lote_incompleto_nao_grava_nada_dele_mas_os_outros_lotes_sim(con, monkeypatch):
    from luzia import leituras

    _muitas_entregas(con, 17)
    chamadas = []
    _simular_modelo(monkeypatch, chamadas)
    simulado = pipeline.run_plan

    def segundo_lote_incompleto(payload, **kw):
        res, rec = simulado(payload, **kw)
        if len(chamadas) == 2:  # o modelo esquece um alvo do segundo lote
            res.plan['leituras'] = res.plan['leituras'][:-1]
        return res, rec

    monkeypatch.setattr(pipeline, 'run_plan', segundo_lote_incompleto)
    assert leituras.gerar(con) == 12  # lotes 1 (8) e 3 (4) entram; o 2º não grava leitura nenhuma
    assert len(leituras.vencidas(con)) == 8
