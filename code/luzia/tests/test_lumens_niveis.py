"""Lúmens, níveis, lampejos e dossiê sobre o banco; o hook grava com espera curta e nunca trava a sessão."""

import json
import re
import threading
import time
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from luzia import acoes, banco, jogo, observer, pipeline, trajetoria

DDD = 'Domain-Driven Design (DDD)'
TESTES = 'Testes e Qualidade / SQL'
CODE = Path(__file__).resolve().parents[2]


@pytest.fixture
def plan(privado):
    return pipeline.load_state()['plano']


def _sql(sql, *args):
    con = banco.conectar()
    try:
        with banco.transacao(con):
            con.execute(sql, args)
    finally:
        con.close()


def _consulta(sql, *args):
    con = banco.conectar()
    try:
        return con.execute(sql, args).fetchall()
    finally:
        con.close()


def _agora(dias=0, horas=0):
    return (datetime.now() - timedelta(days=dias, hours=horas)).isoformat(timespec='seconds')


def _evento(privado, tool='Write', conteudo='class Pedido : Aggregate { }', sessao='s-teste'):
    cfg = json.loads((privado / 'observer.json').read_text(encoding='utf-8'))
    return {'session_id': sessao, 'tool_name': tool, 'cwd': cfg['autorizados'][0],
            'tool_input': {'file_path': 'Pedido.cs', 'content': conteudo}}, cfg


# ------------------------------------------------------------------ níveis
def test_subir_registra_conquistado(plan):
    jogo.lancar(DDD, 160, 'propria', 'feixe', 'teste')
    antes = jogo.niveis(plan)[DDD]['nivel']
    r = jogo.subir(DDD, plan)
    assert r['para'] == antes + 1
    regs = _consulta("SELECT * FROM nivel_registro WHERE prisma = ? AND origem = 'conquistado'", DDD)
    assert len(regs) == 1 and regs[0]['para'] == antes + 1 and regs[0]['lm'] == 160
    assert jogo.niveis(plan)[DDD]['nivel'] == antes + 1
    assert jogo.progresso_skill(DDD)['lm'] == 0  # recomeça do zero


def test_progresso_conta_desde_o_ultimo_registro_de_qualquer_origem(plan):
    _sql("INSERT INTO lumen (quando, prisma, lm, luz, fonte, ref) VALUES (?, ?, 100, 'propria', 'feixe', 'a')",
         '2026-11-01T10:00:00', DDD)
    _sql("INSERT INTO nivel_registro (prisma, de, para, quando, origem) VALUES (?, 1, 2, ?, 'declarado')",
         DDD, '2026-11-02T10:00:00')
    _sql("INSERT INTO lumen (quando, prisma, lm, luz, fonte, ref) VALUES (?, ?, 50, 'refletida', 'passivo-refletida', '')",
         '2026-11-03T10:00:00', DDD)
    p = jogo.progresso_skill(DDD)
    assert (p['lm'], p['propria'], p['refletida'], p['feixes']) == (50, 0, 50, 0)


def test_subir_exige_tudo_do_nivel(plan):
    jogo.lancar(DDD, 160, 'refletida', 'passivo-refletida', 'x')
    r = jogo.subir(DDD, plan)
    assert 'erro' in r and 'luz própria' in r['erro'] and '1 centelha acesa' in r['erro']
    assert _consulta("SELECT 1 FROM nivel_registro WHERE origem = 'conquistado'") == []


# ------------------------------------------------------------------ dossiê
def _secao(texto, titulo):
    m = re.search(rf'## {re.escape(titulo)}\n(.*?)(?=\n## |\n_Gerado|\Z)', texto, re.S)
    assert m, f'seção {titulo!r} ausente'
    return m.group(1)


def test_declarado_nao_e_evidencia_no_dossie(plan):
    con = banco.conectar()
    trajetoria.declarar_nivel(con, DDD, 3)
    con.close()
    texto = jogo.dossie(plan, 'teste').read_text(encoding='utf-8')
    assert '- nenhum' in _secao(texto, 'Níveis conquistados')
    _sql("INSERT INTO lumen (quando, prisma, lm, luz, fonte, ref) VALUES (?, ?, 160, 'propria', 'feixe', 'teste')",
         _agora(horas=-1), DDD)  # depois do registro declarado (os lúmens contam a partir dele)
    assert 'erro' not in jogo.subir(DDD, plan)
    texto = jogo.dossie(plan, 'teste').read_text(encoding='utf-8')
    conquistados = _secao(texto, 'Níveis conquistados')
    assert DDD in conquistados and 'nível 4' in conquistados and 'nenhum' not in conquistados


