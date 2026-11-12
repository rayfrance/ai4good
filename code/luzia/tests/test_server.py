"""Testes da Tarefa 13 — API do painel (`code/luzia/server.py`)."""

from __future__ import annotations

import http.client
import json
import threading
from types import SimpleNamespace
from urllib.parse import quote

import pytest

from luzia import banco, entregas, jogo, leituras, pipeline, planner, server, trajetoria

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

    def bruto(method: str, path: str, corpo: bytes = b'', headers: dict | None = None) -> tuple[int, dict]:
        """Requisição sem passar pelo json.dumps do teste: corpo e cabeçalhos exatamente como dados."""
        conn = http.client.HTTPConnection('127.0.0.1', port, timeout=5)
        hdrs = {'Host': f'127.0.0.1:{port}', 'Origin': f'http://127.0.0.1:{port}', **(headers or {})}
        conn.request(method, path, body=corpo, headers=hdrs)
        resp = conn.getresponse()
        data = json.loads(resp.read().decode('utf-8') or '{}')
        conn.close()
        return resp.status, data

    req.bruto = bruto
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
    recebidos = []

    def fake_run_plan(payload, schema=None, intro='', **kw):
        recebidos.append(payload)  # as chaves são as que o código de verdade monta (pedido.nivel_solicitado...)
        ped = payload.get('pedido') or {}
        nivel = ped.get('nivel_solicitado') if ped.get('nivel_solicitado') is not None else 1
        meta = ped.get('meta_solicitada') if ped.get('meta_solicitada') is not None else 3
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
    assert recebidos[-1]['pedido']['nivel_solicitado'] == 2 and recebidos[-1]['pedido']['meta_solicitada'] == 4
    assert r2['pedido']['proposta']['nivel_partida'] == 2
    assert r2['pedido']['proposta']['meta'] == 4
    assert 'Início no nível 2 até 4' in r2['pedido']['leitura']['texto']

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

    # `leituras.gerar` roda de verdade; só o modelo é falso
    def modelo_de_leituras(payload, **kw):
        itens = [{'alvo': a['alvo'], 'texto': f"Leitura de {a['id']}."} for a in payload['alvos']]
        res = planner.LLMResult(plan={'leituras': itens}, raw='{}', seconds=0.1, tokens_in=1, tokens_out=1, model='gemini/x')
        return res, {'quando': '2026-11-12T16:20:00', 'modelo': 'gemini/x'}

    monkeypatch.setattr(pipeline, 'run_plan', modelo_de_leituras)
    _, antes = api('GET', '/api/estado')
    esperadas = antes['leituras_vencidas']
    assert esperadas >= 3
    c_lt, r_lt = api('POST', '/api/leituras', {})
    assert c_lt == 200 and r_lt.get('geradas') == esperadas
    _, depois = api('GET', '/api/estado')
    assert depois['leituras_vencidas'] == 0
    leitura = next(p for p in depois['prismas'] if p['nome'] == DDD)['leitura']
    assert leitura['texto'] == f'Leitura de {DDD}.' and leitura['modelo'] == 'gemini/x' and leitura['vencida'] is False


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


def test_acender_avancos_para_entrega_api(api, monkeypatch):
    with trajetoria.abrir() as con:
        with banco.transacao(con):
            cur = con.execute("INSERT INTO entrega (chave, titulo, inicio, fim, fonte, commits, arquivos, linhas, areas_json) "
                              "VALUES ('pr:9', 'Ajusta agregado', '2026-11-10T10:00:00', '2026-11-11T16:00:00', 'merge-pr', "
                              "1, 2, 30, '[]')")
            eid = int(cur.lastrowid)
            con.execute('INSERT INTO entrega_prisma (entrega_id, prisma, termos_json) VALUES (?, ?, ?)',
                        (eid, DDD, json.dumps(['aggregate'])))
    monkeypatch.setattr(pipeline, 'run_plan', lambda *a, **k: (_ for _ in ()).throw(RuntimeError('sem internet')))
    c, r = api('POST', '/api/entrega/acender', {'id': eid})
    assert c == 400 and 'sem internet' in r['erro']
    acao = {'titulo': 'Explicar o agregado', 'tipo': 'explicar', 'skill': DDD, 'por_que': 'p', 'conceitos': ['c'],
            'como': ['1'], 'onde_explorar': 'o', 'prompt': 'x', 'duracao_min': 10}
    reg = {'quando': '2026-11-12T16:00:00', 'modelo': 'gemini/x'}
    monkeypatch.setattr(pipeline, 'run_plan', lambda *a, **k: (
        SimpleNamespace(plan={'acoes': [acao, {**acao, 'titulo': 'Defender a decisão'}]}, model='gemini/x'), reg))
    c, r = api('POST', '/api/entrega/acender', {'id': eid})
    assert c == 200 and len(r['avancos']) == 2
    _, det = api('GET', f'/api/entrega?id={eid}')
    assert sorted(a['dimensao'] for a in det['avancos_feitos']) == ['P3', 'P4']
    c, r = api('POST', '/api/entrega/acender', {'id': 'x'})
    assert c == 400


