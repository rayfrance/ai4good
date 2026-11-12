"""Banco SQLite da Luzia (`private/luzia.db`): a única camada que abre o estado persistente.

Hook, CLI e painel escrevem ao mesmo tempo, então:
- modo WAL (leitores não bloqueiam quem escreve) e `busy_timeout` de 5 s (quem chega espera a vez);
- toda escrita acontece dentro de `transacao(con)`, que abre `BEGIN IMMEDIATE` e confirma ou desfaz tudo;
- a conexão fica em autocommit do Python (`isolation_level=None`): só os `BEGIN` explícitos abrem transação.

Livros só de acréscimo (`lumen`, `avanco_evento`, `nivel_registro`, `trajetoria_versao`, `chamada_modelo`):
o código só insere neles, nunca reescreve nem apaga (um teste procura isso nas consultas dos módulos).
O estado atual (estado de um avanço, nível de um prisma) fica em colunas e tem de bater com os livros.
"""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Iterator

from . import arquivos

ESQUEMA_VERSAO = 1
ESPERA_MS = 5000

ESQUEMA = (
    """CREATE TABLE IF NOT EXISTS meta (
        chave TEXT PRIMARY KEY,
        valor TEXT
    )""",
    """CREATE TABLE IF NOT EXISTS perfil (
        chave TEXT PRIMARY KEY,
        valor_json TEXT NOT NULL
    )""",
    """CREATE TABLE IF NOT EXISTS prisma (
        nome TEXT PRIMARY KEY,
        palavras_json TEXT NOT NULL DEFAULT '[]',
        nivel INTEGER,
        meta INTEGER,
        estado TEXT NOT NULL DEFAULT 'ativo' CHECK (estado IN ('ativo', 'arquivado')),
        origem TEXT NOT NULL CHECK (origem IN ('triagem', 'pedido')),
        ultimo_nivel_em TEXT,
        criado_em TEXT NOT NULL
    )""",
    """CREATE TABLE IF NOT EXISTS leitura (
        id INTEGER PRIMARY KEY,
        alvo_tipo TEXT NOT NULL CHECK (alvo_tipo IN ('prisma', 'entrega', 'pedido')),
        alvo_id TEXT NOT NULL,
        texto TEXT NOT NULL,
        base_json TEXT NOT NULL,
        base_hash TEXT NOT NULL,
        modelo TEXT NOT NULL,
        criado_em TEXT NOT NULL
    )""",
    """CREATE TABLE IF NOT EXISTS pedido (
        id INTEGER PRIMARY KEY,
        tipo TEXT NOT NULL CHECK (tipo IN ('incluir', 'arquivar', 'reativar', 'mudar_meta')),
        prisma TEXT NOT NULL,
        motivo TEXT,
        proposta_json TEXT,
        leitura_id INTEGER REFERENCES leitura (id),
        estado TEXT NOT NULL DEFAULT 'aberto' CHECK (estado IN ('aberto', 'proposto', 'aceito', 'recusado')),
        criado_em TEXT NOT NULL,
        decidido_em TEXT
    )""",
    """CREATE TABLE IF NOT EXISTS trajetoria_versao (
        numero INTEGER PRIMARY KEY,
        criada_em TEXT NOT NULL,
        origem TEXT NOT NULL,
        pedido_id INTEGER REFERENCES pedido (id),
        foto_json TEXT NOT NULL
    )""",
    """CREATE TABLE IF NOT EXISTS entrega (
        id INTEGER PRIMARY KEY,
        chave TEXT NOT NULL UNIQUE,
        titulo TEXT,
        inicio TEXT,
        fim TEXT,
        commits INTEGER NOT NULL DEFAULT 0,
        arquivos INTEGER NOT NULL DEFAULT 0,
        linhas INTEGER NOT NULL DEFAULT 0,
        areas_json TEXT NOT NULL DEFAULT '[]',
        ids_privados_json TEXT NOT NULL DEFAULT '[]',
        fonte TEXT
    )""",
    """CREATE TABLE IF NOT EXISTS commit_ (
        hash TEXT PRIMARY KEY,
        entrega_id INTEGER REFERENCES entrega (id),
        data TEXT,
        mensagem TEXT,
        arquivos INTEGER NOT NULL DEFAULT 0,
        linhas INTEGER NOT NULL DEFAULT 0,
        areas_json TEXT NOT NULL DEFAULT '[]'
    )""",
    """CREATE TABLE IF NOT EXISTS entrega_prisma (
        entrega_id INTEGER NOT NULL REFERENCES entrega (id),
        prisma TEXT NOT NULL,
        termos_json TEXT NOT NULL DEFAULT '[]',
        PRIMARY KEY (entrega_id, prisma)
    )""",
    # O avanço guarda o estado atual; a história fica no livro avanco_evento.
    """CREATE TABLE IF NOT EXISTS avanco (
        id TEXT PRIMARY KEY,
        prisma TEXT NOT NULL,
        tipo TEXT,
        titulo TEXT NOT NULL,
        conteudo_json TEXT NOT NULL DEFAULT '{}',
        duracao_min INTEGER,
        valor_lm INTEGER,
        conta_json TEXT,
        origem TEXT,
        entrega_id INTEGER,
        dimensao TEXT,
        estado TEXT NOT NULL,
        nota INTEGER,
        lm_ganho INTEGER NOT NULL DEFAULT 0,
        tentativas INTEGER NOT NULL DEFAULT 0,
        revisitas INTEGER NOT NULL DEFAULT 0,
        revisita_aberta INTEGER NOT NULL DEFAULT 0,
        criado_em TEXT NOT NULL
    )""",
    """CREATE TABLE IF NOT EXISTS avanco_evento (
        id INTEGER PRIMARY KEY,
        avanco_id TEXT NOT NULL REFERENCES avanco (id),
        quando TEXT NOT NULL,
        evento TEXT NOT NULL,
        onde TEXT,
        nota INTEGER,
        resumo TEXT,
        motivo TEXT
    )""",
    """CREATE TABLE IF NOT EXISTS lumen (
        id INTEGER PRIMARY KEY,
        quando TEXT NOT NULL,
        prisma TEXT NOT NULL,
        lm INTEGER NOT NULL,
        luz TEXT NOT NULL CHECK (luz IN ('propria', 'refletida')),
        fonte TEXT NOT NULL,
        ref TEXT NOT NULL DEFAULT ''
    )""",
    """CREATE TABLE IF NOT EXISTS nivel_registro (
        id INTEGER PRIMARY KEY,
        prisma TEXT NOT NULL,
        de INTEGER,
        para INTEGER NOT NULL,
        quando TEXT NOT NULL,
        origem TEXT NOT NULL CHECK (origem IN ('conquistado', 'declarado', 'migrado', 'pedido')),
        lm INTEGER,
        luz_propria REAL
    )""",
    """CREATE TABLE IF NOT EXISTS lampejo (
        id INTEGER PRIMARY KEY,
        prisma TEXT NOT NULL,
        sessao TEXT,
        quando TEXT NOT NULL,
        estado TEXT NOT NULL DEFAULT 'aberto' CHECK (estado IN ('aberto', 'convertido', 'guardado')),
        usado_em TEXT
    )""",
    """CREATE TABLE IF NOT EXISTS fila (
        avanco_id TEXT PRIMARY KEY,
        titulo TEXT,
        quando TEXT NOT NULL,
        oferecida_json TEXT NOT NULL DEFAULT '[]'
    )""",
    """CREATE TABLE IF NOT EXISTS sessao_evento (
        id INTEGER PRIMARY KEY,
        quando TEXT NOT NULL,
        sessao TEXT,
        prisma TEXT,
        extensao TEXT,
        ferramenta TEXT,
        modo TEXT,
        lm INTEGER,
        luz TEXT,
        interveio INTEGER
    )""",
    """CREATE TABLE IF NOT EXISTS chamada_modelo (
        id INTEGER PRIMARY KEY,
        quando TEXT NOT NULL,
        rotulo TEXT,
        modelo TEXT,
        segundos REAL,
        tokens_in INTEGER,
        tokens_out INTEGER,
        registro_json TEXT
    )""",
    'CREATE INDEX IF NOT EXISTS lumen_prisma_quando ON lumen (prisma, quando)',
    'CREATE INDEX IF NOT EXISTS avanco_prisma_estado ON avanco (prisma, estado)',
    'CREATE INDEX IF NOT EXISTS avanco_evento_avanco ON avanco_evento (avanco_id, quando)',
    'CREATE INDEX IF NOT EXISTS nivel_registro_prisma ON nivel_registro (prisma, quando)',
    'CREATE INDEX IF NOT EXISTS lampejo_prisma_estado ON lampejo (prisma, estado)',
    'CREATE INDEX IF NOT EXISTS sessao_evento_sessao ON sessao_evento (sessao, prisma)',
    'CREATE INDEX IF NOT EXISTS commit_entrega ON commit_ (entrega_id)',
    'CREATE INDEX IF NOT EXISTS leitura_alvo ON leitura (alvo_tipo, alvo_id)',
)


