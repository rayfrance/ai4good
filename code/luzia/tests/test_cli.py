"""Testes da Tarefa 12 — CLI, comandos, foco e vocabulário novo."""

from __future__ import annotations

import io
import json
import re
import sys
from contextlib import redirect_stdout
from pathlib import Path
from types import SimpleNamespace

import pytest

from luzia import acoes, banco, cli, entregas, jogo, observer, pedidos, pipeline, statusline, trajetoria

DDD = 'Domain-Driven Design (DDD)'
TESTES = 'Testes e Qualidade / SQL'

RE_TERMOS_ANTIGOS = re.compile(
    r'\b(feixes?|degraus?|trechos?(?!\s+d[eo]\s+c[óo]digo)|rota|cart[aã]o|cart[oõ]es)\b',
    re.IGNORECASE,
)


def rodar(monkeypatch, *argv: str) -> str:
    monkeypatch.setattr(sys, 'argv', ['luzia', *[str(a) for a in argv]])
    buf = io.StringIO()
    with redirect_stdout(buf):
        cli.main()
    return buf.getvalue()


def visivel(saida: str) -> str:
    return '\n'.join(l for l in saida.splitlines() if not l.startswith('LUZIA_'))


def botoes_de(saida: str) -> list[dict]:
    linha = next((x for x in saida.splitlines() if x.startswith('LUZIA_BOTOES=')), None)
    return json.loads(linha.split('=', 1)[1]) if linha else []


def tem_rodape_botoes(saida: str) -> bool:
    linhas = [l for l in saida.splitlines() if l.strip()]
    return (
        any(l.startswith('LUZIA_CLI=') for l in linhas)
        and any(l.startswith('LUZIA_PERGUNTA=') for l in linhas)
        and any(l.startswith('LUZIA_BOTOES=') for l in linhas)
        and len(botoes_de(saida)) >= 1
    )


def _semear_entrega(con) -> int:
    with banco.transacao(con):
        cur = con.execute(
            "INSERT INTO entrega (chave, titulo, inicio, fim, fonte, commits, arquivos, linhas, areas_json) "
            "VALUES ('pr:1', 'Separa agregado de agendamento', '2026-11-10T10:00:00', '2026-11-11T15:00:00', "
            "'merge-pr', 2, 4, 90, '[\"Back-end C# / .NET\"]')"
        )
        eid = int(cur.lastrowid)
        con.execute(
            'INSERT INTO entrega_prisma (entrega_id, prisma, termos_json) VALUES (?, ?, ?)',
            (eid, DDD, json.dumps(['aggregate', 'domain'])),
        )
    return eid


def test_toda_saida_termina_em_botoes(privado, monkeypatch):
    plan = pipeline.load_state()['plano']
    cat = jogo.sincronizar(plan)
    sugeridos = [k for k, f in cat.items() if f['estado'] == 'sugerido']
    f1, f2 = sugeridos[0], sugeridos[1]

    with trajetoria.abrir() as con:
        eid = _semear_entrega(con)
    monkeypatch.setattr(entregas, 'atualizar', lambda con, dias=90: {'novas': 0, 'atualizadas': 0})

    comandos = [
        ('hoje',),
        ('trajetoria',),
        ('rota',),
        ('next-level',),
        ('avancos',),
        ('acoes',),
        ('fila',),
        ('fazer', f1),
        ('registrar', f1, '--nota', '3', '--resumo', 'Explicou invariantes do agregado'),
        ('descartar', f2, '--motivo', 'agora_nao'),
        ('restaurar', f2),
        ('enviar', f2),
        ('guardar', DDD, '--pergunta', 'Como separar domínio e infraestrutura?'),
        ('cartao', DDD, '--acao', 'guardar'),
        ('subir', DDD),
        ('nivel', DDD, '2'),
        ('entregas',),
        ('entrega', str(eid)),
        ('dossie',),
        ('modo',),
        ('modo', 'passivo'),
        ('modelo',),
    ]
    for argv in comandos:
        s = rodar(monkeypatch, *argv)
        assert tem_rodape_botoes(s), f'Comando {argv} não terminou com botões válidos:\n{s}'


