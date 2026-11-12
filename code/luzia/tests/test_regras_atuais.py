"""Regras atuais do jogo, da CLI e do instalador (rede de segurança para a troca de JSON por SQLite).

Antes eram os roteiros avulsos teste_lote1.py (22 verificações) e teste_lote23.py (17), que copiavam a pasta
privada real. Agora cada teste roda na fixture `privado`, com dados sintéticos.
"""

import io
import json
import sys
import time
from contextlib import redirect_stdout
from types import SimpleNamespace

import pytest

from luzia import acoes, arquivos, banco, cli, instalar, jogo, observer, pipeline

DDD = 'Domain-Driven Design (DDD)'
TESTES = 'Testes e Qualidade / SQL'


@pytest.fixture
def plan(privado):
    return pipeline.load_state()['plano']


@pytest.fixture
def sugeridos(plan):
    cat = jogo.sincronizar(plan)
    return [k for k, f in cat.items() if f['estado'] == 'sugerido']


def _conquistado_nota_3(plan, fid):
    jogo.iniciar(fid, 'teste')
    return jogo.conquistar(fid, 3, 't', plan)


def _revisitado(plan, fid):
    _conquistado_nota_3(plan, fid)
    jogo.enfileirar(fid)
    jogo.iniciar(fid, 'revisita')
    return jogo.conquistar(fid, 4, 't', plan)


def _linhas(sql):
    con = banco.conectar()
    try:
        return con.execute(sql).fetchall()
    finally:
        con.close()


def _feixes():
    con = banco.conectar()
    try:
        return {f['id']: f for f in jogo.avancos(con)}
    finally:
        con.close()


# ------------------------------------------------------------------ lote 1 · revisita paga só uma vez
def test_registrar_sem_iniciar_e_recusado(plan, sugeridos):
    assert jogo.conquistar(sugeridos[0], 4, 't', plan).get('erro', '').startswith('este avanço ainda não foi iniciado')


def test_nota_3_rende_75_por_cento(plan, sugeridos):
    f1 = sugeridos[0]
    v = _feixes()[f1]['valor_lm']
    assert _conquistado_nota_3(plan, f1)['ganho'] == round(v * 0.75)


def test_enviar_para_revisita_mantem_conquistado(plan, sugeridos):
    f1 = sugeridos[0]
    _conquistado_nota_3(plan, f1)
    assert jogo.enfileirar(f1)
    assert _feixes()[f1]['estado'] == 'conquistado'


def test_revisita_sem_abrir_e_recusada(plan, sugeridos):
    f1 = sugeridos[0]
    _conquistado_nota_3(plan, f1)
    jogo.enfileirar(f1)
    assert 'abra a revisita' in jogo.conquistar(f1, 4, 't', plan).get('erro', '')


def test_revisita_paga_so_a_diferenca(plan, sugeridos):
    f1 = sugeridos[0]
    v = _feixes()[f1]['valor_lm']
    r = _revisitado(plan, f1)
    assert r['ganho'] == v - round(v * 0.75)
    assert r['feixe']['lm_ganho'] == v


def test_depois_da_revisita_nao_volta_para_a_fila_nem_reabre(plan, sugeridos):
    f1 = sugeridos[0]
    _revisitado(plan, f1)
    assert jogo.enfileirar(f1) is None
    assert jogo.iniciar(f1) is None


def test_terceiro_registro_e_recusado(plan, sugeridos):
    f1 = sugeridos[0]
    _revisitado(plan, f1)
    assert 'já foi revisitado' in jogo.conquistar(f1, 4, 't', plan).get('erro', '')


def test_livro_de_lumens_soma_o_valor_do_feixe(plan, sugeridos):
    f1 = sugeridos[0]
    v = _feixes()[f1]['valor_lm']
    _revisitado(plan, f1)
    jogo.conquistar(f1, 4, 't', plan)  # terceiro registro, recusado
    assert sum(x['lm'] for x in jogo.livro() if x['ref'] == f1) == v