def test_dossie_em_linguagem_formal(plan):
    texto = jogo.dossie(plan, 'teste').read_text(encoding='utf-8').lower()
    for proibida in ('feixe', 'degrau', 'prisma', 'lúmen', 'lampejo'):
        assert proibida not in texto
    assert 'skill' in texto and 'nível' in texto and 'ações' in texto
    assert not re.search(r'\blm\b', texto)


def test_dossie_lista_pedidos_aceitos(plan):
    _sql("INSERT INTO pedido (tipo, prisma, motivo, estado, criado_em, decidido_em) "
         "VALUES ('mudar_meta', ?, 'quero focar em domínio', 'aceito', '2026-11-05T09:00:00', '2026-11-06T09:00:00')", DDD)
    _sql("INSERT INTO pedido (tipo, prisma, motivo, estado, criado_em) "
         "VALUES ('arquivar', ?, 'motivo recusado', 'recusado', '2026-11-05T09:00:00')", TESTES)
    texto = jogo.dossie(plan, 'teste').read_text(encoding='utf-8')
    pedidos = _secao(texto, 'Pedidos de mudança aceitos')
    assert 'quero focar em domínio' in pedidos and '2026-11-06' in pedidos
    assert 'motivo recusado' not in texto


# ------------------------------------------------------------------ passivos
def test_teto_passivo_por_dia(plan):
    assert [jogo.passivo(DDD, 'prompt', 's') for _ in range(3)] == [20, 20, 0]
    assert jogo.passivo(DDD, 'refletida', 's') == 0
    assert jogo.passivo(TESTES, 'refletida', 's') == 10  # o teto é por prisma
    assert jogo.passivo(TESTES, 'prompt', 's') == 20
    assert jogo.passivo(TESTES, 'refletida', 's') == 10
    assert jogo.passivo(TESTES, 'prompt', 's') == 0  # 40 lm: nada além


def test_teto_corta_o_ultimo_passivo(plan):
    for _ in range(3):
        jogo.passivo(DDD, 'refletida', 's')
    assert jogo.passivo(DDD, 'prompt', 's') == 10  # 30 já ganhos: só cabem mais 10


def test_teto_nao_conta_o_dia_anterior_nem_conversao_ultrapassa(plan):
    _sql("INSERT INTO lumen (quando, prisma, lm, luz, fonte, ref) VALUES (?, ?, 40, 'propria', 'passivo-prompt', '')",
         _agora(dias=1), DDD)
    assert jogo.passivo(DDD, 'prompt', 's') == 20
    jogo.abrir_lampejo(DDD, 's')
    assert jogo.converter(DDD, 4)['lm'] == 30  # conversão não é barrada pelo teto


# ------------------------------------------------------------------ lampejos
def test_lampejo_uma_vez(plan):
    jogo.abrir_lampejo(DDD, 'abc')
    assert jogo.converter(DDD, 4)['lm'] == 30
    assert 'erro' in jogo.converter(DDD, 4)
    estados = [r['estado'] for r in _consulta('SELECT estado FROM lampejo')]
    assert estados == ['convertido']
    assert sum(r['lm'] for r in _consulta("SELECT lm FROM lumen WHERE fonte = 'passivo-conversao'")) == 30


def test_lampejo_vale_24_horas(plan):
    _sql("INSERT INTO lampejo (prisma, sessao, quando, estado) VALUES (?, 'x', ?, 'aberto')", DDD, _agora(horas=25))
    assert 'erro' in jogo.converter(DDD, 4)
    _sql("INSERT INTO lampejo (prisma, sessao, quando, estado) VALUES (?, 'x', ?, 'aberto')", DDD, _agora(horas=23))
    assert jogo.converter(DDD, 3)['lm'] == 22  # 30 × 75%, arredondado


