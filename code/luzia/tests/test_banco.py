"""Banco SQLite da Luzia (`private/luzia.db`): esquema v1, WAL, transações e livros só de acréscimo.

Tudo roda na fixture `privado`: o banco nasce na pasta temporária do teste, nunca em `code/luzia/private/`.
"""

import multiprocessing
import re
from pathlib import Path

import pytest

from luzia import banco

TABELAS = {
    'meta': {'chave', 'valor'},
    'perfil': {'chave', 'valor_json'},
    'prisma': {'nome', 'palavras_json', 'nivel', 'meta', 'estado', 'origem', 'ultimo_nivel_em', 'criado_em'},
    'trajetoria_versao': {'numero', 'criada_em', 'origem', 'pedido_id', 'foto_json'},
    'pedido': {'id', 'tipo', 'prisma', 'motivo', 'proposta_json', 'leitura_id', 'estado', 'criado_em', 'decidido_em'},
    'avanco': {'id', 'prisma', 'tipo', 'titulo', 'conteudo_json', 'duracao_min', 'valor_lm', 'conta_json', 'origem',
               'entrega_id', 'dimensao', 'estado', 'nota', 'lm_ganho', 'tentativas', 'revisitas', 'revisita_aberta',
               'criado_em'},
    'avanco_evento': {'id', 'avanco_id', 'quando', 'evento', 'onde', 'nota', 'resumo', 'motivo', 'extra_json'},
    'lumen': {'id', 'quando', 'prisma', 'lm', 'luz', 'fonte', 'ref'},
    'nivel_registro': {'id', 'prisma', 'de', 'para', 'quando', 'origem', 'lm', 'luz_propria'},
    'lampejo': {'id', 'prisma', 'sessao', 'quando', 'estado', 'usado_em'},
    'entrega': {'id', 'chave', 'titulo', 'inicio', 'fim', 'commits', 'arquivos', 'linhas', 'areas_json',
                'ids_privados_json', 'fonte'},
    'commit_': {'hash', 'entrega_id', 'data', 'mensagem', 'arquivos', 'linhas', 'areas_json'},
    'entrega_prisma': {'entrega_id', 'prisma', 'termos_json'},
    'leitura': {'id', 'alvo_tipo', 'alvo_id', 'texto', 'base_json', 'base_hash', 'modelo', 'criado_em'},
    'fila': {'avanco_id', 'titulo', 'quando', 'oferecida_json'},
    'sessao_evento': {'id', 'quando', 'sessao', 'prisma', 'extensao', 'ferramenta', 'modo', 'lm', 'luz', 'interveio'},
    'chamada_modelo': {'id', 'quando', 'rotulo', 'modelo', 'segundos', 'tokens_in', 'tokens_out', 'registro_json'},
}
LIVROS = ('lumen', 'avanco_evento', 'nivel_registro', 'trajetoria_versao', 'chamada_modelo')
# Reescrever um livro: UPDATE, DELETE ou INSERT OR REPLACE / REPLACE INTO (que apaga a linha antiga).
REESCRITA = re.compile(r'\b(?:UPDATE|DELETE\s+FROM|INSERT\s+OR\s+REPLACE\s+INTO|REPLACE\s+INTO)\s+["`]?('
                       + '|'.join(LIVROS) + r')\b', re.IGNORECASE)
POR_PROCESSO = 200


def _gravar_lumens(arquivo: str, quem: int, largada) -> None:
    """Roda num processo filho (spawn): grava POR_PROCESSO lúmens, um por transação, no banco indicado."""
    con = banco.conectar(Path(arquivo))
    largada.wait(timeout=60)
    for i in range(POR_PROCESSO):
        with banco.transacao(con):
            con.execute('INSERT INTO lumen (quando, prisma, lm, luz, fonte, ref) VALUES (?, ?, ?, ?, ?, ?)',
                        ('2026-11-12T10:00:00', f'Prisma {quem}', 10, 'refletida', 'teste', f'{quem}-{i}'))
    con.close()


def _abrir_junto(arquivo: str, largada, saida) -> None:
    """Roda num processo filho (spawn): abre um banco ainda inexistente ao mesmo tempo que os outros."""
    largada.wait(timeout=60)
    try:
        banco.conectar(Path(arquivo)).close()
        saida.put('ok')
    except Exception as e:  # o teste mostra qual processo falhou e por quê
        saida.put(repr(e))


def _esperar(procs, timeout: float = 120) -> list:
    """Espera os processos; quem passar do tempo é encerrado (não fica preso depois do teste)."""
    for p in procs:
        p.join(timeout=timeout)
    for p in procs:
        if p.is_alive():
            p.terminate()
            p.join(timeout=10)
    return [p.exitcode for p in procs]


def test_esquema_criado(privado):
    con = banco.conectar()
    assert banco.caminho() == privado / 'luzia.db' and banco.caminho().exists()
    for tabela, colunas in TABELAS.items():
        achadas = {r['name'] for r in con.execute(f'PRAGMA table_info({tabela})')}
        assert colunas <= achadas, (tabela, colunas - achadas)
    meta = dict(con.execute('SELECT chave, valor FROM meta').fetchall())
    assert meta['esquema'] == str(banco.ESQUEMA_VERSAO) == '1'
    assert meta['migrado_em']
    pk = [r['name'] for r in con.execute('PRAGMA table_info(entrega_prisma)') if r['pk']]
    assert sorted(pk) == ['entrega_id', 'prisma']
    con.close()


