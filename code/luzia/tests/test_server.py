"""Testes da Tarefa 13 — API do painel (`code/luzia/server.py`)."""

from __future__ import annotations

import http.client
import json
import threading
from types import SimpleNamespace
from urllib.parse import quote

import pytest

from luzia import banco, entregas, jogo, leituras, pipeline, server, trajetoria

DDD = 'Domain-Driven Design (DDD)'
TESTES = 'Testes e Qualidade / SQL'


@pytest.fixture
def api(privado, monkeypatch):
    plan = pipeline.load_state()['plano']
    jogo.sincronizar(plan)
    monkeypatch.setattr(entregas, 'atualizar', lambda con, dias=90: {'novas': 0, 'atualizadas': 0})

    httpd = server.ThreadingHTTPServer(('127.0.0.1', 0), server.Handler)
    port = httpd.server_address[1]
    hosts = {f'localhost:{port}', f'127.0.0.1:{port}'}
    origens = {f'http://{h}' for h in hosts}
    monkeypatch.setattr(server, 'HOSTS_OK', hosts)
    monkeypatch.setattr(server, 'ORIGENS_OK', origens)

    t = threading.Thread(target=httpd.serve_forever, daemon=True)
    t.start()

    def req(method: str, path: str, body: dict | None = None, headers: dict | None = None) -> tuple[int, dict]:
        conn = http.client.HTTPConnection('127.0.0.1', port, timeout=5)
        hdrs = {'Host': f'127.0.0.1:{port}'}
        if method == 'POST':
            hdrs['Content-Type'] = 'application/json'
            hdrs['Origin'] = f'http://127.0.0.1:{port}'
        if headers:
            hdrs.update(headers)
        raw = json.dumps(body).encode('utf-8') if body is not None else None
        conn.request(method, path, body=raw, headers=hdrs)
        resp = conn.getresponse()
        data = json.loads(resp.read().decode('utf-8') or '{}')
        conn.close()
        return resp.status, data

    yield req
    httpd.shutdown()
    httpd.server_close()


def test_estado_forma_completa(api):
    code, st = api('GET', '/api/estado')
    assert code == 200
    for chave in (
        'perfil', 'trajetoria', 'rota', 'prismas', 'skills',
        'avancos', 'acoes', 'entregas', 'lumens', 'pedidos',
        'regras', 'modelo', 'modo', 'modo_nome',
    ):
        assert chave in st, f'Chave ausente em /api/estado: {chave}'

    assert st['modo_nome'] == 'em foco, com lampejos'
    assert st['trajetoria']['versao_atual'] >= 1
    assert isinstance(st['trajetoria']['versoes'], list)
    assert len(st['prismas']) >= 2
    p0 = st['prismas'][0]
    assert 'espectro' in p0 and len(p0['espectro']) == 5
    assert 'leitura' in p0


def test_avancos_filtros_get(api):
    q = f'/api/avancos?estado=sugerido&prisma={quote(DDD)}&tipo=praticar'
    code, data = api('GET', q)
    assert code == 200
    lista = data['avancos']
    assert len(lista) == 1
    assert lista[0]['titulo'] == 'Modelar um agregado de exemplo'
    assert 'link' in lista[0]


def test_entrega_detalhe_e_ampliar(api):
    with trajetoria.abrir() as con:
        with banco.transacao(con):
            cur = con.execute(
                "INSERT INTO entrega (chave, titulo, inicio, fim, fonte, commits, arquivos, linhas, areas_json) "
                "VALUES ('pr:7', 'Refatora serviço de domínio', '2026-11-10T10:00:00', '2026-11-11T16:00:00', "
                "'merge-pr', 3, 5, 110, '[\"Back-end C# / .NET\"]')"
            )
            eid = int(cur.lastrowid)
            con.execute(
                'INSERT INTO entrega_prisma (entrega_id, prisma, termos_json) VALUES (?, ?, ?)',
                (eid, DDD, json.dumps(['aggregate', 'domain'])),
            )

    code_st, st_ent = api('GET', '/api/estado')
    assert code_st == 200
    assert any(e['id'] == eid for e in st_ent['entregas'])

    code, det = api('GET', f'/api/entrega?id={eid}')
    assert code == 200
    for k in ('fatos', 'prismas', 'avancos_feitos', 'avancos_uteis', 'lumens_ligados', 'propriedade', 'leitura'):
        assert k in det

    code404, _ = api('GET', '/api/entrega?id=99999')
    assert code404 == 404

    code_amp, res_amp = api('POST', '/api/entregas/ampliar', {'dias': 180})
    assert code_amp == 200
    assert res_amp.get('ok') is True