# ------------------------------------------------------------------ lote 1 · tente de novo
def test_nota_1_tente_de_novo_mantem_em_andamento(plan, sugeridos):
    f2 = sugeridos[1]
    jogo.iniciar(f2)
    r = jogo.conquistar(f2, 1, 't', plan)
    assert r.get('tente_de_novo')
    assert _feixes()[f2]['estado'] == 'em_andamento'


def test_segunda_tentativa_na_mesma_sessao_e_aceita(plan, sugeridos):
    f2 = sugeridos[1]
    jogo.iniciar(f2)
    jogo.conquistar(f2, 1, 't', plan)
    assert jogo.conquistar(f2, 4, 't', plan)['ganho'] > 0


def test_feixe_com_lumens_e_estado_perdido_nao_paga_de_novo(plan, sugeridos):
    f3 = sugeridos[2]
    con = banco.conectar()
    with banco.transacao(con):
        con.execute("UPDATE avanco SET estado = 'em_andamento', lm_ganho = 20, nota = 4 WHERE id = ?", (f3,))
    con.close()
    assert 'erro' in jogo.conquistar(f3, 4, 't', plan)


# ------------------------------------------------------------------ lote 1 · cartão converte uma vez
def test_converter_sem_cartao_e_recusado(plan):
    assert 'erro' in jogo.converter(plan['skills'][0]['nome'], 4)


def test_cartao_aberto_converte_30_lm(plan):
    skill = plan['skills'][0]['nome']
    jogo.abrir_cartao(skill, 'abc')
    assert jogo.converter(skill, 4).get('lm') == 30


def test_segunda_conversao_do_mesmo_cartao_e_recusada(plan):
    skill = plan['skills'][0]['nome']
    jogo.abrir_cartao(skill, 'abc')
    jogo.converter(skill, 4)
    assert 'erro' in jogo.converter(skill, 4)


# ------------------------------------------------------------------ lote 1 · degrau exige um feixe
def _passivos_160(skill):
    for _ in range(8):
        jogo.lancar(skill, 20, 'propria', 'passivo-prompt', 'x')


def test_160_lm_so_passivos_nao_sobem_degrau(plan):
    sk2 = plan['skills'][1]['nome']
    _passivos_160(sk2)
    p = jogo.progresso_skill(sk2)
    assert not p['pronto']
    assert '1 avanço conquistado' in p['falta']


def test_com_um_feixe_conquistado_o_degrau_fica_pronto(plan):
    sk2 = plan['skills'][1]['nome']
    _passivos_160(sk2)
    jogo.lancar(sk2, 30, 'propria', 'feixe', 'zzzz')
    assert jogo.progresso_skill(sk2)['pronto']


# ------------------------------------------------------------------ lote 1 · arquivos
def test_catalogo_sem_mudanca_nao_e_regravado(plan, sugeridos):
    espiao = banco.conectar()  # data_version muda quando outra conexão confirma uma gravação
    antes = espiao.execute('PRAGMA data_version').fetchone()[0]
    jogo.catalogo(plan)
    assert espiao.execute('PRAGMA data_version').fetchone()[0] == antes
    espiao.close()


def _corromper(privado):
    """Um JSON de configuração quebrado (o jogo em si já não usa JSON: a leitura segura é a de `arquivos`)."""
    caminho = privado / 'config-teste.json'
    caminho.write_text('{"quebrado":', encoding='utf-8')
    return caminho


def test_json_corrompido_devolve_o_padrao(privado, sugeridos):
    assert arquivos.ler_json(_corromper(privado), {}) == {}


def test_uma_unica_copia_do_arquivo_ruim(privado, sugeridos):
    caminho = _corromper(privado)
    arquivos.ler_json(caminho, {})
    arquivos.ler_json(caminho, {})
    assert len(list(privado.glob('config-teste.json.corrompido-*'))) == 1


def test_erro_registrado_so_com_o_tipo(privado, sugeridos):
    arquivos.ler_json(_corromper(privado), {})
    log = (privado / 'erros.log').read_text(encoding='utf-8')
    assert 'JSONDecodeError' in log
    assert 'quebrado' not in log