def test_wal_e_timeout(privado):
    con = banco.conectar()
    assert con.execute('PRAGMA journal_mode').fetchone()[0] == 'wal'
    assert con.execute('PRAGMA busy_timeout').fetchone()[0] == 5000
    assert con.execute('PRAGMA foreign_keys').fetchone()[0] == 1
    assert isinstance(con.execute('SELECT valor FROM meta').fetchone(), banco.sqlite3.Row)
    con.close()


def test_escrita_concorrente(privado):
    banco.conectar().close()
    ctx = multiprocessing.get_context('spawn')
    largada = ctx.Barrier(4)
    procs = [ctx.Process(target=_gravar_lumens, args=(str(banco.caminho()), quem, largada)) for quem in range(4)]
    for p in procs:
        p.start()
    assert _esperar(procs) == [0, 0, 0, 0]
    con = banco.conectar()
    assert con.execute('SELECT COUNT(*) FROM lumen').fetchone()[0] == 4 * POR_PROCESSO
    assert con.execute('SELECT COUNT(DISTINCT ref) FROM lumen').fetchone()[0] == 4 * POR_PROCESSO
    con.close()


def test_primeira_abertura_simultanea(privado):
    """Hook, statusline, painel e CLI podem abrir juntos um banco que ainda não existe: ninguém falha."""
    arquivo = privado / 'novo' / 'luzia.db'
    ctx = multiprocessing.get_context('spawn')
    n = 8
    largada, saida = ctx.Barrier(n), ctx.Queue()
    procs = [ctx.Process(target=_abrir_junto, args=(str(arquivo), largada, saida)) for _ in range(n)]
    for p in procs:
        p.start()
    assert _esperar(procs) == [0] * n
    assert sorted(saida.get(timeout=10) for _ in range(n)) == ['ok'] * n
    con = banco.conectar(arquivo)
    assert con.execute('PRAGMA journal_mode').fetchone()[0] == 'wal'
    assert con.execute("SELECT COUNT(*) FROM meta WHERE chave IN ('esquema', 'migrado_em')").fetchone()[0] == 2
    con.close()


def test_commit_que_falha_desfaz(privado):
    """Se o COMMIT falhar (aqui, chave estrangeira adiada), a conexão não fica presa numa transação."""
    con = banco.conectar()
    with pytest.raises(banco.sqlite3.IntegrityError):
        with banco.transacao(con):
            con.execute('PRAGMA defer_foreign_keys = ON')
            con.execute("INSERT INTO commit_ (hash, entrega_id) VALUES ('h1', 999)")
    assert not con.in_transaction
    assert con.execute('SELECT COUNT(*) FROM commit_').fetchone()[0] == 0
    con.close()


def test_aceita_dados_antigos_incompletos(privado):
    """A migração (Tarefa 3) não pode abortar por evento órfão nem inventar título, prisma ou data."""
    con = banco.conectar()
    with banco.transacao(con):
        con.execute("INSERT INTO avanco_evento (avanco_id, quando, evento) VALUES ('sem-feixe', '2026-01-01', 'conquistado')")
        con.execute("INSERT INTO avanco (id, estado, criado_em) VALUES ('a1', 'sugerido', '2026-01-01')")
        con.execute("INSERT INTO prisma (nome) VALUES ('Mensageria')")
    assert con.execute("SELECT origem FROM prisma WHERE nome = 'Mensageria'").fetchone()[0] == 'triagem'
    with pytest.raises(banco.sqlite3.IntegrityError):  # as enumerações continuam conferidas
        with banco.transacao(con):
            con.execute("INSERT INTO prisma (nome, origem) VALUES ('X', 'inventada')")
    con.close()


def test_livros_sem_update():
    assert REESCRITA.search("UPDATE lumen SET lm = 0") and REESCRITA.search('delete from avanco_evento where 1')
    assert REESCRITA.search('INSERT OR REPLACE INTO nivel_registro VALUES (1)')
    assert not REESCRITA.search('UPDATE avanco SET estado = ?')  # estado atual pode mudar; o livro, não
    pacote = Path(banco.__file__).parent
    fontes = [pacote / 'banco.py', pacote / 'jogo.py', *sorted(pacote.glob('*.py'))]
    for fonte in dict.fromkeys(fontes):
        achado = REESCRITA.search(fonte.read_text(encoding='utf-8'))
        assert not achado, f'{fonte.name} reescreve o livro {achado.group(1)}'


def test_transacao_desfaz_em_erro(privado):
    con = banco.conectar()
    antes = con.execute('SELECT COUNT(*) FROM perfil').fetchone()[0]  # a migração já trouxe o plano da fixture
    with pytest.raises(RuntimeError):
        with banco.transacao(con):
            con.execute("INSERT INTO perfil (chave, valor_json) VALUES ('teste_desfazer', '\"12 meses\"')")
            raise RuntimeError('falhou no meio')
    assert con.execute('SELECT COUNT(*) FROM perfil').fetchone()[0] == antes
    assert not con.in_transaction
    con.close()


def test_migracao_roda_uma_vez(privado, monkeypatch):
    from luzia import migrar

    chamadas = []
    monkeypatch.setattr(migrar, 'migrar', lambda con: chamadas.append(con.in_transaction) or {})
    banco.conectar().close()
    banco.conectar().close()
    assert chamadas == [True]