def caminho() -> Path:
    """Onde mora o banco; lê `arquivos.PRIVATE` a cada chamada (LUZIA_PRIVATE pode mudar, como nos testes)."""
    return Path(arquivos.PRIVATE) / 'luzia.db'


def conectar(arquivo: Path | None = None) -> sqlite3.Connection:
    """Abre o banco (por padrão `caminho()`), configura WAL, espera e chaves estrangeiras e garante o esquema."""
    arquivo = Path(arquivo) if arquivo is not None else caminho()
    arquivo.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(arquivo, timeout=ESPERA_MS / 1000, isolation_level=None)
    try:
        con.row_factory = sqlite3.Row
        con.execute(f'PRAGMA busy_timeout = {ESPERA_MS}')  # antes do WAL: trocar o modo também espera a vez
        con.execute('PRAGMA journal_mode = WAL')
        con.execute('PRAGMA foreign_keys = ON')
        garantir(con)
    except BaseException:
        con.close()
        raise
    return con


@contextmanager
def transacao(con: sqlite3.Connection, modo: str = 'IMMEDIATE') -> Iterator[sqlite3.Connection]:
    """`with transacao(con):` abre `BEGIN IMMEDIATE` (ou `EXCLUSIVE`); confirma no fim ou desfaz se der erro."""
    if modo not in ('IMMEDIATE', 'EXCLUSIVE'):
        raise ValueError(f'modo de transação inválido: {modo}')
    con.execute(f'BEGIN {modo}')
    try:
        yield con
    except BaseException:
        con.rollback()
        raise
    con.commit()


