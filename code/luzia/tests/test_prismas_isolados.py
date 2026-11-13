"""Um prisma = uma habilidade (13/11/2026): divisão determinística dos nomes compostos e o pedido `dividir`."""

import json

import pytest

from luzia import prismas

DDD = 'Domain-Driven Design (DDD)'
TESTES = 'Testes e Qualidade / SQL'
FRONT = 'Front-end (JS / Razor / React)'


# ------------------------------------------------------------------ divisão dos nomes
@pytest.mark.parametrize('nome, esperado', [
    ('Testes e Qualidade / SQL', ['Testes e Qualidade', 'SQL']),
    ('Arquitetura .NET / Clean Architecture', ['Arquitetura .NET', 'Clean Architecture']),
    ('Front-end (JS / Razor / React)', ['JavaScript', 'Razor', 'React']),
    ('Back-end C# / .NET e Integrações', ['C# / .NET', 'Integrações']),
    ('Programação Agêntica e Fluxo com IA', ['Programação Agêntica']),
    ('Domain-Driven Design (DDD)', ['Domain-Driven Design (DDD)']),
])
def test_divisao_de_cada_nome_atual(nome, esperado):
    assert prismas.partes(nome) == esperado
    assert prismas.composto(nome) is (esperado != [nome])


@pytest.mark.parametrize('nome, esperado', [
    ('Kafka / RabbitMQ', ['Kafka', 'RabbitMQ']),
    ('Mensageria e Eventos Assíncronos', ['Mensageria', 'Eventos Assíncronos']),
    ('Cloud (AWS, Azure)', ['AWS', 'Azure']),
    ('Observabilidade', ['Observabilidade']),
    ('Testes e Qualidade', ['Testes e Qualidade']),
    ('C# / .NET', ['C# / .NET']),
    ('CI/CD', ['CI/CD']),
    ('Docker / Testes e Qualidade', ['Docker', 'Testes e Qualidade']),
])
def test_regra_generica_para_nomes_novos(nome, esperado):
    assert prismas.partes(nome) == esperado


def test_exigir_isolado_recusa_composto_e_sugere_as_partes():
    assert prismas.exigir_isolado('  SQL ') == 'SQL'
    with pytest.raises(ValueError) as e:
        prismas.exigir_isolado(TESTES)
    assert '"Testes e Qualidade"' in str(e.value) and '"SQL"' in str(e.value)


def test_classificar_avanco_pelas_palavras_da_parte():
    nomes = prismas.partes(TESTES)
    assert prismas.classificar({'titulo': 'Otimizar um JOIN com índice', 'conceitos': [TESTES]}, nomes) == 'SQL'
    assert prismas.classificar({'titulo': 'Escrever um teste de unidade guiado', 'conceitos': [TESTES]}, nomes) == \
        'Testes e Qualidade'
    # nenhum acerto: fica com a primeira parte (a pessoa confere antes de aceitar)
    assert prismas.classificar({'titulo': 'Revisar algo', 'conceitos': []}, nomes) == 'Testes e Qualidade'
    front = prismas.partes(FRONT)
    assert prismas.classificar({'titulo': 'Extrair um componente de tela', 'conceitos': [FRONT]}, front) == 'React'


def test_repartir_palavras_do_antigo_entre_as_partes():
    por = prismas.repartir_palavras(['xunit', 'Assert', 'JOIN', 'palavra-solta'], ['Testes e Qualidade', 'SQL'])
    assert 'xunit' in por['Testes e Qualidade'] and 'Assert' in por['Testes e Qualidade']
    assert 'JOIN' in por['SQL'] and 'JOIN' not in por['Testes e Qualidade']
    assert 'palavra-solta' in por['Testes e Qualidade']  # sem casa: primeira parte, nada se perde
    assert 'SELECT' in por['SQL']  # padrão da parte


def test_triagem_divide_skill_composta_que_o_modelo_devolver():
    plano = {'skills': [{'nome': TESTES, 'luzia_sugere': 2, 'alvo': 4, 'evidencia': 'poucos testes',
                         'palavras_chave': ['xunit', 'JOIN']},
                        {'nome': DDD, 'luzia_sugere': 1, 'alvo': 4, 'palavras_chave': []}],
             'plano': [{'acoes': [{'titulo': 'Otimizar um JOIN', 'skill': TESTES, 'conceitos': []}]}]}
    out = prismas.dividir_plano(plano)
    nomes = [s['nome'] for s in out['skills']]
    assert nomes == ['Testes e Qualidade', 'SQL', DDD]
    sql = out['skills'][1]
    assert sql['luzia_sugere'] == 2 and sql['alvo'] == 4 and sql['dividido_de'] == TESTES and 'JOIN' in sql['palavras_chave']
    assert out['plano'][0]['acoes'][0]['skill'] == 'SQL'
    assert not any(prismas.composto(n) for n in nomes)


