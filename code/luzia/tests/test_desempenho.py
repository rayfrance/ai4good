"""/api/estado roda a cada 4 s: cada entrega é calculada uma vez, e o termos.txt não é relido sem mudar."""

import json
import os
from pathlib import Path

import pytest

from luzia import banco, entregas, jogo, privacy, server

DDD = 'Domain-Driven Design (DDD)'


def _semear(n):
    con = banco.conectar()
    try:
        with banco.transacao(con):
            for i in range(n):
                cur = con.execute(
                    "INSERT INTO entrega (chave, titulo, inicio, fim, fonte, commits, arquivos, linhas, areas_json) "
                    "VALUES (?, ?, '2026-11-10T10:00:00', '2026-11-11T15:00:00', 'merge-pr', 2, 4, 90, '[]')",
                    (f'pr:{i}', f'Entrega de exemplo {i}'))
                con.execute('INSERT INTO entrega_prisma (entrega_id, prisma, termos_json) VALUES (?, ?, ?)',
                            (int(cur.lastrowid), DDD, '["aggregate"]'))
                con.execute("INSERT INTO leitura (alvo_tipo, alvo_id, texto, base_json, base_hash, modelo, criado_em) "
                            "VALUES ('entrega', ?, 'leitura de exemplo', '{}', 'antiga', 'm/x', '2026-11-12T10:00:00')",
                            (str(cur.lastrowid),))
    finally:
        con.close()


def test_estado_calcula_cada_entrega_uma_vez(privado, monkeypatch):
    _semear(4)
    chamadas = {'propriedade': 0, 'avancos': 0}
    original_prop, original_av = entregas._propriedade_entrega, jogo.avancos

    def prop(*a, **k):
        chamadas['propriedade'] += 1
        return original_prop(*a, **k)

    def avancos(*a, **k):
        chamadas['avancos'] += 1
        return original_av(*a, **k)

    monkeypatch.setattr(entregas, '_propriedade_entrega', prop)
    monkeypatch.setattr(jogo, 'avancos', avancos)
    st = server.estado()
    assert len(st['entregas']) == 4
    assert chamadas['propriedade'] == 4, chamadas  # antes: 8 (o detalhe rodava de novo dentro da base da leitura)
    assert chamadas['avancos'] <= 8, chamadas      # uma lista de avanços compartilhada, não uma por entrega


def test_leitura_da_entrega_continua_vencendo_quando_a_base_muda(privado):
    """A base reaproveitada não pode esconder mudança: o hash da leitura segue o mesmo de antes da otimização."""
    from luzia import leituras
    _semear(1)
    con = banco.conectar()
    try:
        antes = leituras.hash_base(leituras.base(con, 'entrega', '1'))
        det = entregas.detalhe(con, 1, incluir_leitura=False)
        assert leituras.hash_base(leituras.base(con, 'entrega', '1', det=det)) == antes
    finally:
        con.close()


def test_termos_so_sao_relidos_quando_o_arquivo_muda(privado, monkeypatch):
    termos = privado / 'termos.txt'
    termos.write_text('ProdutoZeta\n', encoding='utf-8')
    leituras_do_arquivo = []
    original = Path.read_text

    def espiao(self, *a, **k):
        if self.name == 'termos.txt':
            leituras_do_arquivo.append(1)
        return original(self, *a, **k)

    monkeypatch.setattr(Path, 'read_text', espiao)
    for _ in range(5):
        assert privacy.Redactor.from_file(termos).redact('usa ProdutoZeta aqui') == 'usa [EMPRESA/PRODUTO] aqui'
    assert len(leituras_do_arquivo) == 1
    termos.write_text('ProdutoZeta\nOutroNome\n', encoding='utf-8')
    os.utime(termos, ns=(1, 2_000_000_000_000_000_000))  # garante um mtime diferente mesmo em disco com resolução grossa
    assert privacy.Redactor.from_file(termos).redact('fala OutroNome') == 'fala [EMPRESA/PRODUTO]'
    assert len(leituras_do_arquivo) == 2
    termos.unlink()
    assert privacy.Redactor.from_file(termos).redact('ProdutoZeta') == 'ProdutoZeta'  # sem arquivo, sem termos


def test_update_state_nao_perde_campos_de_escritas_simultaneas(privado):
    """Ler, alterar e gravar o plano tem de acontecer numa transação só: ninguém sobrescreve o campo do outro."""
    import threading
    from luzia import pipeline
    pipeline.load_state()  # traz a foto para o banco antes da corrida
    n, barreira, erros = 8, threading.Barrier(8), []

    def escrever(i):
        try:
            barreira.wait(10)
            pipeline.update_state({f'campo_{i}': i}, {'quando': '2026-11-12T10:00:00'})
        except Exception as e:  # pragma: no cover - o teste falha abaixo
            erros.append(e)

    ts = [threading.Thread(target=escrever, args=(i,)) for i in range(n)]
    [t.start() for t in ts]
    [t.join() for t in ts]
    assert not erros, erros
    plano = pipeline.load_state()['plano']
    assert [i for i in range(n) if plano.get(f'campo_{i}') != i] == []