def test_pedido_fluxo_api(api, monkeypatch):
    def fake_run_plan(payload, schema=None, intro='', **kw):
        nivel = payload.get('nivel_sugerido_pela_pessoa') or 1
        meta = payload.get('meta_sugerida_pela_pessoa') or 3
        res = {
            'nivel_partida': nivel,
            'meta': meta,
            'palavras_chave': ['mensageria', 'fila', 'evento'],
            'analise': f'Início no nível {nivel} até {meta}.',
            'acoes': [
                {
                    'titulo': 'Desenhar consumidor idempotente',
                    'tipo': 'praticar',
                    'skill': 'Mensageria',
                    'dimensao': None,
                    'por_que': 'Evitar duplicidade em eventos.',
                    'conceitos': ['idempotência'],
                    'como': ['Definir chave.', 'Testar repetição.'],
                    'onde_explorar': 'Fila de pedidos.',
                    'prompt': 'Me guie em idempotência.',
                    'duracao_min': 20,
                }
            ],
        }
        reg = {
            'quando': '2026-11-12T16:00:00',
            'tempo_total_s': 0.4,
            'pico_memoria_mib': 10.0,
            'tokens_entrada': 40,
            'tokens_saida': 30,
            'versao': 'test',
            'modelo': 'gemini-2.5-flash',
        }
        return SimpleNamespace(plan=res), reg

    monkeypatch.setattr(pipeline, 'run_plan', fake_run_plan)

    c1, r1 = api('POST', '/api/pedido', {'acao': 'abrir', 'tipo': 'incluir', 'prisma': 'Mensageria', 'motivo': 'Filas novas'})
    assert c1 == 200
    pid = r1['pedido']['id']
    assert r1['pedido']['estado'] == 'proposto'

    c2, r2 = api('POST', '/api/pedido', {'acao': 'ajustar', 'id': pid, 'nivel': 2, 'meta': 4})
    assert c2 == 200
    assert r2['pedido']['proposta']['nivel_partida'] == 2
    assert r2['pedido']['proposta']['meta'] == 4

    c3, r3 = api('POST', '/api/pedido', {'acao': 'aceitar', 'id': pid})
    assert c3 == 200
    assert r3['pedido']['estado'] == 'aceito'

    _, st = api('GET', '/api/estado')
    nomes_prismas = [p['nome'] for p in st['prismas']]
    assert 'Mensageria' in nomes_prismas


def test_nivel_acender_leituras_api(api, monkeypatch):
    c_nv, r_nv = api('POST', '/api/nivel', {'prisma': DDD, 'nivel': 2})
    assert c_nv == 200 and r_nv.get('ok') is True

    fake_trecho = {
        'acoes': [
            {
                'titulo': f'Avanço API {i}',
                'tipo': 'praticar',
                'skill': DDD,
                'por_que': 'p',
                'conceitos': ['c'],
                'como': ['1', '2'],
                'onde_explorar': 'o',
                'prompt': 'x',
                'duracao_min': 15,
            }
            for i in range(3)
        ]
    }
    reg = {
        'quando': '2026-11-12T16:10:00',
        'tempo_total_s': 0.5,
        'pico_memoria_mib': 10.0,
        'tokens_entrada': 20,
        'tokens_saida': 20,
        'versao': 't',
        'modelo': 'gemini-2.5-flash',
    }
    monkeypatch.setattr(pipeline, 'run_plan', lambda payload, **kw: (SimpleNamespace(plan=fake_trecho), reg))

    c_ac, r_ac = api('POST', '/api/acender', {'prisma': DDD})
    assert c_ac == 200 and len(r_ac.get('avancos', [])) == 3

    monkeypatch.setattr(leituras, 'gerar', lambda con, alvos=None: 2)
    c_lt, r_lt = api('POST', '/api/leituras', {})
    assert c_lt == 200 and r_lt.get('geradas') == 2