# ------------------------------------------------------------------ pedido `dividir`
from luzia import acoes, banco, jogo, pedidos, pipeline, trajetoria  # noqa: E402

TESTE_GUIADO = acoes.aid('rota', 'Escrever um teste de unidade guiado')
COMPONENTE = acoes.aid('rota', 'Extrair um componente de tela')


@pytest.fixture
def con(privado, monkeypatch):
    def sem_modelo(*a, **k):  # dividir nunca chama o modelo
        raise AssertionError('dividir não deve chamar o modelo')
    monkeypatch.setattr(pipeline, 'run_plan', sem_modelo)
    jogo.sincronizar(trajetoria.plano())
    c = banco.conectar()
    yield c
    c.close()


def _prisma(con, nome):
    return next((p for p in trajetoria.prismas(con, incluir_arquivados=True) if p['nome'] == nome), None)


def test_dividir_cria_prismas_herdados_arquiva_o_antigo_e_preserva_lumens(con):
    jogo.lancar(TESTES, 40, 'propria', 'feixe', TESTE_GUIADO)
    jogo.lancar(TESTES, 10, 'refletida', 'observer', 's1')
    total_antes = trajetoria.lumens_totais(con)
    lm_antigo = con.execute('SELECT SUM(lm) FROM lumen WHERE prisma = ?', (TESTES,)).fetchone()[0]
    antigo = _prisma(con, TESTES)
    versoes_antes = len(trajetoria.versoes(con))

    p = pedidos.abrir(con, 'dividir', TESTES, 'um prisma por habilidade')
    p = pedidos.propor(con, p['id'])
    prop = p['proposta']
    assert p['estado'] == 'proposto' and p['tipo'] == 'dividir'
    assert [x['nome'] for x in prop['partes']] == ['Testes e Qualidade', 'SQL']
    assert all(x['nivel'] == antigo['nivel'] and x['meta'] == antigo['meta'] for x in prop['partes'])
    para = {a['id']: a['para'] for a in prop['avancos']}
    assert para[TESTE_GUIADO] == 'Testes e Qualidade'

    out = pedidos.aceitar(con, p['id'])
    assert out['estado'] == 'aceito' and out['versao'] == versoes_antes + 1
    assert _prisma(con, TESTES)['estado'] == 'arquivado'
    for nome in ('Testes e Qualidade', 'SQL'):
        novo = _prisma(con, nome)
        assert (novo['estado'], novo['nivel'], novo['meta'], novo['origem']) == ('ativo', antigo['nivel'], antigo['meta'], 'pedido')
        reg = trajetoria.registros(con, nome)
        assert [(r['origem'], r['para']) for r in reg] == [('pedido', antigo['nivel'])]
    assert 'xunit' in _prisma(con, 'Testes e Qualidade')['palavras']
    foto = [x['nome'] for x in trajetoria.versoes(con)[-1]['prismas']]
    assert 'SQL' in foto and TESTES not in foto
    # lúmens: livro intacto no prisma arquivado, totais iguais, o nível novo conta de agora
    assert trajetoria.lumens_totais(con) == total_antes
    assert con.execute('SELECT SUM(lm) FROM lumen WHERE prisma = ?', (TESTES,)).fetchone()[0] == lm_antigo
    rota = jogo.rota(trajetoria.plano(), con)
    nomes = [s['nome'] for s in rota['skills']]
    assert 'SQL' in nomes and 'Testes e Qualidade' in nomes and TESTES not in nomes
    assert next(s for s in rota['skills'] if s['nome'] == 'SQL')['lm'] == 0


def test_avanco_reclassificado_continua_no_prisma_novo_depois_do_sync(con):
    p = pedidos.propor(con, pedidos.abrir(con, 'dividir', FRONT)['id'])
    assert [x['nome'] for x in p['proposta']['partes']] == ['JavaScript', 'Razor', 'React']
    assert {a['id']: a['para'] for a in p['proposta']['avancos']}[COMPONENTE] == 'React'
    pedidos.aceitar(con, p['id'])
    plan = trajetoria.plano()
    for _ in range(2):  # o painel sincroniza a cada leitura: o avanço não volta para o prisma antigo
        jogo.sincronizar(plan)
        a = next(x for x in jogo.avancos(con) if x['id'] == COMPONENTE)
        assert a['skill_plano'] == 'React' and a['skill'] == 'React'
    assert not [x for x in jogo.avancos(con, prisma=FRONT) if x['estado'] != 'conquistado']


