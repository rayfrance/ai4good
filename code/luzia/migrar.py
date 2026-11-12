"""Migração dos JSON antigos de `private/` para o banco (`luzia.db`).

A Tarefa 3 implementa a importação. `banco.garantir` chama `migrar(con)` uma única vez, já dentro de uma
transação `BEGIN EXCLUSIVE`: esta função só executa comandos na conexão recebida, nunca abre, confirma
nem desfaz a transação.
"""

from __future__ import annotations


def migrar(con) -> dict:
    """Importa os dados antigos para o banco e devolve um resumo do que entrou (por enquanto, nada)."""
    return {}
