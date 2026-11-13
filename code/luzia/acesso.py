"""Entrada no painel herdada do agente: link de uso único e sessões de 30 dias (biblioteca padrão).

- Quem abre o painel pelo chat (`career-map`, em qualquer harness) já roda como a pessoa no sistema: a CLI grava um link
  de uso único (`secrets.token_urlsafe(32)`) que vale 2 minutos e abre `http://127.0.0.1:8501/#entrar=<token>`. O token
  vai no fragmento (o navegador não o manda ao servidor nem no Referer); o painel o tira da barra e o troca por uma
  sessão em `POST /api/acesso/link`. O link é gasto na primeira tentativa, mesmo vencido. Vários podem estar pendentes.
- Sessão: token aleatório só no cookie `luzia_sessao`; no banco privado fica só o SHA-256 dele, com o último uso. Vale 30
  dias sem uso; cada uso real renova (chamadas automáticas do painel conferem sem renovar). Sobrevive a reinícios do
  servidor. "Sair" encerra a sessão atual; `acesso sair-de-todos` no chat encerra todas.
- Links e sessões moram no SQLite (`acesso_link`, `acesso_sessao`): a CLI grava o link enquanto o servidor lê e grava
  sessões, e as transações do banco (WAL, BEGIN IMMEDIATE, busy_timeout) já resolvem essa concorrência.
- Comparação dos hashes em tempo constante (`hmac.compare_digest`, sobre todas as linhas). Passados 10 links errados
  num minuto, os errados seguintes recebem 429; um link válido sempre entra (o limite vale só para erros: nenhum outro
  processo local consegue barrar a entrada da pessoa, e adivinhar 256 bits é inviável de qualquer jeito). Banco ocupado
  ou migração bloqueada vira `AcessoIndisponivel` (o servidor responde 503 com o motivo) sem apagar nada.
- Nada aqui grava ou devolve um token em claro em log, banco ou resposta.
"""

from __future__ import annotations

import hashlib
import hmac
import secrets
import sqlite3
import threading
import time
from collections import deque
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Iterator

from . import arquivos, banco

COOKIE = 'luzia_sessao'
LINK_S = 120                     # validade do link de entrada
SESSAO_MAX_S = 30 * 24 * 3600    # 30 dias sem uso
LIMITE_LINKS = 10                # links errados aceitos por janela
JANELA_LINKS_S = 60
MIN_TOKEN, MAX_TOKEN = 20, 256


class AcessoIndisponivel(RuntimeError):
    """O banco não respondeu agora (trava ou disco): tente de novo; nenhuma sessão foi apagada."""


def _hash(token: str) -> str:
    return hashlib.sha256(token.encode('utf-8')).hexdigest()


def _token_ok(token) -> bool:
    return isinstance(token, str) and MIN_TOKEN <= len(token) <= MAX_TOKEN


def _abrir() -> sqlite3.Connection:
    return banco.conectar()


def _apagar_legado() -> None:
    """`private/acesso.json` de versões anteriores (guardava um hash de credencial): não serve mais e não fica largado."""
    antigo = arquivos.PRIVATE / 'acesso.json'
    try:
        antigo.unlink(missing_ok=True)
    except OSError as e:
        arquivos.registrar_erro('acesso apagar acesso.json antigo', e)


@contextmanager
def _banco() -> Iterator[sqlite3.Connection]:
    try:
        con = _abrir()
    except sqlite3.OperationalError as e:
        raise AcessoIndisponivel('o banco da Luzia está ocupado; tente de novo') from e
    except RuntimeError as e:  # banco.garantir: migração bloqueada ou esquema mais novo que este código
        raise AcessoIndisponivel(f'o banco da Luzia não abriu: {e}') from e
    try:
        yield con
    except sqlite3.OperationalError as e:
        raise AcessoIndisponivel('o banco da Luzia está ocupado; tente de novo') from e
    finally:
        con.close()


def _achar(con: sqlite3.Connection, tabela: str, token: str) -> sqlite3.Row | None:
    """A linha cujo hash é o do token, comparando com todas em tempo constante."""
    alvo = _hash(token)
    achada = None
    for r in con.execute(f'SELECT * FROM {tabela}').fetchall():
        if hmac.compare_digest(r['hash'], alvo):
            achada = r
    return achada


# ------------------------------------------------------------------ links (gravados pela CLI)
def emitir_link(agora: float | None = None) -> str:
    """Link novo de uso único (2 min). Devolve o token, que só deve ir para o fragmento da URL do navegador."""
    agora = time.time() if agora is None else agora
    token = secrets.token_urlsafe(32)
    _apagar_legado()
    with _banco() as con, banco.transacao(con):
        con.execute('DELETE FROM acesso_link WHERE expira < ?', (agora,))
        con.execute('INSERT INTO acesso_link (hash, expira) VALUES (?, ?)', (_hash(token), agora + LINK_S))
    return token