def test_avancos_filtros(privado, monkeypatch):
    plan = pipeline.load_state()['plano']
    jogo.sincronizar(plan)

    s_ddd = rodar(monkeypatch, 'avancos', '--estado', 'sugerido', '--prisma', DDD)
    v_ddd = visivel(s_ddd)
    assert 'Modelar um agregado de exemplo' in v_ddd
    assert 'Escrever um teste de unidade guiado' not in v_ddd
    assert tem_rodape_botoes(s_ddd)

    s_testes = rodar(monkeypatch, 'avancos', '--prisma', TESTES, '--tipo', 'praticar')
    v_testes = visivel(s_testes)
    assert 'Escrever um teste de unidade guiado' in v_testes
    assert 'Modelar um agregado de exemplo' not in v_testes


def test_pedido_fluxo_completo_pelo_chat(privado, monkeypatch):
    recebidos = []

    def fake_run_plan(payload, schema=None, intro='', **kw):
        recebidos.append(payload)  # o payload é o que o código de verdade monta: pedido.nivel_solicitado / meta_solicitada
        ped = payload.get('pedido') or {}
        nivel = ped.get('nivel_solicitado') if ped.get('nivel_solicitado') is not None else 1
        meta = ped.get('meta_solicitada') if ped.get('meta_solicitada') is not None else 3
        res = {
            'nivel_partida': nivel,
            'meta': meta,
            'palavras_chave': ['opentelemetry', 'tracing', 'metrics'],
            'analise': f'Partida no nível {nivel} rumo à meta {meta} com foco em telemetria.',
            'acoes': [
                {
                    'titulo': 'Instrumentar endpoint crítico com tracing',
                    'tipo': 'praticar',
                    'skill': 'Observabilidade',
                    'dimensao': None,
                    'por_que': 'Dar visibilidade à latência real.',
                    'conceitos': ['tracing', 'span'],
                    'como': ['Escolher endpoint.', 'Adicionar span e medir.'],
                    'onde_explorar': 'Camada de entrada HTTP.',
                    'prompt': 'Me guie na instrumentação de um endpoint com tracing.',
                    'duracao_min': 20,
                }
            ],
        }
        reg = {
            'quando': '2026-11-12T15:00:00',
            'tempo_total_s': 0.5,
            'pico_memoria_mib': 10.0,
            'tokens_entrada': 50,
            'tokens_saida': 40,
            'versao': 'test',
            'modelo': 'gemini-2.5-flash',
        }
        return SimpleNamespace(plan=res), reg

    monkeypatch.setattr(pipeline, 'run_plan', fake_run_plan)

    s_abrir = rodar(monkeypatch, 'pedido', 'abrir', 'incluir', 'Observabilidade', '--motivo', 'Monitorar serviços')
    assert tem_rodape_botoes(s_abrir)
    botoes = botoes_de(s_abrir)
    rotulos = [b['rotulo'].lower() for b in botoes]
    assert any('aceitar' in r for r in rotulos)
    assert any('ajustar' in r for r in rotulos)
    assert any('recusar' in r for r in rotulos)

    with trajetoria.abrir() as con:
        lista = pedidos.listar(con)
        assert len(lista) == 1
        pid = lista[0]['id']

    s_ajustar = rodar(monkeypatch, 'pedido', 'ajustar', str(pid), '--nivel', '2', '--meta', '4')
    assert tem_rodape_botoes(s_ajustar)
    # o modelo recebeu o pedido de verdade (nível 2, meta 4) e a proposta impressa traz exatamente esses números
    assert recebidos[-1]['pedido']['nivel_solicitado'] == 2 and recebidos[-1]['pedido']['meta_solicitada'] == 4
    assert 'nível **2 → meta 4/5**' in visivel(s_ajustar)
    assert 'Partida no nível 2 rumo à meta 4' in visivel(s_ajustar)

    s_aceitar = rodar(monkeypatch, 'pedido', 'aceitar', str(pid))
    assert tem_rodape_botoes(s_aceitar)
    assert 'Observabilidade' in visivel(s_aceitar)

    s_traj = rodar(monkeypatch, 'trajetoria')
    v_traj = visivel(s_traj)
    assert 'Observabilidade' in v_traj
    assert '▰' in v_traj