def test_ajustar_dividir_renomeia_parte_e_move_avanco(con):
    p = pedidos.abrir(con, 'dividir', TESTES)
    pedidos.propor(con, p['id'])
    p = pedidos.propor(con, p['id'], partes=['Testes automatizados', 'SQL'], mover={TESTE_GUIADO: 'SQL'})
    assert len(p['propostas']) == 2
    assert [x['nome'] for x in p['proposta']['partes']] == ['Testes automatizados', 'SQL']
    assert {a['id']: a['para'] for a in p['proposta']['avancos']}[TESTE_GUIADO] == 'SQL'
    with pytest.raises(ValueError):  # uma parte também tem de ser uma habilidade só
        pedidos.propor(con, p['id'], partes=['Kafka / RabbitMQ', 'SQL'])
    with pytest.raises(ValueError):
        pedidos.propor(con, p['id'], mover={TESTE_GUIADO: 'Parte que não existe'})
    pedidos.aceitar(con, p['id'])
    assert _prisma(con, 'Testes automatizados')['estado'] == 'ativo'
    assert next(x for x in jogo.avancos(con) if x['id'] == TESTE_GUIADO)['skill_plano'] == 'SQL'


def test_dividir_recusa_prisma_isolado_desconhecido_ou_parte_que_ja_existe(con):
    with pytest.raises(ValueError):
        pedidos.abrir(con, 'dividir', DDD)
    with pytest.raises(ValueError):
        pedidos.abrir(con, 'dividir', 'Prisma que não existe / Outro')
    with banco.transacao(con):
        con.execute("INSERT INTO prisma (nome, palavras_json, nivel, meta, estado, origem) "
                    "VALUES ('SQL', '[]', 1, 3, 'ativo', 'pedido')")
    p = pedidos.abrir(con, 'dividir', TESTES)
    with pytest.raises(ValueError):
        pedidos.propor(con, p['id'])


def test_incluir_recusa_nome_composto_e_reativar_prisma_dividido_e_recusado(con):
    with pytest.raises(ValueError):
        pedidos.abrir(con, 'incluir', 'Kafka / RabbitMQ')
    pedidos.aceitar(con, pedidos.propor(con, pedidos.abrir(con, 'dividir', TESTES)['id'])['id'])
    with pytest.raises(ValueError):
        pedidos.abrir(con, 'reativar', TESTES)


def test_dividir_todos_abre_um_pedido_por_prisma_composto(con):
    lista = pedidos.dividir_todos(con)
    assert sorted(p['prisma'] for p in lista) == sorted([TESTES, FRONT])
    assert all(p['estado'] == 'proposto' for p in lista)
    assert pedidos.dividir_todos(con) == []  # já há pedido aberto para cada um: nada duplica


# ------------------------------------------------------------------ entregas, triagem e acender
def test_entregas_recalculadas_com_os_prismas_novos(con, privado):
    from luzia import entregas
    from luzia.tests.test_entregas import Repo, _dias, _entrada
    (privado.parent / 'repo-divisao').mkdir()
    repo = Repo(privado.parent / 'repo-divisao')
    repo.commit('feat: otimiza JOIN da consulta', 'src/Consulta.sql', quando=_dias(5))
    _entrada(privado, repo)
    entregas.atualizar(con)
    antes = {r[0] for r in con.execute('SELECT prisma FROM entrega_prisma')}
    assert TESTES in antes and 'SQL' not in antes
    pedidos.aceitar(con, pedidos.propor(con, pedidos.abrir(con, 'dividir', TESTES)['id'])['id'])
    entregas.atualizar(con)  # próxima leitura: refaz a janela com os prismas novos
    termos = {r[0]: json.loads(r[1]) for r in con.execute('SELECT prisma, termos_json FROM entrega_prisma')}
    assert 'JOIN' in termos['SQL']
    assert TESTES in termos  # a passagem antiga fica como história do prisma arquivado
    assert entregas.atualizar(con) == {'novas': 0, 'atualizadas': 0}  # e depois volta a ser incremental


