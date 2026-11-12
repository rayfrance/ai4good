"""Escrita do hook (`banco.gravar_ou_pendurar`): nunca trava a sessão e nenhum evento se perde.

Banco travado (ou que não abre) → o evento vai para `private/pendentes.jsonl`; a próxima `transacao` o absorve,
uma única vez, e só esvazia o arquivo depois do COMMIT. Tudo roda na fixture `privado`.
"""

import json
import multiprocessing
import os
import sqlite3
import time
from pathlib import Path

import pytest

from luzia import banco, migrar

LUMEN = {'quando': '2026-11-12T10:00:00', 'prisma': 'Prisma DDD', 'lm': 10, 'luz': 'refletida',
         'fonte': 'observer', 'ref': 'sessao-1'}


def _linhas_no_disco(pasta: Path) -> list[dict]:
    """Toda linha pendente ainda guardada: o arquivo do hook e os que uma absorção reservou e não apagou."""
    linhas = []
    for arq in sorted(pasta.glob('pendentes*')):
        linhas += [json.loads(l) for l in arq.read_text(encoding='utf-8').splitlines() if l.strip()]
    return linhas


def _lumens(con) -> list[tuple]:
    return [tuple(r) for r in con.execute('SELECT prisma, lm, luz, fonte, ref, quando FROM lumen ORDER BY id')]


@pytest.fixture
def travado(privado):
    """Banco pronto e outra conexão segurando `BEGIN EXCLUSIVE` (devolve a conexão de trabalho e a que trava)."""
    con = banco.conectar()
    outra = sqlite3.connect(banco.caminho(), isolation_level=None)
    outra.execute('BEGIN EXCLUSIVE')
    yield con, outra
    if outra.in_transaction:
        outra.rollback()
    outra.close()
    con.close()


def test_travado_vai_para_pendentes(privado, travado):
    inicio = time.monotonic()
    assert banco.gravar_ou_pendurar('lumen', dict(LUMEN)) is False
    assert time.monotonic() - inicio < 2
    linhas = (privado / 'pendentes.jsonl').read_text(encoding='utf-8').splitlines()
    assert len(linhas) == 1
    linha = json.loads(linhas[0])
    assert set(linha) == {'operacao', 'dados', 'quando'}
    assert linha['operacao'] == 'lumen' and linha['dados'] == LUMEN


def test_absorve_na_proxima_escrita(privado, travado):
    con, outra = travado
    assert banco.gravar_ou_pendurar('lumen', dict(LUMEN)) is False
    outra.rollback()  # solta a trava
    with banco.transacao(con):
        pass
    assert _lumens(con) == [('Prisma DDD', 10, 'refletida', 'observer', 'sessao-1', '2026-11-12T10:00:00')]
    pendentes = privado / 'pendentes.jsonl'
    assert not pendentes.exists() or pendentes.read_text(encoding='utf-8') == ''
    assert _linhas_no_disco(privado) == []


def test_livre_grava_direto(privado):
    banco.conectar().close()
    assert banco.gravar_ou_pendurar('sessao_evento', {'quando': '2026-11-12T10:00:00', 'sessao': 's1',
                                                      'prisma': 'Prisma DDD', 'extensao': '.py', 'ferramenta': 'Edit',
                                                      'modo': 'ativo', 'lm': 10, 'luz': 'refletida',
                                                      'interveio': 1}) is True
    assert banco.gravar_ou_pendurar('lampejo', {'prisma': 'Prisma DDD', 'sessao': 's1'}) is True
    con = banco.conectar()
    assert con.execute('SELECT COUNT(*) FROM sessao_evento').fetchone()[0] == 1
    lampejo = con.execute('SELECT prisma, estado, quando FROM lampejo').fetchone()
    assert lampejo['prisma'] == 'Prisma DDD' and lampejo['estado'] == 'aberto' and lampejo['quando']
    assert _linhas_no_disco(privado) == []


def test_rollback_mantem_pendentes(privado, travado):
    con, outra = travado
    assert banco.gravar_ou_pendurar('lumen', dict(LUMEN)) is False
    outra.rollback()
    with pytest.raises(RuntimeError):
        with banco.transacao(con):
            raise RuntimeError('falha no meio da escrita')
    assert _lumens(con) == []
    assert [l['dados'] for l in _linhas_no_disco(privado)] == [LUMEN]  # o evento continua guardado
    with banco.transacao(con):
        pass
    with banco.transacao(con):
        pass
    assert len(_lumens(con)) == 1
    assert _linhas_no_disco(privado) == []


def test_commit_sem_apagar_nao_aplica_duas_vezes(privado, travado, monkeypatch):
    """O processo pode morrer entre o COMMIT e apagar o arquivo: a próxima absorção não repete as linhas."""
    con, outra = travado
    assert banco.gravar_ou_pendurar('lumen', dict(LUMEN)) is False
    outra.rollback()
    with monkeypatch.context() as m:
        m.setattr(banco, '_apagar', lambda arquivos: None)
        with banco.transacao(con):
            pass
    assert len(_lumens(con)) == 1
    assert _linhas_no_disco(privado)  # o arquivo reservado ficou para trás
    with banco.transacao(con):
        pass
    assert len(_lumens(con)) == 1
    assert _linhas_no_disco(privado) == []