def test_vocabulario_sem_termos_antigos(privado, monkeypatch):
    plan = pipeline.load_state()['plano']
    cat = jogo.sincronizar(plan)
    f1 = next(k for k, f in cat.items() if f['estado'] == 'sugerido')

    with trajetoria.abrir() as con:
        eid = _semear_entrega(con)
    monkeypatch.setattr(entregas, 'atualizar', lambda con, dias=90: {'novas': 0, 'atualizadas': 0})

    saidas = [
        rodar(monkeypatch, 'hoje'),
        rodar(monkeypatch, 'trajetoria'),
        rodar(monkeypatch, 'avancos'),
        rodar(monkeypatch, 'fila'),
        rodar(monkeypatch, 'fazer', f1),
        rodar(monkeypatch, 'registrar', f1, '--nota', '3', '--resumo', 'Explicou bem'),
        rodar(monkeypatch, 'subir', DDD),
        rodar(monkeypatch, 'nivel', DDD, '2'),
        rodar(monkeypatch, 'entregas'),
        rodar(monkeypatch, 'entrega', str(eid)),
        rodar(monkeypatch, 'dossie'),
        rodar(monkeypatch, 'modo'),
    ]
    for s in saidas:
        texto = visivel(s)
        achado = RE_TERMOS_ANTIGOS.search(texto)
        assert achado is None, f'Termo antigo "{achado.group(0)}" encontrado na saída visível:\n{texto}'

    v_traj = visivel(rodar(monkeypatch, 'trajetoria'))
    assert '(prisma · skill)' not in v_traj and not re.search(r'\bPrisma [^(s]', v_traj)
    assert 'DDD `' in v_traj and 'Domain-Driven Design' not in v_traj  # nome curto; o completo fica no painel
    assert '▰' in v_traj or '▱' in v_traj

    v_modo = visivel(rodar(monkeypatch, 'modo'))
    assert 'em foco' in v_modo.lower() and 'lampejo' not in v_modo.lower()

    # Verifica também o lampejo do observador e a linha de status
    cartao = observer.cartao_refletida(DDD, 'Como isolar o domínio?')
    assert '✦ Centelha da sessão · DDD · +10 lm refletida' in cartao and 'Prisma Domain' not in cartao
    assert 'lampejo' not in cartao.split('lampejo --skill')[0].lower()  # o comando interno pode manter o nome
    assert RE_TERMOS_ANTIGOS.search(cartao) is None

    linha_st = statusline.linha({'workspace': {'current_dir': str(privado)}})
    assert RE_TERMOS_ANTIGOS.search(linha_st) is None


def test_dossie_formal(privado, monkeypatch):
    plan = pipeline.load_state()['plano']
    cat = jogo.sincronizar(plan)
    f1 = next(k for k, f in cat.items() if f['estado'] == 'sugerido' and f.get('skill_plano') == DDD)

    # Declara nível em TESTES (não deve entrar em "Níveis conquistados")
    rodar(monkeypatch, 'nivel', TESTES, '3')

    # Conquista nível em DDD
    rodar(monkeypatch, 'fazer', f1)
    rodar(monkeypatch, 'registrar', f1, '--nota', '4', '--resumo', 'Modelou agregado com invariantes claras')
    jogo.lancar(DDD, 160, 'propria', 'feixe', 'extra')
    rodar(monkeypatch, 'subir', DDD)

    # Pedido de mudança aceito (arquivar e reativar sem modelo)
    with trajetoria.abrir() as con:
        p = pedidos.abrir(con, 'arquivar', TESTES, 'Pausa temporária')
        pedidos.aceitar(con, p['id'])

    s = rodar(monkeypatch, 'dossie')
    assert tem_rodape_botoes(s)
    m = re.search(r'(C:[^\n]+dossie-[^\n]+\.md|/[^\n]+dossie-[^\n]+\.md)', visivel(s))
    assert m, f'Caminho do dossiê não encontrado em:\n{s}'
    conteudo = Path(m.group(1).strip()).read_text(encoding='utf-8')

    assert '## Níveis conquistados' in conteudo
    assert '## Ações concluídas' in conteudo
    assert '## Pedidos de mudança aceitos' in conteudo
    assert 'pontos de evidência' in conteudo
    assert 'autoria própria' in conteudo
    # O nível declarado não entra na seção de níveis conquistados
    secao_conq = conteudo.split('## Níveis conquistados')[1].split('## Ações concluídas')[0]
    assert DDD in secao_conq
    assert TESTES not in secao_conq
    assert 'Pausa temporária' in conteudo


