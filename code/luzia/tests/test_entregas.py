"""Entregas detectadas no git (Tarefa 8): repositório descartável no tmp_path, nomes inventados."""

import json
import os
import subprocess
from datetime import datetime, timedelta

import pytest

from luzia import banco, entregas, trajetoria

EU = 'Pessoa Teste'
EU_MAIL = 'pessoa@exemplo.test'
OUTRA = 'Colega Fulana'
OUTRA_MAIL = 'fulana@exemplo.test'
DDD = 'Domain-Driven Design (DDD)'
TESTES = 'Testes e Qualidade / SQL'
FRONT = 'Front-end (JS / Razor / React)'


@pytest.fixture
def con(privado):
    (privado / 'termos.txt').write_text('# sintético\nProdutoZeta\n', encoding='utf-8')
    c = banco.conectar()
    yield c
    c.close()


class Repo:
    def __init__(self, pasta):
        self.pasta = pasta
        self.n = 0
        self.git('init', '-q', '-b', 'main')

    def git(self, *args, nome=EU, mail=EU_MAIL, quando=None):
        env = {'GIT_AUTHOR_NAME': nome, 'GIT_AUTHOR_EMAIL': mail, 'GIT_COMMITTER_NAME': nome,
               'GIT_COMMITTER_EMAIL': mail, 'PATH': os.environ['PATH'],
               'SYSTEMROOT': os.environ.get('SYSTEMROOT', ''), 'HOME': str(self.pasta)}
        if quando:
            env['GIT_AUTHOR_DATE'] = env['GIT_COMMITTER_DATE'] = quando.isoformat(timespec='seconds')
        r = subprocess.run(['git', '-C', str(self.pasta), '-c', 'commit.gpgsign=false', *args], env=env,
                           capture_output=True, text=True, encoding='utf-8', check=True)
        return r.stdout.strip()

    def commit(self, msg, arq, nome=EU, mail=EU_MAIL, quando=None, linhas=3):
        self.n += 1
        alvo = self.pasta / arq
        alvo.parent.mkdir(parents=True, exist_ok=True)
        with alvo.open('a', encoding='utf-8') as f:
            f.write(''.join(f'linha {self.n} {i}\n' for i in range(linhas)))
        self.git('add', '-A')
        self.git('commit', '-q', '-m', msg, nome=nome, mail=mail, quando=quando)
        return self.git('rev-parse', 'HEAD')


@pytest.fixture
def repo(privado):
    r = Repo(privado.parent / 'repo')
    r.commit('chore: inicio', 'README.md', quando=_dias(30))
    return r


def _dias(n):
    return datetime.now() - timedelta(days=n)


def _desde(dias=90):
    return _dias(dias).date().isoformat()


def _entrada(privado, repo):
    (privado / 'entrada.json').write_text(json.dumps({'repo': str(repo.pasta), 'author': EU}), encoding='utf-8')


def test_merge_pr_agrupa_so_minha_autoria(repo):
    repo.git('checkout', '-q', '-b', 'feat')
    h1 = repo.commit('feat: agregado pedido', 'src/Pedido.cs', quando=_dias(10))
    h2 = repo.commit('feat: colega mexe', 'src/Outro.cs', nome=OUTRA, mail=OUTRA_MAIL, quando=_dias(9))
    h3 = repo.commit('test: cobre agregado', 'tests/PedidoTests.cs', quando=_dias(8))
    repo.git('checkout', '-q', 'main')
    repo.git('merge', '--no-ff', '-m', 'Merged PR 12: Ajusta agregado', 'feat', nome=OUTRA, mail=OUTRA_MAIL,
             quando=_dias(7))
    repo.commit('fix: avulso', 'src/Avulso.cs', quando=_dias(5))
    res = entregas.detectar(repo.pasta, [EU], _desde())
    pr = [e for e in res if e['fonte'] == 'merge-pr']
    assert len(pr) == 1
    e = pr[0]
    assert {c['hash'] for c in e['commits']} == {h1, h3}  # o commit da colega não entra
    assert h2 not in {c['hash'] for x in res for c in x['commits']}
    assert e['titulo'] == 'Ajusta agregado'
    assert '12' in e['ids_privados']
    avulso = [x for x in res if x['fonte'] == 'commit' and x['commits'][0]['mensagem'].startswith('fix: avulso')]
    assert len(avulso) == 1
    fora = [x for x in res if x['fonte'] != 'merge-pr' for c in x['commits'] if c['hash'] in (h1, h3)]
    assert not fora  # sem duplicar fora do PR


