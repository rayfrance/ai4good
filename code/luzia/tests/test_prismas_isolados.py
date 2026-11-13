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