# ------------------------------------------------------------------ entrega: propriedade P1–P4 com base (A4)
def test_entrega_detalhe_mostra_p1_a_p4_com_base(privado, monkeypatch):
    with trajetoria.abrir() as con:
        eid = _semear_entrega(con)
        with banco.transacao(con):
            con.execute("INSERT INTO commit_ (hash, entrega_id, data, mensagem, arquivos, linhas, areas_json) "
                        "VALUES ('h1', ?, '2026-11-10T10:00:00', 'feat: agregado', 4, 90, '[\"C#/.NET\"]')", (eid,))
    s = rodar(monkeypatch, 'entrega', str(eid))
    v = visivel(s)
    assert 'None' not in v and 'n/d%' not in v
    assert re.search(r'P1 Direção no prompt: \*\*65\*\* \(inferido · geral\)', v), v
    assert re.search(r'P2 Coesão: \*\*100\*\* \(calculado\) — 100 − 0 \(4 arquivos\)', v), v
    assert 'P3 Aplicação de conceito: — falta você explicar' in v and 'P4 Decisão de arquitetura: — falta você defender' in v
    assert '**82% seu** (medido em P1 e P2)' in v, v
    assert '(s)' not in v and '2 commits' in v and '4 arquivos' in v  # plural de verdade
    assert tem_rodape_botoes(s)


# ------------------------------------------------------------------ pedidos: erros, sem modelo e leitura com base (A6–A8)
def _modelo_pedido(monkeypatch, modelo_nome='gemini/gemini-2.5-flash'):
    def fake(payload, **kw):
        ped = payload.get('pedido') or {}
        nv = ped.get('nivel_solicitado') if ped.get('nivel_solicitado') is not None else 1
        mt = ped.get('meta_solicitada') if ped.get('meta_solicitada') is not None else 3
        res = {'nivel_partida': nv, 'meta': mt, 'palavras_chave': ['tracing'], 'acoes': [],
               'analise': f'Partida no nível {nv} rumo à meta {mt}.'}
        return SimpleNamespace(plan=res, model=modelo_nome), {'quando': '2026-11-12T15:00:00', 'modelo': modelo_nome}

    monkeypatch.setattr(pipeline, 'run_plan', fake)


def test_pedido_mostra_analise_com_base_modelo_e_data(privado, monkeypatch):
    _modelo_pedido(monkeypatch)
    for argv in (('pedido', 'abrir', 'incluir', 'Observabilidade', '--motivo', 'Monitorar'),
                 ('pedido', 'ajustar', '1', '--nivel', '2', '--meta', '4')):
        v = visivel(rodar(monkeypatch, *argv))
        linha = next(l for l in v.splitlines() if 'Partida no nível' in l)
        assert '— Análise da Luzia, 12 nov' in linha and 'base: ' in linha and 'gemini/gemini-2.5-flash' in linha, linha