def consumir_link(token: str, agora: float) -> bool:
    """True se o link existe e está no prazo. Achado, ele é apagado (uso único), vencido ou não."""
    with _banco() as con, banco.transacao(con):
        r = _achar(con, 'acesso_link', token)
        con.execute('DELETE FROM acesso_link WHERE expira < ?', (agora,))
        if r is None:
            return False
        con.execute('DELETE FROM acesso_link WHERE hash = ?', (r['hash'],))
        return float(r['expira']) >= agora


# ------------------------------------------------------------------ sessões
def abrir_sessao(agora: float) -> str:
    token = secrets.token_urlsafe(32)
    with _banco() as con, banco.transacao(con):
        con.execute('DELETE FROM acesso_sessao WHERE ultimo_uso < ?', (agora - SESSAO_MAX_S,))
        con.execute('INSERT INTO acesso_sessao (hash, criada_em, ultimo_uso) VALUES (?, ?, ?)',
                    (_hash(token), agora, agora))
    return token


def validar_sessao(token: str, agora: float, renovar: bool = True) -> bool:
    """Sessão existe e foi usada nos últimos 30 dias? `renovar` (uso real) atualiza o último uso."""
    with _banco() as con:
        r = _achar(con, 'acesso_sessao', token)
        if r is None:
            return False
        if agora - float(r['ultimo_uso']) > SESSAO_MAX_S:
            with banco.transacao(con):
                con.execute('DELETE FROM acesso_sessao WHERE hash = ?', (r['hash'],))
            return False
        if renovar:
            with banco.transacao(con):
                con.execute('UPDATE acesso_sessao SET ultimo_uso = ? WHERE hash = ?', (agora, r['hash']))
        return True


def fechar_sessao(token: str) -> None:
    with _banco() as con:
        r = _achar(con, 'acesso_sessao', token)
        if r is not None:
            with banco.transacao(con):
                con.execute('DELETE FROM acesso_sessao WHERE hash = ?', (r['hash'],))


def encerrar_todas() -> int:
    """Encerra todas as sessões (comando `acesso sair-de-todos`). Devolve quantas havia."""
    with _banco() as con, banco.transacao(con):
        return con.execute('DELETE FROM acesso_sessao').rowcount


def sessoes_ativas(agora: float | None = None) -> int:
    agora = time.time() if agora is None else agora
    with _banco() as con:
        return int(con.execute('SELECT COUNT(*) FROM acesso_sessao WHERE ultimo_uso >= ?',
                               (agora - SESSAO_MAX_S,)).fetchone()[0])


# ------------------------------------------------------------------ portaria do servidor
@dataclass
class Entrada:
    token: str | None = None
    limitado_s: int = 0
    indisponivel: str = ''  # motivo, quando o banco não respondeu


class Portaria:
    """Entrada por link e conferência de sessão no servidor; `relogio` (segundos, época) é injetável nos testes.

    Só o limite de links errados fica em memória: links e sessões estão no banco e sobrevivem a reinícios."""

    def __init__(self, relogio=time.time):
        self.relogio = relogio
        self._falhas: deque[float] = deque()
        self._trava = threading.Lock()

    def _espera(self, agora: float) -> int:
        while self._falhas and agora - self._falhas[0] >= JANELA_LINKS_S:
            self._falhas.popleft()
        if len(self._falhas) < LIMITE_LINKS:
            return 0
        return max(1, int(-(-(self._falhas[0] + JANELA_LINKS_S - agora) // 1)))

    def entrar_por_link(self, token) -> Entrada:
        """Troca um link por uma sessão. Errado, vencido ou já usado: sem sessão; depois de 10 erros no minuto, os
        erros seguintes recebem `limitado_s`. O link é conferido antes do limite: um link válido sempre entra."""
        with self._trava:
            agora = self.relogio()
            try:
                ok = _token_ok(token) and consumir_link(token, agora)
            except AcessoIndisponivel as e:
                return Entrada(indisponivel=str(e))
            if not ok:
                espera = self._espera(agora)
                self._falhas.append(agora)
                return Entrada(limitado_s=espera)
        try:
            _apagar_legado()
            return Entrada(token=abrir_sessao(agora))
        except AcessoIndisponivel as e:
            return Entrada(indisponivel=str(e))

    def valida(self, token, renovar: bool = True) -> bool:
        """Sessão válida? `AcessoIndisponivel` (banco ocupado) sobe sem apagar a sessão."""
        if not _token_ok(token):
            return False
        return validar_sessao(token, self.relogio(), renovar)

    def fechar(self, token) -> None:
        if _token_ok(token):
            fechar_sessao(token)
