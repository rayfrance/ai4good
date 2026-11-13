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
