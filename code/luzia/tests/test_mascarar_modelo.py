"""Interruptor `mascarar_modelo`: o que vai ao modelo sai real por padrão e mascarado quando ligado (modelo falso)."""

from __future__ import annotations

import io
import json
import sys
from contextlib import redirect_stdout
from datetime import datetime

import pytest

from luzia import banco, cli, leituras, pipeline, planner, privacy, trajetoria

DDD = 'Domain-Driven Design (DDD)'


@pytest.fixture
def prompts(privado, monkeypatch):
    """Captura o texto exato que iria ao provedor; responde leituras para os alvos pedidos."""
    (privado / 'termos.txt').write_text('# sintético\nProdutoZeta\nClienteAlfa\n', encoding='utf-8')
    enviados: list[str] = []

    def falso(prompt):
        enviados.append(prompt)
        corpo = json.loads(prompt[prompt.index('\n') + 1:prompt.index('\n\n')])
        itens = [{'alvo': a['alvo'], 'texto': f"Leitura de {a['alvo']}."} for a in corpo.get('alvos', [])]
        return planner.LLMResult(plan={'leituras': itens}, raw='{}', seconds=0.1, tokens_in=1, tokens_out=1,
                                 model='falso/modelo')

    monkeypatch.setattr(planner, 'call_llm', falso)
    monkeypatch.setattr(pipeline, 'version', lambda: 'teste')
    return enviados


def _entrega_com_nomes(con) -> int:
    agora = datetime.now().replace(microsecond=0).isoformat(timespec='seconds')
    with banco.transacao(con):
        eid = con.execute(
            "INSERT INTO entrega (chave, titulo, inicio, fim, commits, arquivos, linhas, areas_json, ids_privados_json, fonte) "
            "VALUES ('tk-1', 'Bug 14988: ProdutoZeta para ClienteAlfa #4821', ?, ?, 1, 2, 30, '[]', '[\"14988\"]', 'ticket')",
            (agora, agora)).lastrowid
        con.execute("INSERT INTO entrega_prisma (entrega_id, prisma, termos_json) VALUES (?, ?, '[\"Aggregate\"]')",
                    (eid, DDD))
    return eid


def test_padrao_desligado(privado):
    assert pipeline.mascarar_modelo() is False


def test_leituras_vao_reais_com_o_interruptor_desligado(prompts):
    with trajetoria.abrir() as con:
        eid = _entrega_com_nomes(con)
        assert leituras.gerar(con, [('entrega', str(eid))]) == 1
    assert 'ProdutoZeta' in prompts[-1] and 'ClienteAlfa' in prompts[-1] and '14988' in prompts[-1]


def test_leituras_vao_mascaradas_com_o_interruptor_ligado_e_a_base_na_tela_segue_real(prompts):
    pipeline.definir_mascarar_modelo(True)
    with trajetoria.abrir() as con:
        eid = _entrega_com_nomes(con)
        assert leituras.gerar(con, [('entrega', str(eid)), ('prisma', DDD)]) == 2  # alvos e prismas voltam intactos
        texto = prompts[-1]
        for real in ('ProdutoZeta', 'ClienteAlfa', '14988', '4821'):
            assert real not in texto, real
        assert '[EMPRESA/PRODUTO]' in texto and f'entrega:{eid}' in texto and DDD in texto
        lt = leituras.obter(con, 'entrega', str(eid))
        assert 'ProdutoZeta' in lt['base']['titulo'] and lt['vencida'] is False  # a base guardada é a real


def test_colegas_do_repositorio_mascarados_so_com_o_interruptor(prompts, privado, monkeypatch):
    from luzia import triage
    monkeypatch.setattr(triage, 'repo_authors', lambda repo, excluir=(): ['Pessoa Teste', 'Colega Fulana', 'Fulana'])
    payload = {'skill': {'nome': DDD, 'evidencia': 'Revisou com Colega Fulana o ProdutoZeta.'}}
    pipeline.run_plan(payload, prep_seconds=0, label='t', save_current_state=False, schema='{}', intro='Fatos:')
    assert 'Colega Fulana' in prompts[-1]
    pipeline.definir_mascarar_modelo(True)
    pipeline.run_plan(payload, prep_seconds=0, label='t', save_current_state=False, schema='{}', intro='Fatos:')
    assert 'Fulana' not in prompts[-1] and 'ProdutoZeta' not in prompts[-1]
    assert '[COLEGA]' in prompts[-1] and DDD in prompts[-1]
    assert payload['skill']['evidencia'] == 'Revisou com Colega Fulana o ProdutoZeta.'  # o original não muda