def test_pedido_erros_no_chat_terminam_em_botoes(privado, monkeypatch):
    _modelo_pedido(monkeypatch)
    s = rodar(monkeypatch, 'pedido', 'abrir', 'incluir', 'Observabilidade')
    assert tem_rodape_botoes(s)
    casos = [
        (('pedido', 'abrir', 'incluir', 'Observabilidade'), 'já existe um pedido em aberto'),
        (('pedido', 'abrir', 'inventado', 'Outro'), 'tipo de pedido inválido'),
        (('pedido', 'aceitar', 'abc'), 'número do pedido'),
        (('pedido', 'ajustar', '999'), 'pedido desconhecido'),
        (('pedido', 'aceitar', '1'), 'aceito'),
        (('pedido', 'aceitar', '1'), 'já foi aceito'),
        (('pedido', 'recusar', '1'), 'já foi aceito'),
        (('pedido', 'ajustar', '1', '--meta', '5'), 'já foi aceito'),
    ]
    for argv, esperado in casos:
        s = rodar(monkeypatch, *argv)
        assert esperado in visivel(s), (argv, s)
        assert tem_rodape_botoes(s), (argv, s)


def test_pedido_sem_modelo_nao_trava_a_pessoa(privado, monkeypatch):
    def sem_modelo(*a, **k):
        raise RuntimeError('Falta a chave GEMINI_API_KEY: configure em Ajustes > Modelo da Luzia.')

    monkeypatch.setattr(pipeline, 'run_plan', sem_modelo)
    s = rodar(monkeypatch, 'pedido', 'abrir', 'incluir', 'Observabilidade', '--nivel', '2', '--meta', '4')
    v = visivel(s)
    assert 'proposto' in v and 'nível **2 → meta 4/5**' in v and 'Sem análise: análise indisponível' not in v and 'Sem análise' in v
    assert any(b['rodar'] == 'pedido aceitar 1' for b in botoes_de(s))
    s = rodar(monkeypatch, 'pedido', 'abrir', 'incluir', 'Observabilidade')  # tentar de novo explica, não trava
    assert 'já existe um pedido em aberto' in visivel(s) and tem_rodape_botoes(s)
    s = rodar(monkeypatch, 'pedido', 'aceitar', '1')
    assert 'aceito' in visivel(s) and tem_rodape_botoes(s)
    with trajetoria.abrir() as con:
        assert {p['nome']: (p['nivel'], p['meta']) for p in trajetoria.prismas(con)}['Observabilidade'] == (2, 4)


def test_toda_leitura_impressa_tem_base_modelo_e_data(privado, monkeypatch):
    from luzia import leituras, modelo
    monkeypatch.setattr(entregas, 'atualizar', lambda con, dias=90: {'novas': 0, 'atualizadas': 0})
    monkeypatch.setattr(modelo, 'pronto', lambda: False)
    with trajetoria.abrir() as con:
        eid = _semear_entrega(con)
        b = leituras.base(con, 'entrega', str(eid))
        with banco.transacao(con):
            con.execute("INSERT INTO leitura (alvo_tipo, alvo_id, texto, base_json, base_hash, modelo, criado_em) "
                        "VALUES ('entrega', ?, 'Entrega focada no domínio.', ?, ?, 'gemini/teste', '2026-11-11T09:00:00')",
                        (str(eid), json.dumps(b), leituras.hash_base(b)))
    v = visivel(rodar(monkeypatch, 'entrega', str(eid)))
    linha = next(l for l in v.splitlines() if 'Entrega focada no domínio.' in l)
    assert 'base: 2 commits, 4 arquivos, 90 linhas, 1 prisma' in linha, linha
    assert '— Análise da Luzia, 11 nov' in linha and 'gemini/teste' in linha, linha
    v = visivel(rodar(monkeypatch, 'entregas'))  # a lista: uma linha por entrega, a análise só no detalhe
    assert f'**#{eid} Separa agregado de agendamento** · ' in v and 'Entrega focada no domínio.' not in v
    v = visivel(rodar(monkeypatch, 'trajetoria'))  # prisma sem análise: diz por quê, nunca fica vazio
    assert 'Sem análise: falta configurar o modelo' in v