def test_squash_agrupa_por_ticket(repo):
    repo.commit('feat: primeira parte AB#345', 'src/A.cs', quando=_dias(12))
    repo.commit('feat: segunda parte AB#345', 'src/B.cs', quando=_dias(11))
    repo.commit('feat: outra coisa AB#999', 'src/C.cs', quando=_dias(10))
    repo.commit('docs: da colega AB#345', 'docs/x.md', nome=OUTRA, mail=OUTRA_MAIL, quando=_dias(9))
    res = entregas.detectar(repo.pasta, [EU_MAIL], _desde())
    tk = [e for e in res if e['fonte'] == 'ticket']
    dois = [e for e in tk if len(e['commits']) == 2]
    assert len(dois) == 1 and dois[0]['ids_privados'] == ['345']  # só os 2 meus; o da colega fica de fora
    assert all('colega' not in c['mensagem'] for c in dois[0]['commits'])
    assert len([e for e in tk if e['ids_privados'] == ['999']]) == 1


def test_commit_isolado(repo):
    h = repo.commit('feat: coisa solta', 'src/Solta.cs', quando=_dias(3), linhas=5)
    res = entregas.detectar(repo.pasta, [EU], _desde())
    e = [x for x in res if x['commits'][0]['hash'] == h][0]
    assert e['fonte'] == 'commit' and len(e['commits']) == 1
    c = e['commits'][0]
    assert (c['arquivos'], c['linhas'], c['caminhos']) == (1, 5, ['src/Solta.cs'])
    assert 'C#/.NET' in c['areas']
    assert e['inicio'] == e['fim'] == c['data']


def test_prismas_atravessados_com_termos(con, repo, privado):
    repo.commit('feat: monta Aggregate de pedido', 'src/Pedido.cs', quando=_dias(4))
    repo.commit('test: cobre com xunit', 'tests/PedidoTests.cs', quando=_dias(3))
    _entrada(privado, repo)
    assert entregas.atualizar(con)['novas'] == 3
    por = {r['prisma']: json.loads(r['termos_json'])
           for r in con.execute('SELECT prisma, termos_json FROM entrega_prisma')}
    assert [t.lower() for t in por[DDD]] == ['aggregate']
    assert 'xunit' in [t.lower() for t in por[TESTES]]
    assert FRONT not in por


def test_janela_90_dias_e_incremental(con, repo, privado):
    repo.commit('feat: velho', 'src/Velho.cs', quando=_dias(100))
    repo.commit('feat: recente', 'src/Recente.cs', quando=_dias(20))
    _entrada(privado, repo)
    assert entregas.identidades(con) == [EU]
    # 'chore: inicio' (30 dias) e 'recente' entram; 'velho' não
    assert entregas.atualizar(con, dias=90) == {'novas': 2, 'atualizadas': 0}
    assert trajetoria.perfil_ler(con, 'entregas_desde')
    assert entregas.atualizar(con, dias=90) == {'novas': 0, 'atualizadas': 0}
    repo.commit('feat: novo', 'src/Novo.cs', quando=_dias(1))
    assert entregas.atualizar(con, dias=90) == {'novas': 1, 'atualizadas': 0}
    assert entregas.atualizar(con, dias=120)['novas'] == 1  # janela ampliada traz o velho
    assert con.execute('SELECT COUNT(*) FROM entrega').fetchone()[0] == 4
    assert con.execute('SELECT COUNT(*) FROM commit_').fetchone()[0] == 4
    assert entregas.atualizar(con, dias=120) == {'novas': 0, 'atualizadas': 0}