def test_triagem_grava_so_prismas_de_uma_habilidade(privado):
    from luzia import planner
    nomes = [n.strip(' "') for n in planner.SKILLS_OBRIGATORIAS.replace(' e "', ', "').split('", ')]
    assert len(nomes) >= 6 and not any(prismas.composto(n) for n in nomes), nomes
    plano = trajetoria.plano()
    plano['skills'] = [{'nome': 'Kafka / RabbitMQ', 'luzia_sugere': 1, 'alvo': 3, 'palavras_chave': ['Kafka', 'RabbitMQ']}]
    pipeline.save_state({}, plano, {'quando': '2026-11-13T10:00:00'}, {})
    with trajetoria.abrir() as c:
        ativos = {p['nome'] for p in trajetoria.prismas(c)}
        gravado = trajetoria.perfil_ler(c, 'plano')
    assert {'Kafka', 'RabbitMQ'} <= ativos and 'Kafka / RabbitMQ' not in ativos
    assert [s['nome'] for s in gravado['skills']] == ['Kafka', 'RabbitMQ']


def test_acender_grava_os_avancos_no_prisma_pedido(privado, monkeypatch):
    from luzia import cli, planner

    def falso(payload, **k):
        acao = {'titulo': 'Revisar um índice composto', 'tipo': 'praticar', 'skill': TESTES, 'dimensao': None,
                'por_que': 'x', 'conceitos': ['índice'], 'como': ['a', 'b'], 'onde_explorar': 'x', 'prompt': 'x',
                'duracao_min': 10}
        assert 'uma habilidade só' in k['schema']
        return planner.LLMResult({'acoes': [acao]}, '{}', 0.1, 1, 1, 'falso/modelo'), {'quando': '2026-11-13T10:00:00'}
    monkeypatch.setattr(pipeline, 'run_plan', falso)
    jogo.sincronizar(trajetoria.plano())
    res = cli.gerar_trecho(DDD)
    assert [a['skill'] for a in res['avancos']] == [DDD]


# ------------------------------------------------------------------ chat e painel
import re  # noqa: E402

from luzia.tests.test_server import api  # noqa: E402,F401  (fixture do painel autenticado)

RE_PREFIXO = re.compile(r'\bPrisma [^(]')  # "Prisma X" num rótulo; "Prismas ..." (título de seção) não casa


def _rodar(monkeypatch, *argv):
    from luzia.tests.test_cli import rodar, visivel, botoes_de
    saida = rodar(monkeypatch, *argv)
    return visivel(saida), botoes_de(saida)


def test_chat_dividir_ajustar_e_aceitar(con, monkeypatch):
    texto, bts = _rodar(monkeypatch, 'dividir', TESTES)
    assert 'Testes e Qualidade' in texto and 'SQL' in texto and 'nível' in texto
    assert not RE_PREFIXO.search(texto)
    pid = next(p['id'] for p in pedidos.listar(con) if p['tipo'] == 'dividir')
    assert {'pedido aceitar %d' % pid, 'pedido ajustar %d' % pid} <= {b['rodar'] for b in bts}
    texto, _ = _rodar(monkeypatch, 'pedido', 'ajustar', str(pid), '--partes', 'Testes automatizados', 'SQL',
                      '--mover', f'{TESTE_GUIADO}=SQL')
    assert 'Testes automatizados' in texto
    _rodar(monkeypatch, 'pedido', 'aceitar', str(pid))
    assert _prisma(con, 'Testes automatizados')['estado'] == 'ativo' and _prisma(con, TESTES)['estado'] == 'arquivado'
    assert next(x for x in jogo.avancos(con) if x['id'] == TESTE_GUIADO)['skill_plano'] == 'SQL'


def test_chat_dividir_todos_e_oferta_nos_botoes(con, monkeypatch):
    _, bts = _rodar(monkeypatch, 'hoje')
    assert any(b['rodar'] == 'dividir-todos' for b in bts)
    texto, bts = _rodar(monkeypatch, 'dividir-todos')
    assert sorted(p['prisma'] for p in pedidos.listar(con) if p['tipo'] == 'dividir') == sorted([TESTES, FRONT])
    assert 'React' in texto and 'SQL' in texto


def test_rotulos_do_chat_sem_prefixo_prisma(con, monkeypatch):
    for comando in (('hoje',), ('trajetoria',), ('avancos',), ('pedido',)):
        texto, bts = _rodar(monkeypatch, *comando)
        assert not RE_PREFIXO.search(texto), (comando, RE_PREFIXO.findall(texto))
        assert not any(RE_PREFIXO.search(b.get('rotulo', '') + ' ' + b.get('descricao', '')) for b in bts), comando