# ------------------------------------------------------------------ entregas: sem atalho para as tarefas da IA (A2)
def test_sem_entrega_git_mostra_diagnostico_e_nunca_tarefas_da_ia(privado, monkeypatch):
    monkeypatch.setattr(pipeline, 'run_plan', lambda *a, **k: (_ for _ in ()).throw(AssertionError('sem modelo aqui')))
    for argv in (('entregas',), ('feedback-progress',), ('feedback-progress', '--rotulo', 'feedback-progress')):
        s = rodar(monkeypatch, *argv)
        v = visivel(s)
        assert 'Nenhuma entrega encontrada' in v, v
        assert 'cadastro de exemplo' not in v and 'cobertura do relatório' not in v  # tarefas_recentes (IA) fora
        assert 'Repositório:**' in v and 'não consegui ler o histórico git' in v
        assert 'E-mails do git:** Pessoa Teste' in v and 'Janela:** ainda não lida' in v
        rodar_bts = [b['rodar'] for b in botoes_de(s)]
        assert 'entregas --ampliar 180' in rodar_bts and 'identidade' in rodar_bts, rodar_bts


def test_identidade_confere_e_acrescenta_mostrando_o_email_para_a_dona(privado, monkeypatch):
    s = rodar(monkeypatch, 'identidade')
    assert 'Pessoa Teste' in visivel(s) and tem_rodape_botoes(s)
    s = rodar(monkeypatch, 'identidade', 'adicionar', 'pessoa.segunda@exemplo.test')
    v = visivel(s)
    assert 'pessoa.segunda@exemplo.test' in v and '***' not in v
    assert tem_rodape_botoes(s) and any(b['rodar'] == 'entregas' for b in botoes_de(s))
    with trajetoria.abrir() as con:
        assert 'pessoa.segunda@exemplo.test' in entregas.identidades(con)


# ------------------------------------------------------------------ avanços ligados a uma entrega: P3/P4 (A3)
def _acao_entrega(titulo, skill, dimensao):
    return {'titulo': titulo, 'tipo': 'explicar', 'skill': skill, 'dimensao': dimensao, 'por_que': 'Dono da decisão.',
            'conceitos': ['agregado'], 'como': ['Abra a entrega.', 'Explique com suas palavras.'],
            'onde_explorar': 'Os arquivos de domínio da entrega.', 'prompt': 'Me pergunte uma coisa por vez.',
            'duracao_min': 15}


def _modelo_entrega(monkeypatch, chamadas):
    def fake(payload, schema=None, **kw):
        chamadas.append({'payload': payload, 'schema': schema})
        acoes_ = [_acao_entrega('Explicar o agregado desta entrega', 'Prisma inventado', None),
                  _acao_entrega('Defender a separação do agregado', DDD, 'P3')]
        reg = {'quando': '2026-11-12T15:00:00', 'modelo': 'gemini/teste', 'tempo_total_s': 0.1, 'pico_memoria_mib': 1,
               'tokens_entrada': 1, 'tokens_saida': 1, 'versao': 't'}
        return SimpleNamespace(plan={'acoes': acoes_}, model='gemini/teste'), reg

    monkeypatch.setattr(pipeline, 'run_plan', fake)