def test_titulo_e_mensagem_reais_com_numeros_e_ids_guardados(con, repo, privado):
    """A dona dos dados vê o título real (empresa, colegas, tickets); os números também ficam em ids_privados."""
    repo.git('checkout', '-q', '-b', 'feat')
    repo.commit('feat: ProdutoZeta integra #12 com Colega Fulana', 'src/Z.cs', quando=_dias(6))
    repo.commit('refactor: ajusta AB#777', 'src/Y.cs', quando=_dias(5))
    repo.git('checkout', '-q', 'main')
    repo.git('merge', '--no-ff', '-m', 'Merged PR 12: ProdutoZeta de Colega Fulana (#12)', 'feat', quando=_dias(4))
    h = repo.commit('fix: ProdutoZeta quebrado #12', 'src/W.cs', quando=_dias(2))
    repo.commit('docs: outra', 'x.md', nome=OUTRA, mail=OUTRA_MAIL, quando=_dias(2))
    _entrada(privado, repo)
    entregas.atualizar(con)
    titulos = [r['titulo'] for r in con.execute('SELECT titulo FROM entrega')]
    assert len(titulos) >= 3
    assert 'ProdutoZeta de Colega Fulana (#12)' in titulos and 'fix: ProdutoZeta quebrado #12' in titulos
    assert all(h[:7] not in t for t in titulos)  # hash nunca vira título
    mensagens = [r['mensagem'] for r in con.execute('SELECT mensagem FROM commit_')]
    assert 'feat: ProdutoZeta integra #12 com Colega Fulana' in mensagens and 'refactor: ajusta AB#777' in mensagens
    ids = [json.loads(r['ids_privados_json']) for r in con.execute('SELECT ids_privados_json FROM entrega')]
    assert any('12' in i for i in ids)
    eid = con.execute("SELECT id FROM entrega WHERE fonte = 'merge-pr'").fetchone()[0]
    det = entregas.detalhe(con, eid, incluir_leitura=False)
    assert det['titulo'] == 'ProdutoZeta de Colega Fulana (#12)' and '12' in det['ids']
    assert any('#12' in c['mensagem'] for c in det['commits'])
    assert all(h not in json.dumps(det, ensure_ascii=False) for h in [h, h[:7]])  # hashes ficam só no banco


def test_commits_soltos_depois_mergeados_nao_duplicam(con, repo, privado):
    repo.git('checkout', '-q', '-b', 'feat')
    repo.commit('feat: parte um', 'src/A.cs', quando=_dias(6))
    repo.commit('feat: parte dois', 'src/B.cs', quando=_dias(5))
    repo.git('checkout', '-q', 'main')
    repo.git('merge', '-q', '--ff-only', 'feat')  # já na principal, ainda sem PR: viram entregas soltas
    _entrada(privado, repo)
    assert entregas.atualizar(con) == {'novas': 3, 'atualizadas': 0}  # 'inicio' + 2 soltas
    repo.git('reset', '-q', '--hard', 'HEAD~2')
    repo.git('merge', '--no-ff', '-m', 'Merged PR 7: Parte um e dois', 'feat', quando=_dias(1))
    res = entregas.atualizar(con)
    assert res['novas'] == 1
    assert con.execute('SELECT COUNT(*) FROM entrega').fetchone()[0] == 2  # 'inicio' + o PR
    assert con.execute("SELECT COUNT(*) FROM entrega WHERE fonte = 'merge-pr'").fetchone()[0] == 1
    assert con.execute('SELECT COUNT(*) FROM entrega e WHERE NOT EXISTS '
                       '(SELECT 1 FROM commit_ c WHERE c.entrega_id = e.id)').fetchone()[0] == 0
    assert con.execute('SELECT commits FROM entrega WHERE fonte = ?', ('merge-pr',)).fetchone()[0] == 2


def test_ramo_nao_integrado_nao_vira_entrega(repo):
    repo.git('checkout', '-q', '-b', 'abandonado')
    h = repo.commit('feat: meia obra', 'src/Meia.cs', quando=_dias(3))
    repo.git('checkout', '-q', 'main')
    res = entregas.detectar(repo.pasta, [EU], _desde())
    assert h not in {c['hash'] for e in res for c in e['commits']}