def test_lampejo_guardado_nao_paga_e_nota_baixa_nao_paga(plan):
    jogo.abrir_lampejo(DDD, 'a')
    assert jogo.usar_lampejo(DDD, 'guardado') is True
    assert jogo.usar_lampejo(DDD, 'guardado') is False
    jogo.abrir_lampejo(DDD, 'b')
    assert jogo.converter(DDD, 1)['lm'] == 0
    assert [r['estado'] for r in _consulta('SELECT estado FROM lampejo ORDER BY id')] == ['guardado', 'guardado']


def test_conversao_e_lampejo_na_mesma_transacao(plan, monkeypatch):
    jogo.abrir_lampejo(DDD, 'a')
    monkeypatch.setattr(jogo, '_lumen', lambda *a, **k: (_ for _ in ()).throw(RuntimeError('falhou')))
    with pytest.raises(RuntimeError):
        jogo.converter(DDD, 4)
    assert [r['estado'] for r in _consulta('SELECT estado FROM lampejo')] == ['aberto']


# ------------------------------------------------------------------ conquistar numa transação só
def test_conquistar_lumen_e_estado_na_mesma_transacao(plan, monkeypatch):
    fid = next(f['id'] for f in jogo.catalogo(plan))
    jogo.iniciar(fid, 'teste')

    def quebrar(*a, **k):
        raise RuntimeError('falhou no meio')
    monkeypatch.setattr(jogo, '_evento', quebrar)
    with pytest.raises(RuntimeError):
        jogo.conquistar(fid, 4, 'ok', plan)
    assert _consulta('SELECT 1 FROM lumen') == []
    assert _consulta('SELECT estado, lm_ganho FROM avanco WHERE id = ?', fid)[0]['estado'] == 'em_andamento'


def test_conquistar_grava_lumen_no_banco(plan):
    fid = next(f['id'] for f in jogo.catalogo(plan))
    jogo.iniciar(fid, 'teste')
    r = jogo.conquistar(fid, 4, 'ok', plan)
    linhas = _consulta('SELECT * FROM lumen')
    assert len(linhas) == 1 and linhas[0]['ref'] == fid and linhas[0]['lm'] == r['ganho']
    assert (linhas[0]['luz'], linhas[0]['fonte']) == ('propria', 'feixe')


# ------------------------------------------------------------------ hook
def test_observer_grava_no_banco(privado, plan, capsys):
    evento, cfg = _evento(privado)
    observer.ao_usar_ferramenta(evento, cfg)
    assert 'luz refletida' in capsys.readouterr().out
    lumens = _consulta('SELECT * FROM lumen')
    assert [(r['prisma'], r['lm'], r['luz'], r['fonte']) for r in lumens] == [(DDD, 10, 'refletida', 'passivo-refletida')]
    ev = _consulta('SELECT * FROM sessao_evento')
    assert len(ev) == 1 and ev[0]['prisma'] == DDD and ev[0]['lm'] == 10 and ev[0]['ferramenta'] == 'Write'
    assert ev[0]['extensao'] == '.cs' and ev[0]['interveio'] == 1
    assert [r['estado'] for r in _consulta('SELECT estado FROM lampejo')] == ['aberto']
    assert not (privado / 'sessao.jsonl').exists() and not (privado / 'lumens.jsonl').exists()


def test_observer_prompt_grava_luz_propria(privado, plan, capsys):
    evento, cfg = _evento(privado)
    evento['prompt'] = 'modele um Aggregate para o pedido'
    observer.ao_enviar_prompt(evento, cfg)
    assert [(r['lm'], r['luz'], r['fonte']) for r in _consulta('SELECT * FROM lumen')] == [(20, 'propria', 'passivo-prompt')]
    assert _consulta('SELECT ferramenta FROM sessao_evento')[0]['ferramenta'] == 'prompt'


def test_observer_um_reconhecimento_por_prisma_por_sessao(privado, plan, capsys):
    evento, cfg = _evento(privado)
    observer.ao_usar_ferramenta(evento, cfg)
    observer.ao_usar_ferramenta(evento, cfg)
    assert len(_consulta('SELECT 1 FROM lumen')) == 1
    evento['session_id'] = 'outra'
    observer.ao_usar_ferramenta(evento, cfg)
    assert len(_consulta('SELECT 1 FROM lumen')) == 2