def test_acender_entrega_liga_avancos_e_acende_p3(privado, monkeypatch):
    from luzia import planner
    chamadas = []
    _modelo_entrega(monkeypatch, chamadas)
    with trajetoria.abrir() as con:
        eid = _semear_entrega(con)
    s = rodar(monkeypatch, 'entrega', str(eid))
    assert f'acender-entrega {eid}' in [b['rodar'] for b in botoes_de(s)]

    s = rodar(monkeypatch, 'acender-entrega', str(eid))
    assert tem_rodape_botoes(s) and len(chamadas) == 1 and chamadas[0]['schema'] == planner.ENTREGA_SCHEMA
    enviado = chamadas[0]['payload']
    assert set(enviado) == {'entrega'} and set(enviado['entrega']) == {'titulo', 'periodo', 'fatos', 'prismas'}
    assert enviado['entrega']['prismas'] == [{'prisma': DDD, 'termos': ['aggregate', 'domain']}]
    with trajetoria.abrir() as con:
        ligados = [a for a in jogo.avancos(con) if a.get('entrega_id') == eid]
    assert sorted(a['dimensao'] for a in ligados) == ['P3', 'P4']
    assert {a['skill_plano'] for a in ligados} == {DDD} and {a['origem'] for a in ligados} == {'entrega'}
    assert all(a['estado'] == 'sugerido' and 10 <= a['valor_lm'] <= 100 for a in ligados)
    p3 = next(a for a in ligados if a['dimensao'] == 'P3')
    assert p3['titulo'] == 'Explicar o agregado desta entrega'  # a primeira é sempre a P3

    s = rodar(monkeypatch, 'acender-entrega', str(eid))  # já há P3 e P4 abertos: não chama o modelo de novo
    assert 'já tem centelhas P3 e P4 abertas' in visivel(s) and len(chamadas) == 1 and tem_rodape_botoes(s)

    rodar(monkeypatch, 'fazer', p3['id'])
    s = rodar(monkeypatch, 'registrar', p3['id'], '--nota', '4', '--resumo', 'Explicou as invariantes do agregado')
    assert 'propriedade agora' in visivel(s)
    v = visivel(rodar(monkeypatch, 'entrega', str(eid)))
    assert 'P3 Aplicação de conceito: **100** (evidência)' in v and 'Explicou as invariantes do agregado' in v
    assert 'P4 Decisão de arquitetura: — falta você defender' in v


def test_acender_entrega_sem_modelo_nao_grava_nada(privado, monkeypatch):
    monkeypatch.setattr(pipeline, 'run_plan', lambda *a, **k: (_ for _ in ()).throw(RuntimeError('Falta a chave X')))
    with trajetoria.abrir() as con:
        eid = _semear_entrega(con)
    s = rodar(monkeypatch, 'acender-entrega', str(eid))
    assert 'Falta a chave X' in visivel(s) and tem_rodape_botoes(s)
    with trajetoria.abrir() as con:
        assert not [a for a in jogo.avancos(con) if a.get('entrega_id') == eid]
    s = rodar(monkeypatch, 'acender-entrega', '999')
    assert 'entrega não encontrada' in visivel(s) and tem_rodape_botoes(s)


# ------------------------------------------------------------------ leituras pelo chat (A5)
def _leituras_falsas(monkeypatch, chamadas):
    def fake(payload, schema=None, **kw):
        chamadas.append(payload)
        lt = [{'alvo': a['alvo'], 'texto': f"Leitura de {a['alvo']}."} for a in payload['alvos']]
        return SimpleNamespace(plan={'leituras': lt}, model='gemini/teste'), {'quando': '2026-11-12T10:00:00',
                                                                               'modelo': 'gemini/teste'}
    monkeypatch.setattr(pipeline, 'run_plan', fake)


def test_leituras_pelo_chat(privado, monkeypatch):
    from luzia import leituras, modelo
    monkeypatch.setattr(modelo, 'pronto', lambda: False)
    s = rodar(monkeypatch, 'leituras')
    assert 'sem análise: falta configurar o modelo' in visivel(s) and tem_rodape_botoes(s)
    assert all(b['rodar'] != 'leituras' for b in botoes_de(rodar(monkeypatch, 'hoje')))
    assert '## Luzia · Análises' in visivel(rodar(monkeypatch, 'analises'))  # apelido de `leituras`

    monkeypatch.setattr(modelo, 'pronto', lambda: True)
    with trajetoria.abrir() as con:
        n = len(leituras.vencidas(con))
    assert n == 3  # os 3 prismas do plano, ainda sem leitura
    for cmd in ('hoje', 'trajetoria'):
        bts = botoes_de(rodar(monkeypatch, cmd))
        assert {'rotulo': 'Atualizar 3 análises', 'rodar': 'leituras'}.items() <= next(
            b for b in bts if b['rodar'] == 'leituras').items(), (cmd, bts)

    monkeypatch.setattr(pipeline, 'run_plan', lambda *a, **k: (_ for _ in ()).throw(RuntimeError('sem internet')))
    s = rodar(monkeypatch, 'leituras')
    assert 'nada foi gravado' in visivel(s) and tem_rodape_botoes(s)

    chamadas = []
    _leituras_falsas(monkeypatch, chamadas)
    s = rodar(monkeypatch, 'leituras')
    assert '3 análises atualizadas' in visivel(s) and len(chamadas) == 1  # um lote, uma chamada
    assert 'Todas as análises estão em dia' in visivel(rodar(monkeypatch, 'leituras'))
    v = visivel(rodar(monkeypatch, 'trajetoria'))
    assert f'Leitura de prisma:{DDD}. _— Análise da Luzia, 12 nov · base: ' in v and 'gemini/teste' in v
    assert all(b['rodar'] != 'leituras' for b in botoes_de(rodar(monkeypatch, 'hoje')))


