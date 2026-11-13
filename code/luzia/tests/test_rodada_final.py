"""Rodada final: avanços da triagem sem título de entrega, modelo da triagem, dias inválidos e acabamentos."""

import io
import sys
from contextlib import redirect_stdout
from pathlib import Path

from luzia import banco, cli, jogo, modelo, pipeline, server

DDD = 'Domain-Driven Design (DDD)'


def _rodar(monkeypatch, *argv):
    monkeypatch.setattr(sys, 'argv', ['luzia', *argv])
    buf = io.StringIO()
    with redirect_stdout(buf):
        cli.main()
    return buf.getvalue()


def _plano_com_acao_legada(privado):
    plan = pipeline.load_state()['plano']
    plan['tarefas_recentes'][0]['acoes'] = [{
        'titulo': 'Revisar o agregado da tarefa', 'tipo': 'praticar', 'skill': DDD, 'dimensao': 'P3', 'por_que': 'x',
        'conceitos': ['agregado'], 'como': ['a', 'b'], 'onde_explorar': 'o', 'prompt': 'p', 'duracao_min': 10}]
    return plan


def test_avanco_legado_da_triagem_nunca_mostra_titulo_de_entrega_da_ia(privado, monkeypatch):
    plan = _plano_com_acao_legada(privado)
    cat = jogo.sincronizar(plan)
    f = next(x for x in cat.values() if x['titulo'] == 'Revisar o agregado da tarefa')
    assert f['da_triagem'] is True and 'entrega' not in f
    saida = _rodar(monkeypatch, 'fazer', f['id'])
    assert '▸ da triagem' in saida and 'cadastro de exemplo' not in saida and '▸ entrega' not in saida
    lista = jogo.catalogo(plan)
    assert all('cadastro de exemplo' not in str(x.get('entrega', '')) for x in lista)


def test_estado_traz_modelo_e_data_da_triagem(privado):
    con = banco.conectar()
    try:
        with banco.transacao(con):
            con.execute("INSERT INTO chamada_modelo (quando, rotulo, modelo, segundos, tokens_in, tokens_out, registro_json) "
                        "VALUES ('2026-11-01T10:00:00', 'cmd-triage', 'gemini/x', 1, 1, 1, '{}')")
            con.execute("INSERT INTO chamada_modelo (quando, rotulo, modelo, segundos, tokens_in, tokens_out, registro_json) "
                        "VALUES ('2026-11-05T10:00:00', 'cmd-leituras', 'outro/y', 1, 1, 1, '{}')")
    finally:
        con.close()
    # registro sem a marca = versão antiga, que sempre mascarava o envio
    assert server.estado()['triagem_modelo'] == {'modelo': 'gemini/x', 'quando': '2026-11-01T10:00:00', 'mascarado': True}


def test_rotulo_da_base_da_triagem_segue_o_que_foi_enviado(privado):
    con = banco.conectar()
    try:
        with banco.transacao(con):
            con.execute("INSERT INTO chamada_modelo (quando, rotulo, modelo, segundos, tokens_in, tokens_out, registro_json) "
                        "VALUES ('2026-11-13T10:00:00', 'cmd-triage', 'gemini/x', 1, 1, 1, '{\"mascarar_modelo\": false}')")
    finally:
        con.close()
    assert server.estado()['triagem_modelo']['mascarado'] is False
    assert 'anonimizados' not in cli.base_triagem(False) and 'mascarad' not in cli.base_triagem(False)
    assert 'mascarados' in cli.base_triagem(True)
    js = (Path(server.PAINEL) / 'luzia.js').read_text(encoding='utf-8')
    assert '(anonimizados)' not in js and 'E.triagem_modelo?.mascarado' in js


def test_estado_sem_registro_da_triagem_nao_inventa_modelo(privado):
    assert server.estado()['triagem_modelo'] is None


def test_mensagens_sem_ponto_duplicado_e_p1_sem_traco_solto(privado, monkeypatch):
    e = RuntimeError('x')
    assert not modelo.resumo_erro(RuntimeError('Falta a chave GEMINI_API_KEY: configure em Ajustes.')).endswith('.')
    pipeline_erro = RuntimeError(f"Falta a chave {modelo.PROVEDORES['gemini']['chave']}: configure em Ajustes > Modelo da Luzia")
    assert '..' not in f'Não deu ({modelo.resumo_erro(pipeline_erro)}).'
    linhas = cli.linhas_propriedade({'indice': 60, 'base': '1 de 4 dimensões',
                                     'dimensoes': {'P1': {'nota': 60, 'tipo': 'medida', 'base': ''}}})
    p1 = next(l for l in linhas if 'P1' in l)
    assert not p1.rstrip().endswith('—') and '— ' not in p1.split('(medida)')[-1]
