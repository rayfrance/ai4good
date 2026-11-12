"""Avanços e a história deles no banco: filtros combináveis, eventos em cada mudança, fila e evidências P3/P4."""

import json

import pytest

from luzia import acoes, banco, jogo, pipeline

DDD = 'Domain-Driven Design (DDD)'
TESTES = 'Testes e Qualidade / SQL'


@pytest.fixture
def plan(privado):
    return pipeline.load_state()['plano']


@pytest.fixture
def ids(plan):
    cat = jogo.sincronizar(plan)
    return [k for k, f in cat.items() if f['estado'] == 'sugerido']


def _sql(sql, *args):
    con = banco.conectar()
    try:
        with banco.transacao(con):
            con.execute(sql, args)
    finally:
        con.close()


def _eventos(fid):
    con = banco.conectar()
    try:
        return [(r['evento'], r['nota']) for r in con.execute(
            'SELECT evento, nota FROM avanco_evento WHERE avanco_id = ? ORDER BY id', (fid,))]
    finally:
        con.close()


def _filtrar(**filtros):
    con = banco.conectar()
    try:
        return [f['id'] for f in jogo.avancos(con, **filtros)]
    finally:
        con.close()


def test_filtros_combinaveis(plan, ids):
    a, b, c = ids  # a: DDD, b: Testes, c: Front-end
    jogo.iniciar(a, 'teste')
    _sql("UPDATE avanco SET tipo = 'explicar' WHERE id = ?", b)
    assert set(_filtrar()) == {a, b, c}
    assert _filtrar(estado='em_andamento') == [a]
    assert set(_filtrar(estado='sugerido')) == {b, c}
    assert _filtrar(tipo='explicar') == [b]
    assert _filtrar(prisma=DDD) == [a]
    assert _filtrar(prisma=TESTES, tipo='explicar') == [b]
    assert _filtrar(estado='sugerido', prisma=DDD) == []
    assert _filtrar(estado='em_andamento', prisma=DDD, tipo='explicar') == []
    assert _filtrar(estado='em_andamento', prisma=DDD, tipo='praticar') == [a]


def test_avancos_na_ordem_do_catalogo(plan, ids):
    jogo.iniciar(ids[2], 'teste')
    ordem = _filtrar()
    assert ordem == [f['id'] for f in jogo.catalogo(plan)]
    assert ordem[0] == ids[2]


def test_evento_registrado_em_cada_mudanca(plan, ids):
    f = ids[0]
    jogo.enfileirar(f)
    jogo.iniciar(f, 'aqui')
    jogo.descartar(f, 'ja_domino')
    jogo.restaurar(f)
    nomes = ['enviado ao agente', 'iniciado', 'descartado', 'restaurado']
    assert [e for e, _ in _eventos(f)] == nomes
    hist = next(x for x in jogo.catalogo(plan, descartados=True) if x['id'] == f)['historico']
    assert [h['evento'] for h in hist] == nomes
    assert hist[1]['onde'] == 'aqui' and hist[2]['motivo'] == 'já domino'


def test_conquista_e_tente_de_novo_viram_eventos(plan, ids):
    f = ids[0]
    jogo.iniciar(f)
    jogo.conquistar(f, 1, 'ainda não', plan)
    jogo.conquistar(f, 3, 'agora sim', plan)
    assert _eventos(f) == [('iniciado', None), ('tente de novo', 1), ('conquistado', 3)]
    feixe = jogo.sincronizar(plan)[f]
    assert (feixe['estado'], feixe['tentativas'], feixe['nota'], feixe['resumo']) == ('conquistado', 1, 3, 'agora sim')


def test_motivo_do_descarte_aparece_na_lista(plan, ids):
    jogo.descartar(ids[0], 'agora_nao')
    assert [m['motivo'] for m in jogo.motivos_descartados()] == ['agora não']


