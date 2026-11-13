"""Pedidos formais de mudança da trajetória (Tarefa 11): incluir, arquivar, reativar e mudar meta."""

import json
from datetime import datetime

import pytest

from luzia import banco, jogo, leituras, pipeline, planner, trajetoria

DDD = 'Domain-Driven Design (DDD)'
TESTES = 'Testes e Qualidade / SQL'
FRONT = 'Front-end (JS / Razor / React)'
MENSAGERIA = 'Mensageria'


@pytest.fixture
def con(privado):
    c = banco.conectar()
    yield c
    c.close()


def _acao_sintetica(titulo: str, skill: str, duracao: int = 15) -> dict:
    return {
        'titulo': titulo,
        'tipo': 'praticar',
        'skill': skill,
        'dimensao': None,
        'por_que': f'Praticar {skill} no repositório.',
        'conceitos': [skill],
        'como': ['Localizar ponto de integração.', 'Explicar o contrato de mensagens.'],
        'onde_explorar': 'Serviços de integração do projeto.',
        'prompt': f'Me faça uma pergunta sobre {skill} e espere minha resposta.',
        'duracao_min': duracao,
    }


def _simular_modelo_pedido(monkeypatch, chamadas: list):
    def falso_run_plan(payload, prep_seconds=0.0, label='demo', hits=None, save_current_state=False, schema=None, intro=None):
        chamadas.append({'payload': payload, 'schema': schema, 'label': label})
        ped = payload.get('pedido') or {}
        skill = ped.get('prisma') or MENSAGERIA
        nv = ped.get('nivel_solicitado') if ped.get('nivel_solicitado') is not None else 1
        mt = ped.get('meta_solicitada') if ped.get('meta_solicitada') is not None else 4
        plan_out = {
            'nivel_partida': nv,
            'meta': mt,
            'palavras_chave': ['Queue', 'RabbitMQ', 'EventBus', 'fila', 'mensageria', ' consumidor', 'evento', ' Tópico'],
            'acoes': [
                _acao_sintetica(f'Mapear produtor de mensagens ({nv}->{mt})', skill, 15),
                _acao_sintetica(f'Explicar idempotência no consumidor ({nv}->{mt})', skill, 20),
                _acao_sintetica(f'Testar falha de entrega na fila ({nv}->{mt})', skill, 25),
            ],
            'analise': f'O prisma {skill} parte do nível {nv} rumo à meta {mt} com base na trajetória atual.',
        }
        res = planner.LLMResult(
            plan=plan_out,
            raw=json.dumps(plan_out, ensure_ascii=False),
            seconds=0.5,
            tokens_in=250,
            tokens_out=120,
            model='gemini/gemini-3.5-flash-lite',
        )
        return res, {'quando': datetime.now().isoformat(timespec='seconds'), 'modelo': res.model}

    monkeypatch.setattr(pipeline, 'run_plan', falso_run_plan)


def test_um_pedido_aberto_por_prisma(con, monkeypatch):
    from luzia import pedidos

    chamadas = []
    _simular_modelo_pedido(monkeypatch, chamadas)

    p1 = pedidos.abrir(con, 'incluir', MENSAGERIA, ' Comecei a mexer com filas ')
    assert p1['estado'] == 'aberto' and p1['prisma'] == MENSAGERIA

    with pytest.raises(ValueError):
        pedidos.abrir(con, 'incluir', MENSAGERIA, 'duplicado enquanto aberto')

    pedidos.propor(con, p1['id'])
    with pytest.raises(ValueError):
        pedidos.abrir(con, 'mudar_meta', MENSAGERIA, 'duplicado enquanto proposto')

    # Outro prisma pode abrir normalmente
    p_outro = pedidos.abrir(con, 'mudar_meta', DDD, 'Quero ir até nível 5')
    assert p_outro['prisma'] == DDD

    # Depois de recusar, o prisma fica livre para novo pedido
    pedidos.recusar(con, p1['id'])
    p2 = pedidos.abrir(con, 'incluir', MENSAGERIA, 'Agora sim')
    assert p2['id'] != p1['id'] and p2['estado'] == 'aberto'


def test_ajustar_guarda_propostas(con, monkeypatch):
    from luzia import pedidos

    chamadas = []
    _simular_modelo_pedido(monkeypatch, chamadas)

    ped = pedidos.abrir(con, 'incluir', MENSAGERIA, 'Incluir mensageria')
    p1 = pedidos.propor(con, ped['id'])
    assert p1['estado'] == 'proposto'
    assert (p1['proposta']['nivel_partida'], p1['proposta']['meta']) == (1, 4)
    assert len(p1['propostas']) == 1

    p2 = pedidos.propor(con, ped['id'], nivel=2, meta=4)
    assert (p2['proposta']['nivel_partida'], p2['proposta']['meta']) == (2, 4)
    assert len(p2['propostas']) == 2

    p3 = pedidos.propor(con, ped['id'], nivel=2, meta=5)
    assert (p3['proposta']['nivel_partida'], p3['proposta']['meta']) == (2, 5)
    assert len(p3['propostas']) == 3
    assert [(x['nivel_partida'], x['meta']) for x in p3['propostas']] == [(1, 4), (2, 4), (2, 5)]
    assert len(chamadas) == 3
    assert p3['leitura'] is not None and p3['leitura']['modelo'] == 'gemini/gemini-3.5-flash-lite'