def test_gravacoes_nao_deixam_temporario(privado, plan, sugeridos):
    _conquistado_nota_3(plan, sugeridos[0])
    jogo.abrir_cartao(DDD, 's')
    acoes.enfileirar(sugeridos[1], 't')
    assert not list(privado.glob('.*.tmp'))


# ------------------------------------------------------------------ lote 1 · observador
def test_hook_mostra_o_cartao_e_o_abre(privado, plan, capsys):
    cfg = json.loads((privado / 'observer.json').read_text(encoding='utf-8'))
    lac = observer.lacunas(plan)
    _, info = next(iter(lac.items()))
    evento = {'session_id': 's-teste', 'tool_name': 'Write', 'cwd': cfg['autorizados'][0],
              'tool_input': {'file_path': 'x.cs', 'content': ' '.join(info['palavras'][:3])}}
    observer.ao_usar_ferramenta(evento, cfg)
    abertos = [r for r in _linhas('SELECT * FROM lampejo') if r['estado'] == 'aberto']
    assert 'luz refletida' in capsys.readouterr().out
    assert abertos


# ------------------------------------------------------------------ lote 2 · CLI termina em botões
def rodar(monkeypatch, *argv):
    monkeypatch.setattr(sys, 'argv', ['luzia', *argv])
    buf = io.StringIO()
    with redirect_stdout(buf):
        cli.main()
    return buf.getvalue()


def botoes_de(saida):
    linha = next((x for x in saida.splitlines() if x.startswith('LUZIA_BOTOES=')), None)
    return json.loads(linha.split('=', 1)[1]) if linha else []


def test_rotulos_da_rota_vem_da_declaracao(privado):
    assert pipeline.rotulos(pipeline.load_state()) == ('Júnior 3', 'Plena')


def test_hoje_oferece_botoes_com_cli_e_pergunta(privado, monkeypatch):
    s = rodar(monkeypatch, 'hoje')
    assert 'LUZIA_CLI=' in s and 'LUZIA_PERGUNTA=' in s
    assert 1 <= len(botoes_de(s)) <= 3


def test_hoje_primeiro_botao_continua_o_feixe_em_andamento(sugeridos, monkeypatch):
    jogo.iniciar(sugeridos[1], 'aqui')
    b = botoes_de(rodar(monkeypatch, 'hoje'))
    assert b[0]['rodar'] == f'fazer {sugeridos[1]}'
    assert 'Continuar' in b[0]['rotulo']


def test_hoje_sem_comando_cru_na_parte_visivel(sugeridos, monkeypatch):
    jogo.iniciar(sugeridos[0], 'aqui')
    s = rodar(monkeypatch, 'hoje')
    assert 'python -m luzia.cli subir' not in s
    assert 'cd /c/' not in s


def test_degrau_pronto_vira_o_primeiro_botao(plan, monkeypatch):
    sk = plan['skills'][0]['nome']
    jogo.lancar(sk, 160, 'propria', 'feixe', 'teste')
    assert botoes_de(rodar(monkeypatch, 'hoje'))[0]['rodar'] == f'subir "{sk}"'


def test_depois_de_subir_o_primeiro_botao_acende_o_proximo_trecho(plan, monkeypatch):
    sk = plan['skills'][0]['nome']
    jogo.lancar(sk, 160, 'propria', 'feixe', 'teste')
    s = rodar(monkeypatch, 'subir', sk)
    assert 'subiu para o nível' in s
    assert botoes_de(s)[0]['rodar'] == f'trecho "{sk}"'