def test_erros_do_motor_ja_nascem_no_vocabulario_novo(privado, monkeypatch):
    """Sem tradução na hora de exibir: o painel (que recebe o texto cru) e o chat mostram as mesmas palavras."""
    plan = pipeline.load_state()['plano']
    jogo.sincronizar(plan)
    fid = next(f['id'] for f in jogo.catalogo(plan))
    mensagens = [
        jogo.conquistar('zzzz', 3, 'x', plan)['erro'],            # avanço inexistente
        jogo.conquistar(fid, 3, 'x', plan)['erro'],               # ainda não iniciado
        *jogo.progresso_skill(DDD)['falta'],
    ]
    for m in mensagens:
        assert RE_TERMOS_ANTIGOS.search(m) is None, m
    assert '1 centelha acesa' in mensagens
    saida = visivel(rodar(monkeypatch, 'registrar', fid, '--nota', '3', '--resumo', 'x'))
    assert RE_TERMOS_ANTIGOS.search(saida) is None and 'centelha' in saida
    assert not hasattr(cli, '_vocab_novo')


def test_trajetoria_compacta_a_falta_e_usa_o_nome_curto(privado, monkeypatch):
    saida = visivel(rodar(monkeypatch, 'trajetoria'))
    assert '(prisma · skill)' not in saida and 'skill)' not in saida
    falta = [l for l in saida.splitlines() if ' · falta ' in l]
    assert falta and all('conquistar 1' not in l and len(l) < 120 for l in falta), falta
    assert any(l.strip().startswith('DDD `') and '1 → 4' in l and '/150 lm · falta ' in l for l in falta), falta


def test_acender_sem_modelo_no_chat_nao_quebra_nem_grava(privado, monkeypatch):
    monkeypatch.setattr(pipeline, 'run_plan', lambda *a, **k: (_ for _ in ()).throw(RuntimeError('sem modelo')))
    jogo.sincronizar(pipeline.load_state()['plano'])
    antes = len(jogo.catalogo(pipeline.load_state()['plano']))
    s = rodar(monkeypatch, 'acender', DDD)
    assert 'não deu para acender' in visivel(s) and tem_rodape_botoes(s)
    assert len(jogo.catalogo(pipeline.load_state()['plano'])) == antes


def test_entrega_no_chat_mostra_titulo_real_e_numero_do_ticket(privado, monkeypatch):
    jogo.sincronizar(pipeline.load_state()['plano'])
    with trajetoria.abrir() as con, banco.transacao(con):
        eid = con.execute(
            "INSERT INTO entrega (chave, titulo, inicio, fim, fonte, commits, arquivos, linhas, areas_json, ids_privados_json) "
            "VALUES ('tk-x', 'Bug 14988: ProdutoZeta corrige mapa', '2026-11-10T10:00:00', '2026-11-11T10:00:00', "
            "'ticket', 1, 1, 5, '[]', '[\"14988\"]')").lastrowid
    monkeypatch.setattr(entregas, 'atualizar', lambda con, dias=90: {'novas': 0, 'atualizadas': 0})
    v = visivel(rodar(monkeypatch, 'entrega', eid))
    assert 'Bug 14988: ProdutoZeta corrige mapa' in v and '#14988' in v
    v = visivel(rodar(monkeypatch, 'entregas'))
    assert 'Bug 14988: ProdutoZeta corrige mapa' in v