def _travar_banco(privado, segurar_s):
    """Outra conexão segura a trava de escrita; devolve o evento que a libera."""
    pronto, soltar = threading.Event(), threading.Event()

    def segurar():
        con = banco.conectar()
        con.execute('BEGIN IMMEDIATE')
        pronto.set()
        soltar.wait(segurar_s)
        con.rollback()
        con.close()
    t = threading.Thread(target=segurar)
    t.start()
    assert pronto.wait(10)
    return soltar, t


def test_hook_com_banco_travado_pendura_sem_esperar_mais_que_o_teto(privado, plan, capsys):
    evento, cfg = _evento(privado)
    soltar, t = _travar_banco(privado, 30)
    try:
        inicio = time.monotonic()
        assert jogo.passivo(DDD, 'refletida', 's') == 10
        assert jogo.passivo(TESTES, 'refletida', 's') == 10
        jogo.abrir_lampejo(DDD, 's')
        assert time.monotonic() - inicio < 2 * (banco.ESPERA_CURTA_MS / 1000 + 1.5)
        inicio = time.monotonic()
        observer.ao_usar_ferramenta({**evento, 'session_id': 'nova'}, cfg)  # nunca levanta
        assert time.monotonic() - inicio < 3 * (banco.ESPERA_CURTA_MS / 1000 + 1.5)
    finally:
        soltar.set()
        t.join()
    assert (privado / 'pendentes.jsonl').exists() or list(privado.glob('pendentes-*'))
    _sql('SELECT 1')  # a próxima transação absorve o que ficou pendente
    assert len(_consulta('SELECT 1 FROM lumen')) >= 2
    assert len(_consulta('SELECT 1 FROM lampejo')) >= 1


def test_hook_nunca_levanta_com_banco_quebrado(privado, plan, monkeypatch, capsys):
    evento, cfg = _evento(privado)

    def quebrar(*a, **k):
        raise OSError('disco')
    monkeypatch.setattr(banco, 'conectar', quebrar)
    observer.ao_usar_ferramenta(evento, cfg)
    observer.ao_enviar_prompt({**evento, 'prompt': 'Aggregate'}, cfg)
    observer.ao_iniciar_sessao(evento, cfg)


# ------------------------------------------------------------------ desempenho e JSON antigo
def test_rota_usa_uma_conexao_e_poucas_consultas(plan, monkeypatch):
    jogo.catalogo(plan)
    abertas, consultas = [], []
    original = banco.conectar

    def espiar(*a, **k):
        con = original(*a, **k)
        abertas.append(con)
        con.set_trace_callback(consultas.append)
        return con
    monkeypatch.setattr(banco, 'conectar', espiar)
    r = jogo.rota(plan)
    assert len(r['skills']) == 3
    assert len(abertas) == 1, 'rota deve abrir uma conexão só'
    assert len([c for c in consultas if 'FROM lumen' in c]) <= 2
    assert len(consultas) <= 15, consultas


def test_sem_json_antigo():
    antigos = ('feixes.json', 'lumens.jsonl', 'degraus.json', 'cartoes.json', 'fila.json')
    for arquivo in (CODE / 'luzia').glob('*.py'):
        if arquivo.name == 'migrar.py':
            continue
        texto = arquivo.read_text(encoding='utf-8')
        for nome in antigos:
            assert nome not in texto, f'{arquivo.name} ainda cita {nome}'


def test_banco_que_acabou_de_falhar_nao_faz_o_hook_esperar_de_novo(privado, plan):
    soltar, t = _travar_banco(privado, 30)
    try:
        assert banco.gravar_ou_pendurar('lumen', {'prisma': DDD, 'lm': 10, 'luz': 'refletida', 'fonte': 'x'}) is False
        assert banco.ocupado()
        inicio = time.monotonic()
        assert banco.gravar_ou_pendurar('sessao_evento', {'sessao': 's', 'prisma': DDD}) is False
        assert time.monotonic() - inicio < 0.5  # foi direto para os pendentes
    finally:
        soltar.set()
        t.join()
    _sql('SELECT 1')
    assert len(_consulta('SELECT 1 FROM lumen')) == 1 and len(_consulta('SELECT 1 FROM sessao_evento')) == 1