def test_aceitar_incluir_cria_prisma_avancos_e_versao(con, monkeypatch):
    from luzia import pedidos

    chamadas = []
    _simular_modelo_pedido(monkeypatch, chamadas)

    resumo_antes = trajetoria.resumo(con)
    versoes_antes = len(trajetoria.versoes(con))

    ped = pedidos.abrir(con, 'incluir', MENSAGERIA, 'Demanda de filas no projeto')
    pedidos.propor(con, ped['id'], nivel=1, meta=4)
    aceito = pedidos.aceitar(con, ped['id'])
    assert aceito['estado'] == 'aceito' and aceito['decidido_em']

    ativos = {p['nome']: p for p in trajetoria.prismas(con)}
    assert MENSAGERIA in ativos
    assert (ativos[MENSAGERIA]['nivel'], ativos[MENSAGERIA]['meta'], ativos[MENSAGERIA]['origem']) == (1, 4, 'pedido')

    regs = con.execute("SELECT * FROM nivel_registro WHERE prisma = ? AND origem = 'pedido'", (MENSAGERIA,)).fetchall()
    assert len(regs) == 1 and regs[0]['para'] == 1

    avs = jogo.avancos(con, prisma=MENSAGERIA)
    assert len(avs) == 3
    assert all(a.get('origem') == 'pedido' and a.get('valor_lm') >= 10 for a in avs)

    versoes_depois = trajetoria.versoes(con)
    assert len(versoes_depois) == versoes_antes + 1
    assert versoes_depois[-1]['origem'] == 'pedido' and versoes_depois[-1]['pedido_id'] == ped['id']
    assert MENSAGERIA in [p['nome'] for p in versoes_depois[-1]['prismas']]

    resumo_depois = trajetoria.resumo(con)
    assert resumo_depois['niveis_total'] == resumo_antes['niveis_total'] + 3

    leitura = leituras.obter(con, 'pedido', str(ped['id']))
    assert leitura is not None and leitura['modelo'] == 'gemini/gemini-3.5-flash-lite'


def test_arquivar_preserva_lumens_e_reativar_devolve(con, monkeypatch):
    from luzia import pedidos

    # Garante que arquivar e reativar NUNCA chamam o modelo
    monkeypatch.setattr(pipeline, 'run_plan', lambda *a, **k: (_ for _ in ()).throw(AssertionError('não deve chamar o modelo')))

    jogo.lancar(DDD, 80, 'propria', 'feixe', 'av1')
    antes = trajetoria.resumo(con)
    assert antes['niveis_total'] == 6 and antes['lm_total'] == 80

    p_arq = pedidos.abrir(con, 'arquivar', DDD, 'Foco mudou neste trimestre')
    pedidos.propor(con, p_arq['id'])
    pedidos.aceitar(con, p_arq['id'])

    meio = trajetoria.resumo(con)
    assert DDD not in [p['nome'] for p in trajetoria.prismas(con)]
    assert meio['niveis_total'] == 3  # 3 níveis de DDD saíram da trajetória ativa
    assert meio['lm_total'] == 80 and meio['luz_propria'] == 100  # lúmens preservados!

    p_reat = pedidos.abrir(con, 'reativar', DDD, 'Voltando a trabalhar no domínio')
    pedidos.propor(con, p_reat['id'])
    pedidos.aceitar(con, p_reat['id'])

    depois = trajetoria.resumo(con)
    assert DDD in [p['nome'] for p in trajetoria.prismas(con)]
    assert depois == antes


def test_mudar_meta_nao_toca_nivel_nem_lumens(con, monkeypatch):
    from luzia import pedidos

    chamadas = []
    _simular_modelo_pedido(monkeypatch, chamadas)

    jogo.lancar(DDD, 50, 'propria', 'feixe', 'av1')
    regs_antes = con.execute('SELECT COUNT(*) FROM nivel_registro WHERE prisma = ?', (DDD,)).fetchone()[0]
    resumo_antes = trajetoria.resumo(con)

    ped = pedidos.abrir(con, 'mudar_meta', DDD, 'Quero dominar DDD até o nível 5')
    prop = pedidos.propor(con, ped['id'], meta=5)
    assert prop['proposta']['nivel_partida'] == 1 and prop['proposta']['meta'] == 5
    assert prop['proposta']['ganho_niveis'] == 1

    pedidos.aceitar(con, ped['id'])
    p_ddd = {p['nome']: p for p in trajetoria.prismas(con)}[DDD]
    assert p_ddd['nivel'] == 1 and p_ddd['meta'] == 5
    assert con.execute('SELECT COUNT(*) FROM nivel_registro WHERE prisma = ?', (DDD,)).fetchone()[0] == regs_antes
    assert jogo.progresso_skill(DDD)['lm'] == 50
    assert trajetoria.resumo(con)['niveis_total'] == resumo_antes['niveis_total'] + 1