def test_seguranca_origem_e_host_403(api):
    c_orig, _ = api('POST', '/api/modo', {'modo': 'passivo'}, headers={'Origin': 'http://evil.example'})
    assert c_orig == 403

    c_host, _ = api('GET', '/api/estado', headers={'Host': 'evil.example'})
    assert c_host == 403


def _modelo_pedido_falso(monkeypatch):
    def fake(payload, **kw):
        ped = payload.get('pedido') or {}
        res = {'nivel_partida': ped.get('nivel_solicitado') or 1, 'meta': ped.get('meta_solicitada') or 3,
               'palavras_chave': ['fila'], 'acoes': [], 'analise': 'Análise de teste.'}
        return SimpleNamespace(plan=res, model='gemini/x'), {'quando': '2026-11-12T16:00:00', 'modelo': 'gemini/x'}

    monkeypatch.setattr(pipeline, 'run_plan', fake)


def test_pedido_erros_api_devolvem_400_json(api, monkeypatch):
    _modelo_pedido_falso(monkeypatch)
    c, r = api('POST', '/api/pedido', {'acao': 'abrir', 'tipo': 'incluir', 'prisma': 'Mensageria'})
    assert c == 200
    pid = r['pedido']['id']
    casos = [
        ({'acao': 'abrir', 'tipo': 'incluir', 'prisma': 'Mensageria'}, 'já existe um pedido em aberto'),
        ({'acao': 'abrir', 'tipo': 'inventado', 'prisma': 'Outro'}, 'tipo de pedido inválido'),
        ({'acao': 'aceitar', 'id': 'abc'}, 'número do pedido'),
        ({'acao': 'ajustar', 'id': 999}, 'pedido desconhecido'),
        ({'acao': 'ajustar', 'id': pid, 'nivel': 'x'}, 'nível'),
    ]
    for corpo, esperado in casos:
        c, r = api('POST', '/api/pedido', corpo)
        assert c == 400 and esperado in r.get('erro', ''), (corpo, c, r)
    assert api('POST', '/api/pedido', {'acao': 'aceitar', 'id': pid})[0] == 200
    for corpo in ({'acao': 'aceitar', 'id': pid}, {'acao': 'recusar', 'id': pid}):
        c, r = api('POST', '/api/pedido', corpo)
        assert c == 400 and 'já foi aceito' in r['erro'], (corpo, r)


def test_pedido_api_sem_modelo_propoe_e_aceita(api, monkeypatch):
    monkeypatch.setattr(pipeline, 'run_plan', lambda *a, **k: (_ for _ in ()).throw(RuntimeError('sem internet')))
    c, r = api('POST', '/api/pedido', {'acao': 'abrir', 'tipo': 'incluir', 'prisma': 'Mensageria', 'nivel': 1, 'meta': 3})
    assert c == 200 and r['pedido']['estado'] == 'proposto'
    assert r['pedido']['leitura'] is None and 'leitura indisponível' in r['pedido']['proposta']['leitura_indisponivel']
    c, r = api('POST', '/api/pedido', {'acao': 'aceitar', 'id': r['pedido']['id']})
    assert c == 200 and r['pedido']['estado'] == 'aceito'


def test_estado_sem_entrega_git_nao_usa_tarefas_da_ia(api):
    code, st = api('GET', '/api/estado')
    assert code == 200 and st['entregas'] == []
    diag = st['entregas_diagnostico']
    assert diag['repo_configurado'] is True and diag['identidades'] == ['Pessoa Teste']
    c, r = api('POST', '/api/identidade', {'identidade': 'outra@exemplo.test'})
    assert c == 200 and r['identidades'] == ['Pessoa Teste', 'o***@***']
    c, r = api('POST', '/api/identidade', {'identidade': ''})
    assert c == 400 and r['erro']
