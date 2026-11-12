"""Migração única dos JSON antigos para o banco: sem perder, sem duplicar e tudo ou nada.

Os dados vêm de `tests/dados/` (sintéticos, no formato que jogo.py, acoes.py, observer.py e pipeline.py gravam hoje)
e são copiados para a pasta temporária da fixture `privado`: `code/luzia/private/` nunca é aberta.
"""

import json
import shutil
import sqlite3
from collections import Counter
from datetime import datetime
from pathlib import Path

import pytest

from luzia import banco, migrar

DADOS = Path(__file__).parent / 'dados'
ARQUIVOS = ('feixes.json', 'lumens.jsonl', 'degraus.json', 'autoavaliacao.json', 'cartoes.json', 'evidencias.jsonl',
            'fila.json', 'acoes_guardadas.json', 'sessao.jsonl', 'career_state.json')
DDD, TST, FRONT = 'Domain-Driven Design (DDD)', 'Testes e Qualidade / SQL', 'Front-end (JS / Razor / React)'
MIGRADAS = ('perfil', 'prisma', 'trajetoria_versao', 'avanco', 'avanco_evento', 'lumen', 'nivel_registro', 'lampejo',
            'fila', 'sessao_evento')


@pytest.fixture
def antigos(privado) -> Path:
    """A pasta privada do teste com os 10 arquivos antigos sintéticos (o banco ainda não existe)."""
    assert sorted(p.name for p in DADOS.iterdir()) == sorted(ARQUIVOS)
    for nome in ARQUIVOS:
        shutil.copy2(DADOS / nome, privado / nome)
    assert not (privado / 'luzia.db').exists()
    return privado


def _contagens(con) -> dict[str, int]:
    return {t: con.execute(f'SELECT COUNT(*) FROM {t}').fetchone()[0] for t in MIGRADAS}


def test_totais_iguais(antigos):
    esperado = migrar.totais_json(antigos)
    # Os números conferidos à mão nos dados sintéticos (a linha cortada de lumens.jsonl fica de fora, como no jogo).
    assert esperado == {
        'lumens_total': 201, 'lumens_propria': 141,
        'avancos_por_estado': {'conquistado': 2, 'descartado': 1, 'em_andamento': 1, 'na_fila': 1, 'sugerido': 2},
        'niveis': {DDD: 2, TST: 3, FRONT: 3},
    }
    con = banco.conectar()
    assert migrar.totais_banco(con) == esperado

    # totais_banco lê o nível do livro; a coluna prisma.nivel tem de bater com ele.
    assert {r['nome']: r['nivel'] for r in con.execute('SELECT nome, nivel FROM prisma')} == esperado['niveis']
    # Só a subida que veio do histórico de degraus é "conquistado"; base e declaração têm a sua origem.
    regs = [tuple(r) for r in con.execute('SELECT prisma, de, para, origem FROM nivel_registro ORDER BY prisma, quando, id')]
    assert regs == [(DDD, None, 1, 'migrado'), (DDD, 1, 2, 'conquistado'), (FRONT, None, 3, 'migrado'),
                    (TST, None, 2, 'migrado'), (TST, 2, 3, 'declarado')]
    assert con.execute("SELECT ultimo_nivel_em FROM prisma WHERE nome = ?", (DDD,)).fetchone()[0] == '2026-11-05T13:00:00'
    assert con.execute("SELECT ultimo_nivel_em FROM prisma WHERE nome = ?", (TST,)).fetchone()[0] is None

    # Eventos de evidência com id fora do catálogo (cartão) continuam no livro de eventos, com seus atributos.
    ev = con.execute("SELECT nota, extra_json FROM avanco_evento WHERE avanco_id = 'a3a8' AND evento = 'concluida'").fetchone()
    assert ev['nota'] == 3 and json.loads(ev['extra_json']) == {'fonte': 'evidencias', 'skill': DDD, 'origem': 'cartao'}
    # A mesma conquista está no histórico do feixe e nas evidências: a fonte separa as duas (sem contar duas vezes).
    fontes = Counter(json.loads(r[0])['fonte'] for r in
                     con.execute("SELECT extra_json FROM avanco_evento WHERE avanco_id = '3fb7'"))
    assert fontes == {'historico': 4, 'evidencias': 2}
    guardada = con.execute("SELECT estado, origem, prisma FROM avanco WHERE id = 'f479'").fetchone()
    assert tuple(guardada) == ('sugerido', 'lampejo', TST)
    assert con.execute("SELECT origem FROM avanco WHERE id = 'c04e'").fetchone()[0] == 'lampejo'
    assert con.execute("SELECT prisma FROM avanco WHERE id = 'e1a0'").fetchone()[0] == DDD
    assert con.execute("SELECT revisita_aberta FROM avanco WHERE id = '3878'").fetchone()[0] == 1
    assert sorted(r[0] for r in con.execute('SELECT estado FROM lampejo')) == ['aberto', 'convertido', 'guardado']
    assert con.execute('SELECT oferecida_json FROM fila').fetchone()[0] == '["sessao03"]'
    assert con.execute('SELECT COUNT(*) FROM sessao_evento').fetchone()[0] == 4
    # O plano inteiro fica no perfil e a trajetória nasce na versão 1, da triagem.
    plano = json.loads(con.execute("SELECT valor_json FROM perfil WHERE chave = 'plano'").fetchone()[0])
    assert plano == json.loads((antigos / 'career_state.json').read_text(encoding='utf-8'))['plano']
    assert json.loads(con.execute("SELECT valor_json FROM perfil WHERE chave = 'rotulos'").fetchone()[0]) == {
        'onde_esta': 'Júnior 3', 'aonde_quer_chegar': 'Plena'}
    versao = con.execute('SELECT numero, origem FROM trajetoria_versao').fetchall()
    assert [tuple(v) for v in versao] == [(1, 'triagem')]
    palavras = json.loads(con.execute('SELECT palavras_json FROM prisma WHERE nome = ?', (DDD,)).fetchone()[0])
    assert palavras[:2] == ['Aggregate', 'ValueObject'] and 'agregado' in palavras
    con.close()