# ------------------------------------------------------------------ fix round 1
def test_dois_sim_ao_mesmo_tempo_sobem_um_nivel_so(plan, monkeypatch):
    jogo.lancar(DDD, 160, 'propria', 'feixe', 'teste')
    barreira = threading.Barrier(2, timeout=3)
    original = jogo.garantir_base

    def lento(*a, **k):
        d = original(*a, **k)  # os dois leem "pronto" antes de qualquer um gravar (se não houver trava)
        try:
            barreira.wait()
        except threading.BrokenBarrierError:
            pass
        return d
    monkeypatch.setattr(jogo, 'garantir_base', lento)
    res = []
    ts = [threading.Thread(target=lambda: res.append(jogo.subir(DDD, plan))) for _ in range(2)]
    for t in ts:
        t.start()
    for t in ts:
        t.join()
    assert len(_consulta("SELECT 1 FROM nivel_registro WHERE origem = 'conquistado'")) == 1
    assert sum('erro' not in r for r in res) == 1


def test_passivo_com_banco_travado_custa_uma_espera_curta(privado, plan):
    soltar, t = _travar_banco(privado, 30)
    try:
        inicio = time.monotonic()
        assert jogo.passivo(TESTES, 'prompt', 's') == 20
        assert time.monotonic() - inicio < banco.ESPERA_CURTA_MS / 1000 + 0.8
    finally:
        soltar.set()
        t.join()


def test_subir_duas_threads_registram_um_so_nivel(plan):
    jogo.lancar(DDD, 160, 'propria', 'feixe', 'teste')
    antes = jogo.niveis(plan)[DDD]['nivel']
    barreira = threading.Barrier(2)
    resultados = []

    def clicar():
        barreira.wait(10)
        resultados.append(jogo.subir(DDD, plan))
    ts = [threading.Thread(target=clicar) for _ in range(2)]
    for t in ts:
        t.start()
    for t in ts:
        t.join(60)
    regs = _consulta("SELECT de, para FROM nivel_registro WHERE prisma = ? AND origem = 'conquistado'", DDD)
    assert [(r['de'], r['para']) for r in regs] == [(antes, antes + 1)]
    assert sorted('erro' in r for r in resultados) == [False, True]
    assert jogo.niveis(plan)[DDD]['nivel'] == antes + 1
    assert 'já subiu' in next(r['erro'] for r in resultados if 'erro' in r)


def test_marco_do_dossie_na_mesma_transacao_da_subida(plan, monkeypatch):
    front = 'Front-end (JS / Razor / React)'
    jogo.lancar(front, 160, 'propria', 'feixe', 'a')
    assert 'erro' not in jogo.subir(front, plan)  # 1 de 6 níveis: ainda sem marco
    jogo.lancar(DDD, 160, 'propria', 'feixe', 'teste')
    antes = jogo.niveis(plan)[DDD]['nivel']

    def quebrar(*a, **k):
        raise RuntimeError('falhou')
    monkeypatch.setattr(trajetoria, 'perfil_gravar', quebrar)
    with pytest.raises(RuntimeError):
        jogo.subir(DDD, plan)
    assert _consulta("SELECT 1 FROM nivel_registro WHERE origem = 'conquistado' AND prisma = ?", DDD) == []
    assert jogo.niveis(plan)[DDD]['nivel'] == antes


def test_passivo_com_banco_ocupado_continua_respeitando_o_teto(privado, plan):
    soltar, t = _travar_banco(privado, 30)
    try:
        vistos = [jogo.passivo(DDD, 'prompt', 's') for _ in range(3)]  # a leitura não bloqueia no WAL
    finally:
        soltar.set()
        t.join()
    assert vistos == [20, 20, 0]
    _sql('SELECT 1')
    assert sum(r['lm'] for r in _consulta('SELECT lm FROM lumen')) == 40


def test_reconhecimento_uma_vez_por_sessao_no_banco_e_poda(privado, plan):
    _sql("INSERT INTO sessao_visto (sessao, chave, prisma, quando) VALUES ('velha', 'agente', ?, ?)", DDD, _agora(dias=8))
    assert jogo.reconhecer('abc', 'agente', DDD, 'refletida') == 10
    assert jogo.reconhecer('abc', 'agente', DDD, 'refletida') is None
    assert jogo.reconhecer('abc', 'prompt', DDD, 'prompt') == 20  # outra origem
    assert jogo.reconhecer('def', 'agente', DDD, 'refletida') == 10  # outra sessão
    assert _consulta("SELECT 1 FROM sessao_visto WHERE sessao = 'velha'") == []
    assert len(_consulta('SELECT 1 FROM sessao_evento')) == 3
    assert not (privado / 'sessao_vistos.json').exists()