def test_sincronizar_so_grava_quando_algo_mudou(plan, ids):
    espiao = banco.conectar()
    antes = espiao.execute('PRAGMA data_version').fetchone()[0]
    jogo.catalogo(plan)
    jogo.catalogo(plan)
    assert espiao.execute('PRAGMA data_version').fetchone()[0] == antes
    espiao.close()


def test_sincronizar_atualiza_valor_quando_a_lacuna_muda(plan, ids):
    antes = jogo.sincronizar(plan)[ids[0]]['valor_lm']
    _sql('UPDATE prisma SET meta = meta + 1 WHERE nome = ?', DDD)
    depois = jogo.sincronizar(plan)[ids[0]]
    assert depois['valor_lm'] > antes
    assert depois['conta'][1][2] == 15 * (int(depois['conta'][1][1].split('→')[1]) - int(depois['conta'][1][1].split('→')[0]))


def test_conquistado_nao_recalcula_valor(plan, ids):
    f = ids[0]
    jogo.iniciar(f)
    jogo.conquistar(f, 4, 't', plan)
    v = jogo.sincronizar(plan)[f]['valor_lm']
    _sql('UPDATE prisma SET meta = meta + 1 WHERE nome = ?', DDD)
    assert jogo.sincronizar(plan)[f]['valor_lm'] == v


def test_novo_avanco_do_plano_entra_sem_mexer_nos_outros(plan, ids):
    jogo.iniciar(ids[0])
    plan['plano'][0]['acoes'].append({**plan['plano'][0]['acoes'][0], 'titulo': 'Um feixe novo no plano'})
    cat = jogo.sincronizar(plan)
    assert len(cat) == 4
    assert cat[ids[0]]['estado'] == 'em_andamento'
    assert [f for f in cat.values() if f['titulo'] == 'Um feixe novo no plano'][0]['estado'] == 'sugerido'


def test_titulo_renomeado_nao_volta_ao_do_plano(plan, ids):
    f = ids[0]
    con = banco.conectar()
    with banco.transacao(con):
        c = json.loads(con.execute('SELECT conteudo_json FROM avanco WHERE id = ?', (f,)).fetchone()['conteudo_json'])
        c['renomeado'] = True
        con.execute("UPDATE avanco SET titulo = 'Meu nome', conteudo_json = ? WHERE id = ?", (json.dumps(c), f))
    con.close()
    assert jogo.sincronizar(plan)[f]['titulo'] == 'Meu nome'


# ------------------------------------------------------------------ fila, evidências e guardadas
def test_fila_vive_no_banco(privado):
    acoes.enfileirar('aaaa', 'Um')
    acoes.enfileirar('bbbb', 'Dois')
    acoes.enfileirar('aaaa', 'Um de novo')
    assert [f['id'] for f in acoes.fila()] == ['bbbb', 'aaaa']
    acoes.marcar_oferecida('aaaa', 's1')
    acoes.marcar_oferecida('aaaa', 's1')
    assert acoes.fila()[1]['oferecida_em'] == ['s1']
    acoes.desenfileirar('bbbb')
    assert [f['id'] for f in acoes.fila()] == ['aaaa']
    assert not (privado / 'fila.json').exists()


def test_evidencias_vem_so_dos_eventos_concluida(plan, ids):
    f = ids[0]
    acoes.registrar_evento(f, 'iniciada', skill=DDD, origem='painel')
    jogo.iniciar(f)
    jogo.conquistar(f, 3, 'ok', plan)  # histórico: 'conquistado' (não é evidência)
    acoes.registrar_evento(f, 'concluida', nota=3, resumo='ok', skill=DDD, entrega='feat: x', dimensao='p3', origem='rota')
    ev = acoes.evidencias()
    assert len(ev) == 1
    e = ev[0]
    assert (e['id'], e['nota'], e['resumo'], e['skill'], e['entrega'], e['dimensao']) == (f, 3, 'ok', DDD, 'feat: x', 'p3')
    assert e['quando']
    assert acoes.status_map()[f]['status'] == 'feita'