def test_repo_invalido_devolve_zeros_com_aviso(con, privado, tmp_path):
    vazio = tmp_path / 'nao-git'
    vazio.mkdir()
    (privado / 'entrada.json').write_text(json.dumps({'repo': str(vazio), 'author': EU}), encoding='utf-8')
    res = entregas.atualizar(con)
    assert res['novas'] == 0 and res['atualizadas'] == 0 and res['aviso']
    assert con.execute('SELECT COUNT(*) FROM entrega').fetchone()[0] == 0


def test_ticket_nao_confunde_csharp_e_lock_nao_conta_termo(repo):
    repo.commit('feat: usa C#5 e AB#42', 'package-lock.json', quando=_dias(2))
    e = [x for x in entregas.detectar(repo.pasta, [EU], _desde()) if x['fonte'] == 'ticket']
    assert len(e) == 1 and e[0]['ids_privados'] == ['42']
    assert entregas.prismas_de({'commits': [{'mensagem': 'x', 'caminhos': ['node_modules/aggregate/a.js']}]},
                               [{'nome': 'P', 'palavras': ['aggregate']}]) == {}


# ------------------------------------------------------------------ identidades (A1)
def test_identidade_parcial_e_com_acento_casa_como_o_git(repo):
    h1 = repo.commit('feat: um', 'src/Um.cs', nome='Pessoa Teste da Silva', mail='outro@exemplo.test', quando=_dias(5))
    h2 = repo.commit('feat: dois', 'src/Dois.cs', nome='Joana Simões', mail='joana@exemplo.test', quando=_dias(4))
    h3 = repo.commit('feat: tres', 'src/Tres.cs', nome='Mariana Souza', mail='mariana@exemplo.test', quando=_dias(3))
    achados = lambda ids: {c['hash'] for e in entregas.detectar(repo.pasta, ids, _desde()) for c in e['commits']}
    assert h1 in achados(['pessoa teste'])          # nome parcial: todas as palavras aparecem no nome do autor
    assert h2 in achados(['JOANA SIMOES'])          # sem acento e sem diferenciar maiúsculas
    assert h2 in achados(['Simões'])
    assert h3 not in achados(['Ana'])               # palavra inteira: 'Ana' não casa com 'Mariana'
    assert h1 not in achados(['Pessoa Outra'])      # toda palavra precisa aparecer
    assert achados(['OUTRO@exemplo.test']) == {h1}  # e-mail: igualdade exata, sem diferenciar maiúsculas
    assert not achados(['exemplo.test@'])


def test_identidades_incluem_git_config_do_repositorio(con, repo, privado):
    (privado / 'entrada.json').write_text(json.dumps({'repo': str(repo.pasta), 'author': 'Apelido Diferente'}),
                                          encoding='utf-8')
    repo.git('config', 'user.email', EU_MAIL)
    repo.git('config', 'user.name', 'Pessoa Teste')
    ids = entregas.identidades(con)
    assert ids[0] == 'Apelido Diferente' and 'Pessoa Teste' in ids and EU_MAIL in ids
    repo.commit('feat: minha', 'src/Minha.cs', quando=_dias(2))
    assert entregas.atualizar(con)['novas'] == 2  # 'inicio' + 'minha', achados pelo e-mail do git config