def test_ordem_e_linhas_ruins(privado, travado):
    con, outra = travado
    for i in range(3):
        assert banco.gravar_ou_pendurar('lumen', {**LUMEN, 'ref': f'r{i}'}) is False
    with (privado / 'pendentes.jsonl').open('a', encoding='utf-8') as f:
        f.write('{"operacao": "lumen", "dados": {"prisma": \n')  # linha cortada
        f.write(json.dumps({'operacao': 'apagar_tudo', 'dados': {}, 'quando': 'x'}) + '\n')
        f.write(json.dumps({'operacao': 'lumen', 'dados': {**LUMEN, 'luz': 'outra'}, 'quando': 'x'}) + '\n')
        f.write(json.dumps({'operacao': 'lumen', 'dados': {**LUMEN, 'coluna_estranha': 1}, 'quando': 'x'}) + '\n')
    outra.rollback()
    with banco.transacao(con):
        pass
    assert [r[4] for r in _lumens(con)] == ['r0', 'r1', 'r2']
    assert _linhas_no_disco(privado) == []
    erros = (privado / 'erros.log').read_text(encoding='utf-8')
    assert 'banco.absorver_pendentes' in erros
    assert 'apagar_tudo' not in erros and 'Prisma' not in erros  # só o tipo do problema, nunca o conteúdo


def test_operacao_desconhecida_levanta(privado):
    with pytest.raises(ValueError):
        banco.gravar_ou_pendurar('avanco', {'id': 'x'})
    with pytest.raises(ValueError):
        banco.gravar_ou_pendurar('lumen', {**LUMEN, 'coluna_estranha': 1})
    assert _linhas_no_disco(privado) == []


def test_migracao_que_falha_vai_para_pendentes(privado, monkeypatch):
    def quebrar(con, pasta=None):
        raise KeyError('formato antigo inesperado')

    with monkeypatch.context() as m:
        m.setattr(migrar, 'migrar', quebrar)
        assert banco.gravar_ou_pendurar('lumen', dict(LUMEN)) is False
    # A migração ficou bloqueada para este código: o hook continua pendurando, sem levantar.
    assert (privado / banco.MIGRACAO_FALHOU).exists()
    assert banco.gravar_ou_pendurar('lumen', {**LUMEN, 'ref': 'sessao-2'}) is False
    assert [l['dados']['ref'] for l in _linhas_no_disco(privado)] == ['sessao-1', 'sessao-2']
    (privado / banco.MIGRACAO_FALHOU).unlink()  # corrigido: apagar a marca libera a nova tentativa
    con = banco.conectar()
    with banco.transacao(con):
        pass
    assert len(_lumens(con)) == 2
    assert _linhas_no_disco(privado) == []


def _escrever_varios(arquivo_privado: str, quem: int, largada) -> None:
    """Roda num processo filho (spawn): grava 25 lúmens pelo caminho do hook, cada um com ref única."""
    largada.wait(timeout=60)
    for i in range(25):
        banco.gravar_ou_pendurar('lumen', {**LUMEN, 'ref': f'{quem}-{i}'})
        time.sleep(0.02)


def _travar_em_rajadas(arquivo: str, largada) -> None:
    """Roda num processo filho (spawn): segura o banco além do tempo curto do hook, três vezes."""
    con = sqlite3.connect(arquivo, isolation_level=None)
    largada.wait(timeout=60)
    for _ in range(3):
        con.execute('BEGIN IMMEDIATE')
        time.sleep(1.8)
        con.commit()
        time.sleep(0.3)
    con.close()


def test_concorrencia_nada_some_nada_duplica(privado):
    banco.conectar().close()
    ctx = multiprocessing.get_context('spawn')
    largada = ctx.Event()
    procs = [ctx.Process(target=_escrever_varios, args=(str(privado), quem, largada)) for quem in range(3)]
    procs.append(ctx.Process(target=_travar_em_rajadas, args=(str(banco.caminho()), largada)))
    for p in procs:
        p.start()
    largada.set()
    for p in procs:
        p.join(timeout=120)
    vivos = [p for p in procs if p.is_alive()]
    for p in vivos:
        p.terminate()
    assert not vivos and [p.exitcode for p in procs] == [0] * len(procs)
    erros = (privado / 'erros.log').read_text(encoding='utf-8')
    assert 'banco.gravar_ou_pendurar' in erros  # as rajadas travaram de fato: parte dos eventos passou pelos pendentes
    con = banco.conectar()
    with banco.transacao(con):
        pass
    refs = [r[4] for r in _lumens(con)]
    assert sorted(refs) == sorted(f'{q}-{i}' for q in range(3) for i in range(25))
    assert _linhas_no_disco(privado) == []