def test_registrar_evento_devolve_o_registro(privado):
    rec = acoes.registrar_evento('zzzz', 'iniciada', skill='X')
    assert rec['id'] == 'zzzz' and rec['evento'] == 'iniciada' and rec['skill'] == 'X' and rec['quando']
    assert not (privado / 'evidencias.jsonl').exists()


def test_guardar_cria_avanco_que_sobrevive_ao_plano(plan, ids):
    a = acoes.guardar(DDD, 'Por que o agregado protege a invariante?')
    assert acoes.guardar(DDD, 'Por que o agregado protege a invariante?')['id'] == a['id']
    achado = acoes.find(plan, a['id'])
    assert achado['origem'] == 'guardada' and achado['estado'] == 'sugerido' and achado['skill_plano'] == DDD
    assert achado['valor_lm'] >= 10
    assert len(acoes.todas(plan)) == 4
    con = banco.conectar()
    try:
        assert con.execute('SELECT origem FROM avanco WHERE id = ?', (a['id'],)).fetchone()['origem'] == 'lampejo'
    finally:
        con.close()


def test_evento_anterior_ao_catalogo_vira_em_andamento(plan):
    base = acoes.derivadas(plan)[0]['id']
    acoes.registrar_evento(base, 'iniciada', skill='x')
    assert jogo.sincronizar(plan)[base]['estado'] == 'em_andamento'


# ------------------------------------------------------------------ hook: fila no banco
def _prompt_com_conceito(plan, privado):
    from luzia import observer
    cfg = json.loads((privado / 'observer.json').read_text(encoding='utf-8'))
    _, info = next(iter(observer.lacunas(plan).items()))
    return {'session_id': 's-fila', 'prompt': ' '.join(info['palavras'][:3]), 'cwd': cfg['autorizados'][0]}, cfg


def test_fila_que_falha_nao_engole_a_luz_propria(plan, privado, monkeypatch, capsys):
    from luzia import observer
    evento, cfg = _prompt_com_conceito(plan, privado)

    def quebra(*a, **k):
        raise RuntimeError('banco travado')
    monkeypatch.setattr(acoes, 'fila', quebra)
    observer.ao_enviar_prompt(evento, cfg)
    saida = json.loads(capsys.readouterr().out)['hookSpecificOutput']['additionalContext']
    assert 'luz própria' in saida and 'Luzia · fila' not in saida
    assert 'RuntimeError' in (privado / 'erros.log').read_text(encoding='utf-8')


def test_trava_do_banco_nao_prende_o_hook(plan, privado, capsys):
    import time
    from luzia import observer
    evento, cfg = _prompt_com_conceito(plan, privado)
    acoes.enfileirar('ab12', 'Um feixe')
    segurando = banco.conectar()
    segurando.execute('BEGIN IMMEDIATE')  # outra escrita em andamento
    try:
        t0 = time.monotonic()
        observer.ao_enviar_prompt(evento, cfg)
        gasto = time.monotonic() - t0
    finally:
        segurando.rollback()
        segurando.close()
    assert gasto < 4  # a espera do hook é curta (1,5 s por escrita), não os 5 s do padrão
    assert 'Luzia · fila' in json.loads(capsys.readouterr().out)['hookSpecificOutput']['additionalContext']


def test_sync_nao_apaga_resumo_gravado_no_meio(plan, ids, monkeypatch):
    f = ids[0]
    _sql('UPDATE prisma SET meta = meta + 1 WHERE nome = ?', DDD)
    real = jogo._atualizar_conteudo

    def com_concorrente(con, feixe, antes):  # outra conexão grava o resumo entre a leitura e a escrita do sync
        con.execute("UPDATE avanco SET conteudo_json = json_set(conteudo_json, '$.resumo', 'gravado agora') WHERE id = ?", (f,))
        return real(con, feixe, antes)
    monkeypatch.setattr(jogo, '_atualizar_conteudo', com_concorrente)
    jogo.sincronizar(plan)
    monkeypatch.undo()
    assert jogo.sincronizar(plan)[f]['resumo'] == 'gravado agora'