def test_recusar_nao_muda_trajetoria(con, monkeypatch):
    from luzia import pedidos

    chamadas = []
    _simular_modelo_pedido(monkeypatch, chamadas)

    versoes_antes = trajetoria.versoes(con)
    resumo_antes = trajetoria.resumo(con)

    ped = pedidos.abrir(con, 'incluir', MENSAGERIA, 'Talvez estudar filas')
    pedidos.propor(con, ped['id'], nivel=1, meta=3)
    rec = pedidos.recusar(con, ped['id'])

    assert rec['estado'] == 'recusado' and rec['decidido_em']
    assert MENSAGERIA not in [p['nome'] for p in trajetoria.prismas(con, incluir_arquivados=True)]
    assert jogo.avancos(con, prisma=MENSAGERIA) == []
    assert trajetoria.versoes(con) == versoes_antes
    assert trajetoria.resumo(con) == resumo_antes
    assert len(pedidos.listar(con)) == 1


def test_sem_modelo_propoe_com_os_valores_da_pessoa_e_aceita(con, monkeypatch):
    """Modelo fora do ar ou sem chave: a proposta sai dos valores pedidos (ou atuais), sem análise, e pode ser aceita."""
    from luzia import pedidos

    def sem_modelo(*a, **k):
        raise RuntimeError('Falta a chave GEMINI_API_KEY: configure em Ajustes > Modelo da Luzia.')

    monkeypatch.setattr(pipeline, 'run_plan', sem_modelo)
    ped = pedidos.abrir(con, 'incluir', MENSAGERIA, 'Filas no projeto')
    p = pedidos.propor(con, ped['id'], nivel=2, meta=4)
    assert p['estado'] == 'proposto'
    assert (p['proposta']['nivel_partida'], p['proposta']['meta']) == (2, 4)
    assert p['proposta']['acoes'] == [] and not p['proposta'].get('analise')
    assert p['proposta']['leitura_indisponivel'] and 'GEMINI_API_KEY' in p['proposta']['leitura_indisponivel']
    assert p['leitura'] is None and p['leitura_id'] is None
    assert con.execute("SELECT COUNT(*) FROM leitura WHERE alvo_tipo = 'pedido'").fetchone()[0] == 0
    aceito = pedidos.aceitar(con, ped['id'])
    assert aceito['estado'] == 'aceito'
    assert {p['nome']: (p['nivel'], p['meta']) for p in trajetoria.prismas(con)}[MENSAGERIA] == (2, 4)

    # mudar meta sem modelo: nível atual, meta pedida
    ped2 = pedidos.abrir(con, 'mudar_meta', DDD, 'Quero ir além')
    p2 = pedidos.propor(con, ped2['id'], meta=5)
    assert (p2['proposta']['nivel_partida'], p2['proposta']['meta']) == (1, 5) and p2['estado'] == 'proposto'
    # sem nada pedido: os valores atuais
    p3 = pedidos.propor(con, ped2['id'])
    assert (p3['proposta']['nivel_partida'], p3['proposta']['meta']) == (1, 4)


def test_ajuste_sem_modelo_nao_herda_analise_antiga(con, monkeypatch):
    from luzia import pedidos

    _simular_modelo_pedido(monkeypatch, [])
    ped = pedidos.abrir(con, 'incluir', MENSAGERIA, 'Filas')
    assert pedidos.propor(con, ped['id'])['leitura'] is not None
    monkeypatch.setattr(pipeline, 'run_plan', lambda *a, **k: (_ for _ in ()).throw(RuntimeError('sem internet')))
    p = pedidos.propor(con, ped['id'], nivel=3, meta=5)
    assert p['leitura'] is None and p['leitura_id'] is None  # a análise velha era de outra proposta


def test_texto_que_nao_veio_do_modelo_nunca_vira_leitura(con, monkeypatch):
    from luzia import pedidos

    def sem_analise(payload, **kw):
        plan_out = {'nivel_partida': 1, 'meta': 3, 'palavras_chave': ['fila'], 'acoes': []}
        res = planner.LLMResult(plan=plan_out, raw='{}', seconds=0.1, tokens_in=1, tokens_out=1, model='gemini/x')
        return res, {'quando': '2026-11-12T10:00:00', 'modelo': res.model}

    monkeypatch.setattr(pipeline, 'run_plan', sem_analise)
    ped = pedidos.abrir(con, 'incluir', MENSAGERIA, 'Filas')
    p = pedidos.propor(con, ped['id'])
    assert not p['proposta'].get('analise') and p['leitura'] is None
    assert con.execute("SELECT COUNT(*) FROM leitura WHERE alvo_tipo = 'pedido'").fetchone()[0] == 0