def test_painel_dividir_e_estado_com_a_divisao_sugerida(api, monkeypatch):
    monkeypatch.setattr(pipeline, 'run_plan', lambda *a, **k: (_ for _ in ()).throw(AssertionError('sem modelo')))
    c, est = api('GET', '/api/estado')
    assert c == 200
    por_nome = {p['nome']: p for p in est['prismas']}
    assert por_nome[TESTES]['divisao'] == ['Testes e Qualidade', 'SQL'] and por_nome[DDD]['divisao'] == []
    c, r = api('POST', '/api/pedido', {'acao': 'abrir', 'tipo': 'dividir', 'prisma': TESTES})
    assert c == 200 and r['pedido']['estado'] == 'proposto'
    pid = r['pedido']['id']
    c, r = api('POST', '/api/pedido', {'acao': 'ajustar', 'id': pid, 'partes': ['Testes e Qualidade', 'Banco SQL'],
                                       'mover': {TESTE_GUIADO: 'Banco SQL'}})
    assert c == 200 and [x['nome'] for x in r['pedido']['proposta']['partes']] == ['Testes e Qualidade', 'Banco SQL']
    c, r = api('POST', '/api/pedido', {'acao': 'ajustar', 'id': pid, 'partes': 'não é lista'})
    assert c == 400
    c, r = api('POST', '/api/pedido', {'acao': 'dividir_todos'})
    assert c == 200 and [p['prisma'] for p in r['pedidos']] == [FRONT]
    assert api('POST', '/api/pedido', {'acao': 'aceitar', 'id': pid})[0] == 200
    _, est = api('GET', '/api/estado')
    assert {'Testes e Qualidade', 'Banco SQL'} <= {p['nome'] for p in est['prismas'] if p['estado'] == 'ativo'}


def test_painel_sem_prefixo_prisma_nos_rotulos():
    from pathlib import Path
    js = (Path(prismas.__file__).parent / 'painel' / 'luzia.js').read_text(encoding='utf-8')
    assert not re.findall(r'Prisma \$\{', js)


# ------------------------------------------------------------------ nome curto (painel e chat usam o mesmo)
@pytest.mark.parametrize('nome, curto', [
    ('Domain-Driven Design (DDD)', 'DDD'),
    ('SQL', 'SQL'),
    ('Front-end (JS / Razor / React)', 'Front-end'),
    ('Arquitetura .NET / Clean Architecture', 'Clean Architecture'),
    ('Programação Agêntica e Fluxo com IA', 'Programação Agênti…'),
    ('  Testes e Qualidade  ', 'Testes e Qualidade'),
])
def test_nome_curto_do_prisma(nome, curto):
    assert prismas.nome_curto(nome) == curto


def test_estado_expoe_nome_curto_e_o_chat_usa_o_mesmo(api, monkeypatch):
    from luzia import cli
    c, est = api('GET', '/api/estado')
    assert c == 200
    por_nome = {p['nome']: p['nome_curto'] for p in est['prismas']}
    assert por_nome[DDD] == 'DDD' and all(v == prismas.nome_curto(k) for k, v in por_nome.items())
    assert cli.nome_prisma(DDD) == 'DDD'
    texto, _ = _rodar(monkeypatch, 'centelhas')  # apelido de `avancos`
    assert texto.startswith('## Luzia · Centelhas') and 'Domain-Driven Design' not in texto


def test_painel_mostra_base_modelo_e_data_atras_de_um_icone_focavel_e_guarda_o_detalhe_aberto():
    from pathlib import Path
    js = (Path(prismas.__file__).parent / 'painel' / 'luzia.js').read_text(encoding='utf-8')
    # a assinatura curta continua levando base, modelo e data (popover acessível pelo teclado)
    assert 'class="info-base" tabindex="0" role="img" aria-label="${esc(dica)}"' in js
    assert 'Base: ${base} · Modelo: ${leitura.modelo}' in js
    # o detalhe aberto de uma entrega sobrevive ao render() do polling; descartar oferece Desfazer
    assert 'const entregasAbertas = new Set()' in js and "entregasAbertas.has(String(e.id))" in js
    assert "{ rotulo: 'Desfazer', dados: { restaurar: id } }" in js
    assert 'nome_curto' in js and 'Leitura da Luzia' not in js and 'Lampejo' not in js