def test_leituras_automaticas_do_painel(api, monkeypatch):
    from luzia import modelo
    monkeypatch.setattr(modelo, 'pronto', lambda: True)
    _, st = api('GET', '/api/estado')
    assert st['modelo_pronto'] is True and st['leituras_vencidas'] == 3
    chamadas = []

    def fake(payload, **kw):
        chamadas.append(1)
        lt = [{'alvo': a['alvo'], 'texto': 'Leitura automática.'} for a in payload['alvos']]
        return SimpleNamespace(plan={'leituras': lt}, model='gemini/x'), {'quando': '2026-11-12T10:00:00', 'modelo': 'gemini/x'}

    monkeypatch.setattr(pipeline, 'run_plan', fake)
    c, r = api('POST', '/api/leituras', {'auto': True})
    assert c == 200 and r['geradas'] == 3 and len(chamadas) == 1
    with trajetoria.abrir() as con:  # a base muda: há leitura vencida de novo, mas o automático espera 10 min
        jogo.lancar(DDD, 20, 'propria', 'feixe', 'x')
    c, r = api('POST', '/api/leituras', {'auto': True})
    assert c == 200 and r['geradas'] == 0 and r.get('adiado') and len(chamadas) == 1
    c, r = api('POST', '/api/leituras', {})  # o botão da pessoa não espera
    assert c == 200 and r['geradas'] == 1 and len(chamadas) == 2
    monkeypatch.setattr(modelo, 'pronto', lambda: False)
    _, st = api('GET', '/api/estado')
    assert st['modelo_pronto'] is False


def test_reativar_pelo_painel_so_abre_o_pedido_e_o_prisma_segue_arquivado(api, monkeypatch):
    """O botão Reativar do painel só abre o pedido: o prisma volta apenas quando a pessoa aceita a proposta."""
    monkeypatch.setattr(pipeline, 'run_plan', lambda *a, **k: (_ for _ in ()).throw(RuntimeError('sem modelo')))
    c, r = api('POST', '/api/pedido', {'acao': 'abrir', 'tipo': 'arquivar', 'prisma': TESTES, 'motivo': 'teste'})
    assert c == 200
    assert api('POST', '/api/pedido', {'acao': 'aceitar', 'id': r['pedido']['id']})[0] == 200
    c, r = api('POST', '/api/pedido', {'acao': 'abrir', 'tipo': 'reativar', 'prisma': TESTES, 'motivo': 'Reativado pelo painel'})
    assert c == 200 and r['pedido']['estado'] == 'aberto'  # aguarda o sim da pessoa no card do pedido
    con = banco.conectar()
    try:
        assert con.execute('SELECT estado FROM prisma WHERE nome = ?', (TESTES,)).fetchone()['estado'] == 'arquivado'
    finally:
        con.close()
    assert api('POST', '/api/pedido', {'acao': 'aceitar', 'id': r['pedido']['id']})[0] == 200
    con = banco.conectar()
    try:
        assert con.execute('SELECT estado FROM prisma WHERE nome = ?', (TESTES,)).fetchone()['estado'] == 'ativo'
    finally:
        con.close()



# ------------------------------------------------------------------ caminhos de erro da API
def test_corpo_invalido_tipo_errado_e_rota_desconhecida(api):
    assert api.bruto('POST', '/api/modo', b'{nao e json', {'Content-Type': 'application/json'}) == (400, {'erro': 'json inválido'})
    c, r = api.bruto('POST', '/api/modo', b'{"modo": "passivo"}', {'Content-Type': 'text/plain'})
    assert c == 415 and 'application/json' in r['erro']
    assert api('POST', '/api/inexistente', {})[0] == 404
    grande = json.dumps({'modo': 'x' * 2_000_000}).encode('utf-8')
    assert api.bruto('POST', '/api/modo', grande, {'Content-Type': 'application/json'})[0] == 413


def test_validacoes_de_cada_acao_devolvem_400_ou_404_sem_gravar(api, privado):
    casos = [
        ('/api/modo', {'modo': 'inventado'}, 400, 'modo inválido'),
        ('/api/agente', {'agente': 'inventado'}, 400, 'agente inválido'),
        ('/api/nivel', {'prisma': DDD, 'nivel': 'alto'}, 400, 'nível inválido'),
        ('/api/nivel', {'prisma': 'Prisma que não existe', 'nivel': 2}, 400, 'prisma desconhecido'),
        ('/api/descartar', {'id': 'abcd', 'motivo': 'qualquer'}, 400, 'motivo inválido'),
        ('/api/enviar', {'id': 'zzzz'}, 404, 'não encontrado'),
        ('/api/iniciar', {'id': 'zzzz'}, 400, 'não pode ser iniciado'),
        ('/api/modelo', {'provedor': 'inventado', 'modelo': 'x'}, 400, 'provedor inválido'),
        ('/api/modelo', {'provedor': 'gemini', 'modelo': 'nome com espaço'}, 400, 'nome de modelo inválido'),
        ('/api/entrega/acender', {'id': 'abc'}, 400, 'id de entrega inválido'),
    ]
    for caminho, corpo, codigo, trecho in casos:
        c, r = api('POST', caminho, corpo)
        assert c == codigo and trecho in r.get('erro', ''), (caminho, corpo, c, r)
    cfg = json.loads((privado / 'observer.json').read_text(encoding='utf-8'))
    assert cfg['modo'] == 'ativo' and cfg.get('agente', 'claude-code') == 'claude-code'
    assert not (privado / 'modelo.json').exists()


def test_acender_sem_modelo_devolve_400_e_nao_grava_avancos(api, monkeypatch):
    monkeypatch.setattr(pipeline, 'run_plan', lambda *a, **k: (_ for _ in ()).throw(RuntimeError('sem modelo')))
    _, antes = api('GET', '/api/estado')
    c, r = api('POST', '/api/acender', {'prisma': DDD})
    assert c == 400 and r.get('erro')
    _, depois = api('GET', '/api/estado')
    assert len(depois['avancos']) == len(antes['avancos'])


def test_subir_sem_nivel_pronto_devolve_o_motivo(api):
    c, r = api('POST', '/api/subir', {'prisma': DDD})
    assert c == 400 and 'lm' in r['erro'] and 'feixe' not in r['erro'].lower()