def test_reconhecimento_com_banco_travado_nao_se_perde(privado, plan, capsys):
    evento, cfg = _evento(privado, sessao='trava')
    soltar, t = _travar_banco(privado, 30)
    try:
        inicio = time.monotonic()
        observer.ao_usar_ferramenta(evento, cfg)
        observer.ao_usar_ferramenta(evento, cfg)  # repetido na mesma sessão, ainda travado
        observer.ao_enviar_prompt({**evento, 'prompt': 'modele um Aggregate'}, cfg)
        assert time.monotonic() - inicio < banco.ESPERA_CURTA_MS / 1000 + 2
    finally:
        soltar.set()
        t.join()
    assert _consulta('SELECT 1 FROM lumen') == []  # ainda pendente
    _sql('SELECT 1')  # a próxima transação absorve
    lumens = [(r['lm'], r['fonte']) for r in _consulta('SELECT * FROM lumen WHERE prisma = ? ORDER BY id', DDD)]
    assert lumens == [(10, 'passivo-refletida'), (20, 'passivo-prompt')]
    ev = _consulta("SELECT ferramenta FROM sessao_evento WHERE sessao = ? AND prisma = ? ORDER BY id",
                   observer.sessao_id(evento), DDD)
    assert [r['ferramenta'] for r in ev] == ['Write', 'prompt']
    assert len(_consulta('SELECT 1 FROM lampejo')) == 1


def test_reconhecimento_pendurado_duas_vezes_vale_uma(privado, plan):
    dados = {'sessao': 's2', 'chave': 'agente', 'prisma': DDD, 'lm': 10, 'luz': 'refletida', 'fonte': 'passivo-refletida',
             'teto': 40, 'ferramenta': 'Write'}
    linha = json.dumps({'operacao': 'reconhecimento', 'dados': dados, 'quando': _agora()}) + '\n'
    (privado / 'pendentes.jsonl').write_text(linha * 2, encoding='utf-8')
    _sql('SELECT 1')
    assert len(_consulta('SELECT 1 FROM lumen')) == 1
    assert len(_consulta('SELECT 1 FROM sessao_evento')) == 1


def test_reconhecimento_pendurado_respeita_o_teto_na_absorcao(privado, plan):
    _sql("INSERT INTO lumen (quando, prisma, lm, luz, fonte, ref) VALUES (?, ?, 35, 'propria', 'passivo-prompt', '')",
         _agora(), DDD)
    dados = {'sessao': 's3', 'chave': 'agente', 'prisma': DDD, 'lm': 10, 'luz': 'refletida', 'fonte': 'passivo-refletida',
             'teto': 40}
    (privado / 'pendentes.jsonl').write_text(
        json.dumps({'operacao': 'reconhecimento', 'dados': dados, 'quando': _agora()}) + '\n', encoding='utf-8')
    _sql('SELECT 1')
    assert sum(r['lm'] for r in _consulta('SELECT lm FROM lumen WHERE prisma = ?', DDD)) == 40


def test_banco_antigo_sem_sessao_visto_ganha_a_tabela(privado, plan):
    _sql('DROP TABLE sessao_visto')
    assert jogo.reconhecer('x', 'agente', DDD, 'refletida') == 10


def test_dossie_pedido_sem_modelo_mostra_leitura_indisponivel(plan):
    _sql("INSERT INTO leitura (id, alvo_tipo, alvo_id, texto, base_json, base_hash, modelo, criado_em) "
         "VALUES (1, 'pedido', '1', 'texto sem modelo', '{}', 'h', '', '2026-11-05T09:00:00')")
    _sql("INSERT INTO pedido (tipo, prisma, motivo, leitura_id, estado, criado_em, decidido_em) "
         "VALUES ('arquivar', ?, 'motivo', 1, 'aceito', '2026-11-05T09:00:00', '2026-11-06T09:00:00')", DDD)
    pedidos = _secao(jogo.dossie(plan, 'teste').read_text(encoding='utf-8'), 'Pedidos de mudança aceitos')
    assert 'leitura indisponível' in pedidos and 'texto sem modelo' not in pedidos and 'None' not in pedidos