def test_registro_da_chamada_diz_se_mascarou_sem_dado_pessoal(prompts):
    pipeline.definir_mascarar_modelo(True)
    _, rec = pipeline.run_plan({'x': 'ProdutoZeta'}, prep_seconds=0, label='t', save_current_state=False, schema='{}')
    assert rec['mascarar_modelo'] is True and rec['itens_mascarados'] >= 1
    assert 'ProdutoZeta' not in json.dumps(rec, ensure_ascii=False)


def test_triagem_usa_o_redator_so_com_o_interruptor(privado):
    assert cli.make_redactor({}).redact('ProdutoZeta pessoa@exemplo.test') == 'ProdutoZeta pessoa@exemplo.test'
    (privado / 'termos.txt').write_text('ProdutoZeta\n', encoding='utf-8')
    pipeline.definir_mascarar_modelo(True)
    assert cli.make_redactor({}).redact('ProdutoZeta pessoa@exemplo.test') == '[EMPRESA/PRODUTO] [EMAIL]'


def test_mascarar_estrutura_mantem_chaves_de_identificacao():
    r = privacy.Redactor(terms=['ProdutoZeta'])
    entrada = {'alvo': 'entrega:3', 'prisma': 'ProdutoZeta', 'lista': [{'titulo': 'ProdutoZeta #4821'}], 'n': 7,
               'skill': {'nome': 'X', 'evidencia': 'no ProdutoZeta'}}
    saida = privacy.mascarar_estrutura(entrada, r, manter=pipeline.CHAVES_MANTIDAS)
    assert saida['alvo'] == 'entrega:3' and saida['prisma'] == 'ProdutoZeta' and saida['n'] == 7
    assert saida['lista'][0]['titulo'] == '[EMPRESA/PRODUTO] [TICKET]'
    assert saida['skill'] == {'nome': 'X', 'evidencia': 'no [EMPRESA/PRODUTO]'}


def _cli(monkeypatch, *argv):
    monkeypatch.setattr(sys, 'argv', ['luzia', *argv])
    buf = io.StringIO()
    with redirect_stdout(buf):
        cli.main()
    return buf.getvalue()


def test_comando_privacidade_no_chat(privado, monkeypatch):
    s = _cli(monkeypatch, 'privacidade')
    assert 'desligado' in s and 'LUZIA_BOTOES=' in s
    assert any('privacidade mascarar-modelo on' == b['rodar']
               for b in json.loads(next(x for x in s.splitlines() if x.startswith('LUZIA_BOTOES='))[13:]))
    s = _cli(monkeypatch, 'privacidade', 'mascarar-modelo', 'on')
    assert 'ligado' in s and pipeline.mascarar_modelo() is True
    s = _cli(monkeypatch, 'privacidade', 'mascarar-modelo', 'off')
    assert pipeline.mascarar_modelo() is False
    s = _cli(monkeypatch, 'privacidade', 'mascarar-modelo', 'talvez')
    assert pipeline.mascarar_modelo() is False and 'on' in s and 'off' in s


def test_ajuste_no_painel(servidor):
    servidor.entrar()
    c, st, _ = servidor.pedir('GET', '/api/estado')
    assert c == 200 and st['privacidade']['mascarar_modelo'] is False
    c, r, _ = servidor.pedir('POST', '/api/privacidade', {'mascarar_modelo': True})
    assert c == 200 and r['mascarar_modelo'] is True and pipeline.mascarar_modelo() is True
    assert servidor.pedir('GET', '/api/estado')[1]['privacidade']['mascarar_modelo'] is True
    for ruim in ('sim', 1, None):
        assert servidor.pedir('POST', '/api/privacidade', {'mascarar_modelo': ruim})[0] == 400
    assert pipeline.mascarar_modelo() is True
    servidor.cookie = None
    assert servidor.pedir('POST', '/api/privacidade', {'mascarar_modelo': False})[0] == 401
    assert pipeline.mascarar_modelo() is True