def test_absorver_de_novo_na_mesma_transacao_e_desfazer(privado, travado):
    """Uma segunda absorção no mesmo bloco não apaga o que a primeira marcou: se a transação desfizer, nada some."""
    con, outra = travado
    assert banco.gravar_ou_pendurar('lumen', dict(LUMEN)) is False
    outra.rollback()
    with pytest.raises(RuntimeError):
        with banco.transacao(con):
            assert banco.absorver_pendentes(con) == 0  # o início da transacao já aplicou a linha
            raise RuntimeError('falha depois da absorção')
    assert _lumens(con) == []
    assert [l['dados'] for l in _linhas_no_disco(privado)] == [LUMEN]
    with banco.transacao(con):
        pass
    assert len(_lumens(con)) == 1
    assert _linhas_no_disco(privado) == []


def test_absorver_de_novo_na_mesma_transacao_e_confirmar(privado, travado):
    con, outra = travado
    assert banco.gravar_ou_pendurar('lumen', dict(LUMEN)) is False
    outra.rollback()
    with banco.transacao(con):
        assert banco.absorver_pendentes(con) == 0
    assert len(_lumens(con)) == 1
    assert _linhas_no_disco(privado) == []  # apagados depois do COMMIT
    with banco.transacao(con):
        pass
    assert len(_lumens(con)) == 1


@pytest.mark.parametrize('operacao, dados', [
    ('lumen', {k: v for k, v in LUMEN.items() if k != 'prisma'}),
    ('lumen', {**LUMEN, 'lm': None}),
    ('lumen', {k: v for k, v in LUMEN.items() if k != 'fonte'}),
    ('lumen', {**LUMEN, 'luz': 'outra'}),
    ('lampejo', {'sessao': 's1'}),
    ('lampejo', {'prisma': 'Prisma DDD', 'estado': 'apagado'}),
    ('sessao_evento', {'sessao': 's1', 'luz': 'outra'}),
])
def test_dados_invalidos_levantam(privado, operacao, dados):
    banco.conectar().close()
    with pytest.raises(ValueError):
        banco.gravar_ou_pendurar(operacao, dados)
    assert _linhas_no_disco(privado) == []


APPENDS_POR_PROCESSO = 500


def _pendurar_muitos(arquivo: str, quem: int, largada) -> None:
    """Roda num processo filho (spawn): acrescenta APPENDS_POR_PROCESSO linhas no mesmo arquivo, sem pausa."""
    largada.wait(timeout=60)
    for i in range(APPENDS_POR_PROCESSO):
        banco._pendurar(Path(arquivo), 'lumen', {**LUMEN, 'ref': f'{quem}-{i}'}, '2026-11-12T10:00:00')


def test_acrescimos_simultaneos_nao_se_sobrepoem(privado):
    """Quatro processos acrescentando no mesmo pendentes.jsonl: toda linha inteira, nenhuma some (sem depender de tempo)."""
    arquivo = privado / banco.PENDENTES
    ctx = multiprocessing.get_context('spawn')
    largada = ctx.Event()
    procs = [ctx.Process(target=_pendurar_muitos, args=(str(arquivo), quem, largada)) for quem in range(4)]
    for p in procs:
        p.start()
    largada.set()
    for p in procs:
        p.join(timeout=120)
    vivos = [p for p in procs if p.is_alive()]
    for p in vivos:
        p.terminate()
    assert not vivos and [p.exitcode for p in procs] == [0] * len(procs)
    linhas = [l for l in arquivo.read_text(encoding='utf-8').split('\n') if l]
    refs = [json.loads(l)['dados']['ref'] for l in linhas]  # toda linha precisa ser JSON inteiro
    assert sorted(refs) == sorted(f'{q}-{i}' for q in range(4) for i in range(APPENDS_POR_PROCESSO))


def test_trava_presa_vai_para_arquivo_proprio(privado, monkeypatch):
    """Se a trava do acréscimo não sai no prazo, o evento vai para um arquivo próprio que a absorção aplica."""
    banco.conectar().close()
    arquivo = privado / banco.PENDENTES
    monkeypatch.setattr(banco, 'ESPERA_PENDURAR_S', 0.05)
    fd = os.open(arquivo, os.O_WRONLY | os.O_APPEND | os.O_CREAT | getattr(os, 'O_BINARY', 0))
    try:
        assert banco._travar(fd, time.monotonic() + 1)  # outro "processo" segurando a trava
        banco._pendurar(arquivo, 'lumen', dict(LUMEN), '2026-11-12T10:00:00')
        banco._destravar(fd)
    finally:
        os.close(fd)
    assert arquivo.read_bytes() == b''
    proprios = list(privado.glob('pendentes-*.absorvendo'))
    assert len(proprios) == 1 and [l['dados'] for l in _linhas_no_disco(privado)] == [LUMEN]
    con = banco.conectar()
    with banco.transacao(con):
        pass
    assert len(_lumens(con)) == 1
    assert _linhas_no_disco(privado) == []