def test_idempotente(antigos, tmp_path):
    con = banco.conectar()  # a primeira abertura migra
    antes = _contagens(con)
    assert all(antes[t] for t in MIGRADAS), antes
    migrar.migrar(con)  # de novo, fora de transação: abre a própria e não acrescenta nada
    assert _contagens(con) == antes and not con.in_transaction
    con.close()
    banco.conectar().close()

    # Num banco só com o esquema (sem a marca de banco.garantir), chamar duas vezes também não duplica.
    cru = sqlite3.connect(tmp_path / 'cru.db', isolation_level=None)
    for sql in banco.ESQUEMA:
        cru.execute(sql)
    # Marcado pelo stub antigo (migrado_em sem a marca 'migracao'): a migração ainda roda quando chamada.
    cru.execute("INSERT INTO meta (chave, valor) VALUES ('migrado_em', '2026-11-12T08:00:00')")
    primeira = migrar.migrar(cru)
    depois = _contagens(cru)
    segunda = migrar.migrar(cru)
    assert _contagens(cru) == depois == antes
    assert primeira['lumen'] == 8 and segunda == {t: 0 for t in primeira}
    cru.close()


def test_rollback(antigos, monkeypatch):
    def quebra(*_, **__):
        raise RuntimeError('falha simulada no meio da migração')

    monkeypatch.setattr(migrar, '_lampejos', quebra)  # depois de perfil, prismas, avanços, lúmens e níveis
    with pytest.raises(RuntimeError, match='migração bloqueada') as erro:
        banco.conectar()
    assert 'falha simulada' in str(erro.value.__cause__)
    cru = sqlite3.connect(antigos / 'luzia.db')
    tabelas = {r[0] for r in cru.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
    for t in set(MIGRADAS) & tabelas:
        assert cru.execute(f'SELECT COUNT(*) FROM {t}').fetchone()[0] == 0, t
    if 'meta' in tabelas:
        assert not cru.execute("SELECT 1 FROM meta WHERE chave IN ('migrado_em', 'migracao')").fetchone()
    cru.close()
    for nome in ARQUIVOS:  # os originais continuam lá, intactos
        assert (antigos / nome).read_bytes() == (DADOS / nome).read_bytes()
    copia = antigos / f"migracao-{datetime.now():%Y%m%d}"
    assert sorted(p.name for p in copia.iterdir()) == sorted(ARQUIVOS)  # a cópia sobrevive ao rollback

    monkeypatch.undo()
    (antigos / banco.MIGRACAO_FALHOU).unlink()  # corrigido: apagar a marca libera a nova tentativa
    con = banco.conectar()  # tenta de novo e migra tudo
    assert migrar.totais_banco(con) == migrar.totais_json(antigos)
    con.close()
    assert sorted(p.name for p in copia.iterdir()) == sorted(ARQUIVOS)  # sem cópias repetidas na nova tentativa


def _avisos(con) -> list[str]:
    return json.loads(con.execute("SELECT valor FROM meta WHERE chave = 'migracao'").fetchone()[0])['avisos']


def _reescrever(pasta: Path, nome: str, mudar) -> None:
    dados = json.loads((pasta / nome).read_text(encoding='utf-8'))
    (pasta / nome).write_text(json.dumps(mudar(dados) or dados, ensure_ascii=False), encoding='utf-8')


def _acrescentar(pasta: Path, nome: str, rec: dict) -> None:
    with (pasta / nome).open('a', encoding='utf-8') as f:
        f.write(json.dumps(rec, ensure_ascii=False) + '\n')


def test_dados_fora_do_formato_nao_derrubam(antigos):
    """Cada gatilho da revisão: o registro ou valor ruim é pulado/convertido com aviso e o resto migra."""
    # nível declarado que não é número (int('dois')) e skill sem 'nome' (KeyError)
    _reescrever(antigos, 'autoavaliacao.json', lambda a: {**a, DDD: 'dois'})

    def plano(st):
        skills = st['plano']['skills']
        skills[2]['palavras_chave'] = 'useState'  # texto em vez de lista (str + list)
        skills.append({'alvo': 4, 'luzia_sugere': 1})
    _reescrever(antigos, 'career_state.json', plano)

    def feixes(cat):  # lista e objeto onde a coluna espera um valor simples (ProgrammingError do sqlite)
        cat['dbe9']['titulo'] = {'texto': 'Escrever um teste'}
        cat['dbe9']['dimensao'] = ['p3']
        cat['4aad']['historico'] = {'quando': '2026-11-03T08:00:00'}
    _reescrever(antigos, 'feixes.json', feixes)
    _reescrever(antigos, 'cartoes.json', lambda c: c.append({'skill': DDD, 'sessao': {'id': 1}, 'quando': '2026-11-09'}))
    _reescrever(antigos, 'fila.json', lambda f: f.append({'id': {'x': 1}, 'quando': '2026-11-09'}))
    _reescrever(antigos, 'degraus.json', lambda g: g['historico'].append({'skill': ['DDD'], 'para': 3}))
    _acrescentar(antigos, 'lumens.jsonl', {'quando': '2026-11-09T10:00:00', 'skill': [DDD], 'lm': 5, 'luz': 'propria',
                                           'fonte': {'tipo': 'feixe'}})
    _acrescentar(antigos, 'sessao.jsonl', {'quando': '2026-11-09T10:00:00', 'sessao': 'sessao04', 'modo': ['ativo']})
    _acrescentar(antigos, 'evidencias.jsonl', {'quando': '2026-11-09T10:00:00', 'id': ['3fb7'], 'evento': 'concluida'})

    con = banco.conectar()  # não levanta
    assert con.execute("SELECT valor FROM meta WHERE chave = 'migrado_em'").fetchone()
    assert not (antigos / banco.MIGRACAO_FALHOU).exists()
    totais = migrar.totais_banco(con)
    assert totais == migrar.totais_json(antigos)
    assert totais['lumens_total'] == 206 and totais['niveis'][DDD] == 1  # 'dois' ignorado: vale o do plano
    assert {r[0] for r in con.execute('SELECT nome FROM prisma')} == {DDD, TST, FRONT}
    palavras = json.loads(con.execute('SELECT palavras_json FROM prisma WHERE nome = ?', (FRONT,)).fetchone()[0])
    assert palavras[0] == 'useState'
    feixe = con.execute("SELECT titulo, dimensao, conteudo_json FROM avanco WHERE id = 'dbe9'").fetchone()
    assert feixe['titulo'] is None and feixe['dimensao'] is None
    assert json.loads(feixe['conteudo_json'])['_fora_do_formato'] == {'titulo': {'texto': 'Escrever um teste'},
                                                                      'dimensao': ['p3']}
    assert con.execute("SELECT COUNT(*) FROM avanco_evento WHERE avanco_id = '4aad'").fetchone()[0] == 0
    assert con.execute("SELECT prisma, fonte FROM lumen WHERE lm = 5").fetchone()[:] == ('', '')
    assert con.execute("SELECT sessao FROM lampejo WHERE quando = '2026-11-09'").fetchone()[0] is None
    assert con.execute('SELECT COUNT(*) FROM fila').fetchone()[0] == 1
    assert con.execute("SELECT modo FROM sessao_evento WHERE sessao = 'sessao04'").fetchone()[0] is None
    avisos = _avisos(con)
    for trecho in ('autoavaliacao.json', 'sem nome', 'avanco: dimensao, titulo', 'histórico',
                   'lampejo: sessao', 'fila.json', 'subida sem skill', 'lumen: fonte, prisma', 'sessao_evento: modo',
                   'evidencias.jsonl'):
        assert any(trecho in a for a in avisos), (trecho, avisos)
    assert 'dois' not in json.dumps(avisos) and 'Escrever um teste' not in json.dumps(avisos)  # só campo e tipo
    con.close()


def test_falha_inesperada_bloqueia_sem_repetir(antigos, monkeypatch):
    """Erro inesperado: marca a falha, não tenta de novo a cada abertura e não multiplica o backup."""
    chamadas = []

    def quebra(*_, **__):
        chamadas.append(1)
        raise TypeError('erro inesperado')

    monkeypatch.setattr(migrar, '_perfil', quebra)
    for _ in range(3):
        with pytest.raises(RuntimeError, match=r'migração bloqueada.*erros\.log'):
            banco.conectar()
    assert len(chamadas) == 1  # só a primeira abertura tentou
    marca = json.loads((antigos / banco.MIGRACAO_FALHOU).read_text(encoding='utf-8'))
    assert marca['versao'] == migrar.versao() and marca['erro'] == 'TypeError'
    assert marca['onde'].startswith('migrar.py:') and set(marca) == {'versao', 'quando', 'erro', 'onde'}
    log = (antigos / 'erros.log').read_text(encoding='utf-8')
    assert 'banco.garantir migração (migrar.py:' in log and 'erro inesperado' not in log  # tipo e lugar, sem dado
    copia = antigos / f"migracao-{datetime.now():%Y%m%d}"
    assert sorted(p.name for p in copia.iterdir()) == sorted(ARQUIVOS)

    monkeypatch.setattr(migrar, 'versao', lambda: 'codigo-novo')  # o código da migração mudou: tenta de novo
    with pytest.raises(RuntimeError, match='migração bloqueada'):
        banco.conectar()
    assert len(chamadas) == 2
    assert json.loads((antigos / banco.MIGRACAO_FALHOU).read_text(encoding='utf-8'))['versao'] == 'codigo-novo'
    (antigos / banco.MIGRACAO_FALHOU).unlink()  # apagar a marca também libera
    with pytest.raises(RuntimeError, match='migração bloqueada'):
        banco.conectar()
    assert len(chamadas) == 3
    assert sorted(p.name for p in copia.iterdir()) == sorted(ARQUIVOS)  # originais iguais: nenhuma cópia nova
    assert sorted(p.name for p in antigos.glob('migracao-*') if p.is_dir()) == [copia.name]  # uma pasta por dia

    monkeypatch.undo()
    con = banco.conectar()  # a marca é de outro código: tenta, migra e apaga a marca
    assert migrar.totais_banco(con) == migrar.totais_json(antigos)
    assert not (antigos / banco.MIGRACAO_FALHOU).exists()
    con.close()


def test_trava_nao_bloqueia_a_migracao(antigos, monkeypatch):
    """Trava ou disco (`OperationalError`) não é defeito do código: nada de marca, a próxima abertura tenta."""
    def trava(*_, **__):
        raise sqlite3.OperationalError('database is locked')

    monkeypatch.setattr(migrar, '_perfil', trava)
    with pytest.raises(sqlite3.OperationalError):
        banco.conectar()
    assert not (antigos / banco.MIGRACAO_FALHOU).exists()
    monkeypatch.undo()
    banco.conectar().close()


def test_falha_de_disco_no_backup_nao_bloqueia(antigos, monkeypatch):
    """OSError ao copiar os originais (disco cheio, arquivo preso): como a trava, a próxima abertura tenta de novo."""
    def disco(*_, **__):
        raise OSError('disco cheio')

    monkeypatch.setattr(migrar, '_copiar_originais', disco)
    with pytest.raises(OSError):
        banco.conectar()
    assert not (antigos / banco.MIGRACAO_FALHOU).exists()
    monkeypatch.undo()
    con = banco.conectar()
    assert migrar.totais_banco(con) == migrar.totais_json(antigos)
    con.close()


def test_erro_de_programacao_nao_vira_aviso():
    """ProgrammingError/InterfaceError são defeitos do código: falham alto, nunca viram 'registro fora do formato'."""
    assert sqlite3.ProgrammingError not in migrar.RUINS
    assert sqlite3.InterfaceError not in migrar.RUINS
    d = {'avisos': []}
    with pytest.raises(sqlite3.ProgrammingError):
        with migrar._registro(d, 'teste'):
            raise sqlite3.ProgrammingError('SQL errado')
    assert d['avisos'] == []


def test_linha_cortada_no_meio_de_um_acento(antigos):
    """Gravação interrompida no meio de um caractere de 2 bytes: só aquela linha fica de fora."""
    with (antigos / 'lumens.jsonl').open('ab') as f:
        f.write('{"quando": "2026-11-09T10:00:00", "skill": "Gest'.encode('utf-8') + b'\xc3')
    with (antigos / 'sessao.jsonl').open('ab') as f:
        f.write(b'\xc3\n{"quando": "2026-11-09T10:00:00", "sessao": "sessao04"\n')
    con = banco.conectar()
    totais = migrar.totais_banco(con)
    assert totais == migrar.totais_json(antigos)
    assert (totais['lumens_total'], totais['lumens_propria']) == (201, 141)  # as 8 linhas boas
    assert con.execute('SELECT COUNT(*) FROM sessao_evento').fetchone()[0] == 4
    avisos = json.loads(con.execute("SELECT valor FROM meta WHERE chave = 'migracao'").fetchone()[0])['avisos']
    assert any(a.startswith('lumens.jsonl: 2 linha') for a in avisos), avisos
    assert any(a.startswith('sessao.jsonl: 2 linha') for a in avisos), avisos
    con.close()


def test_subida_depois_de_declarar(antigos):
    """Base 1, declarou 2 no painel, depois subiu para 3: a declaração não some e a subida é 2 → 3."""
    degraus = json.loads((antigos / 'degraus.json').read_text(encoding='utf-8'))
    degraus['base'][FRONT] = 1
    degraus['desde'][FRONT] = '2026-11-07T09:00:00'
    degraus['historico'].append({'quando': '2026-11-07T09:00:00', 'skill': FRONT, 'para': 3, 'lm': 150, 'luz_propria': 50})
    (antigos / 'degraus.json').write_text(json.dumps(degraus, ensure_ascii=False), encoding='utf-8')
    auto = json.loads((antigos / 'autoavaliacao.json').read_text(encoding='utf-8'))
    (antigos / 'autoavaliacao.json').write_text(json.dumps({**auto, FRONT: 3}, ensure_ascii=False), encoding='utf-8')
    con = banco.conectar()
    regs = [tuple(r) for r in con.execute('SELECT de, para, origem FROM nivel_registro WHERE prisma = ? '
                                          'ORDER BY quando, id', (FRONT,))]
    assert regs == [(None, 1, 'migrado'), (1, 2, 'declarado'), (2, 3, 'conquistado')]
    assert migrar.totais_banco(con)['niveis'][FRONT] == 3 == migrar.totais_json(antigos)['niveis'][FRONT]
    con.close()


def test_backup_criado(antigos):
    pasta = antigos / f"migracao-{datetime.now():%Y%m%d}"
    pasta.mkdir()  # sobra de uma tentativa anterior: não pode falhar
    banco.conectar().close()
    for nome in ARQUIVOS:
        assert (pasta / nome).read_bytes() == (DADOS / nome).read_bytes(), nome
        assert (antigos / nome).read_bytes() == (DADOS / nome).read_bytes(), nome  # nada apagado nem alterado