def test_janela_refaz_a_busca_quando_nada_casou_ou_identidade_mudou(con, repo, privado):
    repo.commit('feat: antiga', 'src/Antiga.cs', quando=_dias(40))
    (privado / 'entrada.json').write_text(json.dumps({'repo': str(repo.pasta), 'author': 'Ninguem Daqui'}),
                                          encoding='utf-8')
    assert entregas.atualizar(con) == {'novas': 0, 'atualizadas': 0}
    janela = trajetoria.perfil_ler(con, 'entregas_desde')
    assert janela['meus'] == 0 and janela['identidades']
    # A mesma identidade de novo: como nada casou, refaz os 90 dias (não só desde a última leitura)
    with banco.transacao(con):
        trajetoria.perfil_gravar(con, 'identidades', ['Ninguem Daqui', EU])  # identidade acrescentada depois
    assert entregas.atualizar(con)['novas'] == 2  # 'inicio' (30 d) e 'antiga' (40 d), mesmo com 'ultima' = agora
    assert trajetoria.perfil_ler(con, 'entregas_desde')['meus'] == 2
    # Outra identidade (segundo e-mail) com commits antigos: o hash muda e a janela inteira é lida de novo
    repo.commit('feat: do outro email', 'src/Outro.cs', nome='Apelido', mail='segundo@exemplo.test', quando=_dias(50))
    assert entregas.atualizar(con) == {'novas': 0, 'atualizadas': 0}  # ainda não é identidade dela
    with banco.transacao(con):
        trajetoria.perfil_gravar(con, 'identidades', ['Ninguem Daqui', EU, 'segundo@exemplo.test'])
    assert entregas.atualizar(con)['novas'] == 1


def test_titulo_do_pr_do_github_vem_do_ramo_com_a_chave_do_ticket(repo):
    """O título do `Merge pull request` sai do nome do ramo, com a chave do ticket (visível para a dona dos dados)."""
    repo.git('checkout', '-q', '-b', 'feature/ABC-1234-ajusta-agregado-2')
    repo.commit('feat: agregado', 'src/Pedido.cs', quando=_dias(6))
    repo.git('checkout', '-q', 'main')
    repo.git('merge', '--no-ff', '-m', 'Merge pull request #4821 from org/feature/ABC-1234-ajusta-agregado-2',
             'feature/ABC-1234-ajusta-agregado-2', quando=_dias(5))
    pr = [e for e in entregas.detectar(repo.pasta, [EU], _desde()) if e['fonte'] == 'merge-pr']
    assert len(pr) == 1
    assert pr[0]['titulo'] == 'ABC-1234 ajusta agregado 2', pr[0]['titulo']
    assert '4821' in pr[0]['ids_privados']


def test_chave_de_ticket_no_titulo_de_commit_fica_visivel(repo):
    repo.commit('feat: ABC-1234 ajusta agregado', 'src/A.cs', quando=_dias(3))
    titulos = [e['titulo'] for e in entregas.detectar(repo.pasta, [EU], _desde())]
    assert titulos[-1] == 'feat: ABC-1234 ajusta agregado'


@pytest.mark.parametrize('bruto, esperado, id_', [
    ('Bug 14988: corrigir layout do mapa ao aplicar zoom', 'corrigir layout do mapa ao aplicar zoom', '14988'),
    ('Task 123 - ajustar filtro', 'ajustar filtro', '123'),
    ('User Story 45 cria cadastro', 'cria cadastro', '45'),
    ('PBI 7: nova regra', 'nova regra', '7'),
    ('feature #9: exporta relatorio', 'exporta relatorio', '9'),
    ('TAREFA 12 - revisa tela', 'revisa tela', '12'),
    ('Item 3: limpa codigo', 'limpa codigo', '3'),
    ('AB#321 ajusta agregado', 'ajusta agregado', '321'),
    ('ajusta agregado #55', 'ajusta agregado', '55'),
    ('ajusta agregado PR 88', 'ajusta agregado', '88'),
    ('ajusta agregado !99', 'ajusta agregado', '99'),
    ('corrige erro 20481 no login', 'corrige erro no login', '20481'),
])
def test_limpar_ids_padroes(bruto, esperado, id_):
    titulo, ids = entregas.limpar_ids(bruto)
    assert titulo == esperado
    assert ids == [id_]


def test_limpar_ids_mantem_numeros_do_texto_e_tag():
    assert entregas.limpar_ids('[Módulo X] Bug 14988: ajusta 3 telas para v2')[0] == '[Módulo X] ajusta 3 telas para v2'
    assert entregas.tag_inicial('[Módulo X] ajusta') == '[Módulo X]'
    assert entregas.tag_inicial('ajusta [x]') is None