# ------------------------------------------------------------------ lote 2 · trecho (modelo simulado)
@pytest.fixture
def modelo_falso(privado, monkeypatch):
    fake = {'acoes': [{'titulo': f'Feixe novo {i}', 'tipo': 'praticar', 'skill': 'qualquer', 'por_que': 'p',
                       'conceitos': ['c'], 'como': ['a', 'b'], 'onde_explorar': 'o', 'prompt': 'x', 'duracao_min': 15}
                      for i in range(3)]}
    registro = {'quando': jogo.agora(), 'tempo_total_s': 1, 'pico_memoria_mib': 1, 'tokens_entrada': 1,
                'tokens_saida': 1, 'versao': 't', 'modelo': 'fake'}
    monkeypatch.setattr(pipeline, 'run_plan', lambda payload, **kw: (SimpleNamespace(plan=fake), registro))


def test_trecho_cria_3_feixes_da_skill_certa(modelo_falso):
    res = cli.gerar_trecho(DDD)
    assert len(res['feixes']) == 3
    assert all(f['skill_plano'] == DDD and f['origem'] == 'trecho' for f in res['feixes'])


def test_trecho_fica_salvo_no_estado_privado(modelo_falso):
    cli.gerar_trecho(DDD)
    assert len(pipeline.load_state()['plano'].get('trechos', [])) == 1


def test_comando_trecho_oferece_os_feixes_novos_em_botoes(modelo_falso, monkeypatch):
    b = botoes_de(rodar(monkeypatch, 'trecho', DDD))
    assert len(b) == 3
    assert all(x['rodar'].startswith('fazer ') for x in b)


# ------------------------------------------------------------------ lote 2 · registrar e descartar
def test_registrar_nota_3_oferece_revisitar_agora(plan, monkeypatch):
    f = next(x for x in acoes.todas(plan) if x['estado'] == 'sugerido')
    rodar(monkeypatch, 'fazer', f['id'])
    s = rodar(monkeypatch, 'registrar', f['id'], '--nota', '3', '--resumo', 'teste')
    assert 'Avanço conquistado' in s
    assert any(x['rotulo'] == 'Revisitar agora' for x in botoes_de(s))


def test_descartar_oferece_desfazer(plan, monkeypatch):
    g = next(x for x in acoes.todas(plan) if x['estado'] == 'sugerido')
    b = botoes_de(rodar(monkeypatch, 'descartar', g['id'], '--motivo', 'agora_nao'))
    assert b and b[0]['rodar'] == f"restaurar {g['id']}"


# ------------------------------------------------------------------ lote 3 · instalador num HOME falso
@pytest.fixture
def casa(privado, tmp_path, monkeypatch):
    claude = tmp_path / 'casa' / '.claude'
    monkeypatch.setattr(instalar, 'CLAUDE', claude)
    monkeypatch.setattr(instalar, 'SETTINGS', claude / 'settings.json')
    claude.mkdir(parents=True)
    instalar.SETTINGS.write_text(json.dumps({'statusLine': {'type': 'command', 'command': 'outra.sh'}, 'model': 'x'}),
                                 encoding='utf-8')
    return claude


def test_comandos_instalados_com_o_caminho_resolvido(casa):
    instalar.comandos()
    hoje_md = (casa / 'commands' / 'luzia' / 'hoje.md').read_text(encoding='utf-8')
    assert '${CLAUDE_PLUGIN_ROOT}' not in hoje_md
    assert 'code/luzia/..' in hoje_md


def test_hooks_registrados_uma_vez_so(casa):
    assert instalar.hooks() == ['SessionStart', 'UserPromptSubmit', 'PostToolUse']
    assert instalar.hooks() == []


def test_nao_troca_uma_linha_de_status_que_ja_existe(casa):
    assert 'outra' in instalar.statusline()


def test_demais_configuracoes_preservadas(casa):
    instalar.hooks()
    instalar.statusline()
    d = json.loads(instalar.SETTINGS.read_text(encoding='utf-8'))
    assert d['model'] == 'x'
    assert d['statusLine']['command'] == 'outra.sh'


def test_backup_do_settings_feito(casa):
    instalar.hooks()
    assert len(list(casa.glob('settings.json.antes-luzia-*'))) >= 1


def test_regras_para_outros_agentes_com_o_caminho_certo(privado):
    regras = instalar.regras()
    assert '<LUZIA_CLI>' not in regras
    assert 'python -m luzia.cli' in regras