def test_aviso_quando_termos_txt_falta_e_alcance_do_interruptor(servidor, privado, monkeypatch):
    servidor.entrar()
    st = servidor.pedir('GET', '/api/estado')[1]
    assert st['privacidade'] == {'mascarar_modelo': False, 'termos': 0}
    s = _cli(monkeypatch, 'privacidade')
    assert 'termos.txt' in s and 'agente do chat' in s
    (privado / 'termos.txt').write_text('# comentário\nProdutoZeta\nClienteAlfa\n', encoding='utf-8')
    assert servidor.pedir('GET', '/api/estado')[1]['privacidade']['termos'] == 2
    s = _cli(monkeypatch, 'privacidade')
    assert 'sem termos' not in s.lower() and 'agente do chat' in s
    from luzia import server
    from pathlib import Path
    js = (Path(server.PAINEL) / 'luzia.js').read_text(encoding='utf-8')
    assert 'E.privacidade?.termos' in js and 'termos.txt' in js and 'Seu agente vê os dados reais' in js


# ------------------------------------------------------------------ nomes reais fora do código versionado
def test_codigo_versionado_sem_nomes_reais_da_dona():
    import re
    from pathlib import Path
    raiz = Path(cli.__file__).resolve().parent
    proibidos = re.compile(r'rayane|cerebro_|rayfrance|\b(?:tasy|jev|brevo)\b', re.IGNORECASE)
    achados = [f'{p.name}:{n}' for p in raiz.glob('*.py')
               for n, linha in enumerate(p.read_text(encoding='utf-8').splitlines(), 1) if proibidos.search(linha)]
    assert not achados, achados


def test_colegas_do_git_sem_a_propria_pessoa_nem_partes_do_nome_dela(privado, monkeypatch):
    from luzia import triage
    import subprocess as sp
    saida = 'Pessoa Teste\nColega Fulana\nOutra Teste\nPESSOA TESTE\n'
    monkeypatch.setattr(sp, 'run', lambda *a, **k: type('R', (), {'stdout': saida})())
    nomes = triage.repo_authors(privado, excluir=['Pessoa Teste', 'pessoa@exemplo.test'])
    assert 'Pessoa Teste' not in nomes and 'PESSOA TESTE' not in nomes
    assert {'Colega Fulana', 'Fulana', 'Colega', 'Outra Teste', 'Outra'} <= set(nomes)
    assert 'Teste' not in nomes and 'Pessoa' not in nomes  # parte do nome dela nunca vira [COLEGA]


def test_redator_da_triagem_nao_mascara_a_propria_pessoa(privado, monkeypatch):
    from luzia import triage
    monkeypatch.setattr(triage, 'repo_authors',
                        lambda repo, excluir=(): [n for n in ('Pessoa Teste', 'Colega Fulana', 'Fulana')
                                                  if n not in excluir])
    pipeline.definir_mascarar_modelo(True)
    r = cli.make_redactor(json.loads((privado / 'entrada.json').read_text(encoding='utf-8')))
    assert r.redact('Pessoa Teste revisou com Colega Fulana') == 'Pessoa Teste revisou com [COLEGA]'
    assert privacy.Redactor.from_file(None, extra_colleagues=['Brevo Silva']).colleagues == ['Brevo Silva']


def test_triagem_mascarada_uma_vez_so(privado, monkeypatch, prompts):
    from luzia import triage
    (privado / 'entrada.json').write_text(json.dumps({'author': 'Pessoa Teste', 'incluir_historico_ia': False,
                                                      'objetivo': 'Plena no ProdutoZeta'}), encoding='utf-8')
    monkeypatch.setattr(triage, 'my_commits', lambda *a, **k: [])
    chamadas = []
    original = privacy.mascarar_estrutura
    monkeypatch.setattr(pipeline, 'mascarar_estrutura', lambda *a, **k: chamadas.append(1) or original(*a, **k))
    monkeypatch.setattr(pipeline, 'save_state', lambda *a, **k: None)
    pipeline.definir_mascarar_modelo(True)
    _, rec, _ = cli.execute_triage(privado / 'entrada.json')
    assert 'ProdutoZeta' not in prompts[-1] and '[EMPRESA/PRODUTO]' in prompts[-1]
    assert chamadas == [] and rec['mascarar_modelo'] is True  # o payload da triagem já sai mascarado do build_payload