def _meta(con: sqlite3.Connection) -> dict[str, str]:
    """As marcas `esquema` e `migrado_em`, ou {} se o banco ainda não tem a tabela meta."""
    if not con.execute("SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'meta'").fetchone():
        return {}
    linhas = con.execute("SELECT chave, valor FROM meta WHERE chave IN ('esquema', 'migrado_em')").fetchall()
    return {r['chave']: r['valor'] for r in linhas}


def _pronto(con: sqlite3.Connection) -> bool:
    marcas = _meta(con)
    versao = marcas.get('esquema')
    if versao is not None and int(versao) > ESQUEMA_VERSAO:
        raise RuntimeError(f'luzia.db tem esquema {versao}, mais novo que o deste código ({ESQUEMA_VERSAO})')
    return versao == str(ESQUEMA_VERSAO) and bool(marcas.get('migrado_em'))


def garantir(con: sqlite3.Connection) -> None:
    """Cria o esquema que faltar e roda a migração dos JSON uma única vez, numa transação exclusiva.

    Qualquer ponto de entrada (hook, CLI, painel) pode chegar primeiro: quem pega a trava cria e migra;
    quem chega depois só confere as marcas `meta('esquema')` e `meta('migrado_em')`.
    """
    if _pronto(con):
        return
    with transacao(con, 'EXCLUSIVE'):
        if _pronto(con):  # outro processo terminou enquanto esperávamos a trava
            return
        for sql in ESQUEMA:
            con.execute(sql)
        con.execute("INSERT INTO meta (chave, valor) VALUES ('esquema', ?) "
                    'ON CONFLICT (chave) DO UPDATE SET valor = excluded.valor', (str(ESQUEMA_VERSAO),))
        if not _meta(con).get('migrado_em'):
            from . import migrar  # import tardio: a migração usa este módulo e não pode criar ciclo
            migrar.migrar(con)
            con.execute("INSERT INTO meta (chave, valor) VALUES ('migrado_em', ?)",
                        (datetime.now().isoformat(timespec='seconds'),))