def test_entrega_azure_mantem_numero_no_titulo_e_guarda_em_ids(repo):
    repo.git('checkout', '-q', '-b', 'feat')
    repo.commit('feat: mapa', 'src/M.cs', quando=_dias(6))
    repo.git('checkout', '-q', 'main')
    repo.git('merge', '--no-ff', '-m', 'Merged PR 123: Bug 14988: corrigir layout do mapa ao aplicar zoom', 'feat',
             quando=_dias(4))
    repo.commit('Task 77 - ajusta 3 telas v2', 'src/T.cs', quando=_dias(2))
    achadas = entregas.detectar(repo.pasta, [EU], _desde())
    pr = next(e for e in achadas if e['fonte'] == 'merge-pr')
    assert pr['titulo'] == 'Bug 14988: corrigir layout do mapa ao aplicar zoom'
    assert pr['ids_privados'] == ['123', '14988']
    solto = next(e for e in achadas if e['fonte'] == 'commit' and e['ids_privados'])
    assert solto['titulo'] == 'Task 77 - ajusta 3 telas v2' and solto['ids_privados'] == ['77']


def test_titulo_mascarado_por_versao_antiga_e_regravado_do_git_sem_duplicar(con, repo, privado):
    from luzia import jogo
    repo.commit('feat: ProdutoZeta algo Bug 14988', 'src/A.cs', quando=_dias(40))
    repo.commit('fix: outra coisa #321', 'src/B.cs', quando=_dias(3))
    _entrada(privado, repo)
    entregas.atualizar(con)
    total = con.execute('SELECT COUNT(*) FROM entrega').fetchone()[0]
    # Como uma versão antiga deixava: título e mensagem mascarados, janela sem a marca de títulos reais.
    con.execute("UPDATE entrega SET titulo = 'feat: [EMPRESA/PRODUTO] algo' WHERE titulo LIKE 'feat: ProdutoZeta%'")
    con.execute("UPDATE commit_ SET mensagem = 'feat: [EMPRESA/PRODUTO] algo' WHERE mensagem LIKE 'feat: ProdutoZeta%'")
    con.execute("UPDATE entrega SET titulo = 'fix: outra coisa' WHERE titulo LIKE 'fix: outra coisa%'")
    janela = trajetoria.perfil_ler(con, 'entregas_desde')
    janela.pop('titulos')
    trajetoria.perfil_gravar(con, 'entregas_desde', janela)
    con.commit()
    eid = con.execute("SELECT id FROM entrega WHERE titulo = 'feat: [EMPRESA/PRODUTO] algo'").fetchone()[0]
    jogo.lancar(DDD, 20, 'propria', 'feixe', 'feat: [EMPRESA/PRODUTO] algo')  # lúmen antigo citava o título mascarado

    assert entregas.atualizar(con) == {'novas': 0, 'atualizadas': 0}
    assert con.execute('SELECT COUNT(*) FROM entrega').fetchone()[0] == total
    titulos = {r['titulo'] for r in con.execute('SELECT titulo FROM entrega')}
    assert {'feat: ProdutoZeta algo Bug 14988', 'fix: outra coisa #321'} <= titulos
    assert not any('[EMPRESA/PRODUTO]' in t for t in titulos)
    assert con.execute("SELECT mensagem FROM commit_ WHERE entrega_id = ?", (eid,)).fetchone()[0] == \
        'feat: ProdutoZeta algo Bug 14988'
    assert '14988' in json.loads(con.execute('SELECT ids_privados_json FROM entrega WHERE id = ?', (eid,)).fetchone()[0])
    det = entregas.detalhe(con, eid, incluir_leitura=False)
    assert det['titulo'] == 'feat: ProdutoZeta algo Bug 14988'
    assert any(l['ref'] == 'feat: [EMPRESA/PRODUTO] algo' for l in det['lumens_ligados'])  # o lúmen segue ligado
    assert entregas.atualizar(con) == {'novas': 0, 'atualizadas': 0}  # a releitura inteira acontece uma vez só
    assert trajetoria.perfil_ler(con, 'entregas_desde')['titulos'] == 'reais'
