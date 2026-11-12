"""Entregas detectadas no histórico git local (só fatos, sem IA).

Uma entrega é um bloco semântico fechado de commits da pessoa:
1. merge de PR (`Merged PR <n>: <título>` ou `Merge pull request #<n> from <branch>`): os commits dela em
   `merge^1..merge^2`;
2. sem merge (squash, commits direto na principal): commits com o mesmo id de ticket (`AB#123` ou `#123`);
3. senão, 1 commit = 1 entrega.

Só entram commits cujo autor (nome ou e-mail) está nas identidades do perfil; a data é a data de autor.
LGPD: título e mensagem passam pelo `Redactor` antes de ir ao banco e nunca carregam número de PR/ticket nem hash;
esses ids ficam só em `entrega.ids_privados_json` e `commit_.hash` (banco privado).
"""

from __future__ import annotations

import hashlib
import json
import re
import sqlite3
import subprocess
from collections import Counter
from datetime import datetime, timedelta
from pathlib import Path

from . import arquivos, banco, trajetoria, triage
from .privacy import Redactor

SEP_REG, SEP_CAMPO = '\x1e', '\x1f'
FORMATO = f'--format=%x1e%H%x1f%P%x1f%an%x1f%ae%x1f%aI%x1f%B%x1f'
RE_MERGED_PR = re.compile(r'^Merged PR (\d+):\s*(.*)', re.IGNORECASE)
RE_GH_PR = re.compile(r'^Merge pull request #(\d+) from (\S+)', re.IGNORECASE)
RE_TICKET = re.compile(r'(?:AB)?#(\d+)')
RE_IDS = re.compile(r'(?:\bAB)?#\d+|\b(?:PR|Pull Request)\s*#?\d+', re.IGNORECASE)
MAX_MENSAGEM = 300
SOBREPOSICAO = timedelta(days=2)  # a busca incremental volta um pouco: datas de autor podem ficar para trás


# ------------------------------------------------------------------ identidades
def identidades(con: sqlite3.Connection) -> list[str]:
    """Nomes e e-mails que a pessoa usa no git (`perfil('identidades')`); a primeira carga vem de `entrada.json`."""
    guardadas = trajetoria.perfil_ler(con, 'identidades')
    if guardadas is not None:
        return [str(i) for i in guardadas]
    autor: list[str] = []
    try:
        cfg = json.loads((arquivos.PRIVATE / 'entrada.json').read_text(encoding='utf-8'))
        bruto = cfg.get('author')
        autor = [bruto] if isinstance(bruto, str) else list(bruto or [])
    except (OSError, ValueError):
        pass
    autor = [a.strip() for a in autor if isinstance(a, str) and a.strip()]
    if autor:
        with banco.transacao(con):
            trajetoria.perfil_gravar(con, 'identidades', autor)
    return autor


# ------------------------------------------------------------------ leitura do git
def _git(repo: Path, *args: str) -> str:
    return subprocess.run(['git', '-C', str(repo), '-c', 'core.quotepath=false', *args],
                          capture_output=True, text=True, encoding='utf-8', errors='replace', check=True).stdout


def _ler(repo: Path, *args: str, numstat: bool = True) -> list[dict]:
    """Registros do `git log` (um por commit, merges incluídos) com autor, data de autor e arquivos alterados."""
    saida = _git(repo, 'log', *(['--numstat', '--no-renames'] if numstat else []), FORMATO, *args)
    out = []
    for bloco in saida.split(SEP_REG)[1:]:
        campos = bloco.split(SEP_CAMPO)
        if len(campos) < 7:
            continue
        h, pais, nome, mail, quando, msg, resto = campos[:7]
        arqs: list[tuple[str, int]] = []
        for linha in resto.splitlines():
            partes = linha.split('\t')
            if len(partes) == 3:
                ins, dels, caminho = partes
                arqs.append((caminho, (int(ins) if ins.isdigit() else 0) + (int(dels) if dels.isdigit() else 0)))
        out.append({'hash': h, 'pais': pais.split(), 'nome': nome, 'mail': mail, 'data': quando[:19],
                    'mensagem': msg.strip(), 'arqs': arqs})
    return out


def _detalhar(repo: Path, regs: list[dict]) -> None:
    """Preenche `arqs` (arquivos e linhas) dos registros escolhidos, em lotes."""
    por_hash = {r['hash']: r for r in regs}
    hashes = list(por_hash)
    for i in range(0, len(hashes), 100):
        for d in _ler(repo, '--no-walk', *hashes[i:i + 100]):
            por_hash[d['hash']]['arqs'] = d['arqs']


def _meu(reg: dict, ids: set[str]) -> bool:
    return reg['nome'].strip().casefold() in ids or reg['mail'].strip().casefold() in ids


def _areas(caminhos: list[str]) -> list[str]:
    cont: Counter = Counter()
    for c in caminhos:
        ext = Path(c).suffix.lower()
        cont[triage.EXT_AREA.get(ext, ext or 'outro')] += 1
    return [a for a, _ in cont.most_common(4)]


def _commit(reg: dict) -> dict:
    caminhos = [c for c, _ in reg['arqs']]
    return {'hash': reg['hash'], 'data': reg['data'], 'mensagem': reg['mensagem'], 'arquivos': len(caminhos),
            'linhas': sum(n for _, n in reg['arqs']), 'areas': _areas(caminhos), 'caminhos': caminhos}


def _limpar(texto: str) -> str:
    """Tira números de PR/ticket do texto (eles só podem existir em `ids_privados`)."""
    texto = RE_IDS.sub('', texto)
    texto = re.sub(r'\(\s*\)', '', texto)
    return re.sub(r'[ \t]{2,}', ' ', texto).strip(' \t:-')


def _chave(prefixo: str, semente: str) -> str:
    return f'{prefixo}-{hashlib.sha1(semente.encode()).hexdigest()[:12]}'


def _entrega(chave: str, titulo: str, fonte: str, regs: list[dict], ids: list[str]) -> dict:
    regs = sorted(regs, key=lambda r: r['data'])
    ids_tk = [i for r in regs for i in RE_TICKET.findall(r['mensagem'])]
    return {'chave': chave, 'titulo': _limpar(titulo) or 'Entrega', 'inicio': regs[0]['data'], 'fim': regs[-1]['data'],
            'commits': [_commit(r) for r in regs], 'fonte': fonte,
            'ids_privados': list(dict.fromkeys(ids + (ids_tk if fonte == 'merge-pr' else [])))}


def _titulo_pr(assunto: str, corpo: str) -> tuple[str, str] | None:
    """(id, título) se o assunto é de merge de PR."""
    m = RE_MERGED_PR.match(assunto)
    if m:
        return m.group(1), m.group(2)
    m = RE_GH_PR.match(assunto)
    if m:
        titulo = corpo.strip().splitlines()[0] if corpo.strip() else m.group(2).split('/', 1)[-1].replace('-', ' ').replace('_', ' ')
        return m.group(1), titulo
    return None


def detectar(repo: Path, identidades: list[str], desde: str) -> list[dict]:
    """Entregas da pessoa desde `desde` (data ISO, por data de autor), das mais antigas às mais novas.

    Cada entrega: chave, titulo, inicio, fim, commits [{hash, data, mensagem, arquivos, linhas, areas, caminhos}],
    fonte ('merge-pr' | 'ticket' | 'commit') e ids_privados (números de PR/ticket, só para o banco privado).
    """
    meus = {i.strip().casefold() for i in identidades if i and i.strip()}
    if not meus:
        return []
    repo = Path(repo)
    # Sem `--since`: o git para de andar no primeiro commit velho e perde commits de data fora de ordem.
    todos = _ler(repo, '--all', numstat=False)
    resultado: list[dict] = []
    em_pr: set[str] = set()

    for reg in todos:
        if len(reg['pais']) < 2 or reg['data'] < desde:
            continue
        assunto, _, corpo = reg['mensagem'].partition('\n')
        pr = _titulo_pr(assunto.strip(), corpo)
        if not pr:
            continue
        numero, titulo = pr
        da_pessoa = [r for r in _ler(repo, f'{reg["pais"][0]}..{reg["pais"][1]}')
                     if len(r['pais']) < 2 and _meu(r, meus)]
        em_pr.update(r['hash'] for r in da_pessoa)
        if da_pessoa:
            resultado.append(_entrega(_chave('pr', reg['hash']), titulo, 'merge-pr', da_pessoa, [numero]))

    restantes = [r for r in todos if len(r['pais']) < 2 and r['hash'] not in em_pr
                 and r['data'] >= desde and _meu(r, meus)]
    _detalhar(repo, restantes)
    por_ticket: dict[str, list[dict]] = {}
    for reg in restantes:
        achado = RE_TICKET.search(reg['mensagem'])
        if achado:
            por_ticket.setdefault(achado.group(1), []).append(reg)
        else:
            resultado.append(_entrega(_chave('cm', reg['hash']), reg['mensagem'].partition('\n')[0], 'commit',
                                      [reg], []))
    for ticket, regs in por_ticket.items():
        primeiro = min(regs, key=lambda r: r['data'])
        resultado.append(_entrega(_chave('tk', ticket), primeiro['mensagem'].partition('\n')[0], 'ticket', regs,
                                  [ticket]))
    return sorted(resultado, key=lambda e: (e['inicio'], e['chave']))


# ------------------------------------------------------------------ prismas atravessados
def termos_do_prisma(palavras: list[str], textos: list[str]) -> list[str]:
    """Palavras do prisma achadas nos textos (sem diferenciar maiúsculas; mesma borda de `observer.detectar`)."""
    achadas = []
    for w in palavras:
        if w and len(w) >= 3 and any(re.search(r'(?<![A-Za-z])' + re.escape(w), t, re.IGNORECASE) for t in textos):
            achadas.append(w)
    return achadas


def prismas_de(entrega: dict, prismas: list[dict]) -> dict[str, list[str]]:
    textos = [t for c in entrega['commits'] for t in (c['mensagem'], *c['caminhos'])]
    achados = {p['nome']: termos_do_prisma(p['palavras'], textos) for p in prismas}
    return {nome: termos for nome, termos in achados.items() if termos}


# ------------------------------------------------------------------ gravação
def _redator(repo: Path, minhas: list[str]) -> Redactor:
    try:
        colegas = triage.repo_authors(repo)
    except (OSError, subprocess.CalledProcessError):
        colegas = []
    tokens = {t.casefold() for i in minhas for t in [i, *i.split()]}
    return Redactor.from_file(arquivos.PRIVATE / 'termos.txt',
                              extra_colleagues=[c for c in colegas if c.casefold() not in tokens])


def _repo_configurado() -> Path | None:
    try:
        cfg = json.loads((arquivos.PRIVATE / 'entrada.json').read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return None
    repo = Path(cfg['repo']) if cfg.get('repo') else None
    return repo if repo and repo.exists() else None


def atualizar(con: sqlite3.Connection, dias: int = 90) -> dict:
    """Detecta e grava as entregas. Primeira execução: últimos `dias`; depois só o que é novo.

    Pedir mais `dias` que a janela guardada (`perfil('entregas_desde')`) alarga a janela para trás.
    Retorna {'novas': entregas criadas, 'atualizadas': entregas que ganharam commits}.
    """
    resultado = {'novas': 0, 'atualizadas': 0}
    repo = _repo_configurado()
    minhas = identidades(con)
    if repo is None or not minhas:
        return resultado
    agora = datetime.now().replace(microsecond=0)
    alvo = agora - timedelta(days=dias)
    janela = trajetoria.perfil_ler(con, 'entregas_desde')
    if janela and janela.get('desde') and janela.get('ultima') and alvo.isoformat() >= janela['desde']:
        busca = datetime.fromisoformat(janela['ultima']) - SOBREPOSICAO
        desde_gravado = janela['desde']
    else:
        busca, desde_gravado = alvo, alvo.isoformat()
    achadas = detectar(repo, minhas, busca.isoformat(timespec='seconds'))
    redator = _redator(repo, minhas)
    prismas = trajetoria.prismas(con)

    with banco.transacao(con):
        for e in achadas:
            linha = con.execute('SELECT id FROM entrega WHERE chave = ?', (e['chave'],)).fetchone()
            novos = 0
            if linha is None:
                cur = con.execute("INSERT INTO entrega (chave, titulo, fonte) VALUES (?, ?, ?)",
                                  (e['chave'], redator.redact(e['titulo']), e['fonte']))
                eid = cur.lastrowid
            else:
                eid = linha['id']
            for c in e['commits']:
                antes = con.execute('SELECT entrega_id FROM commit_ WHERE hash = ?', (c['hash'],)).fetchone()
                if antes is None or antes['entrega_id'] != eid:
                    novos += 1
                    if antes is not None and antes['entrega_id'] is not None:
                        _recalcular(con, antes['entrega_id'])  # saiu de outra entrega (ex.: o PR chegou depois)
                msg = redator.redact(_limpar(c['mensagem']))[:MAX_MENSAGEM]
                con.execute(
                    'INSERT INTO commit_ (hash, entrega_id, data, mensagem, arquivos, linhas, areas_json) '
                    'VALUES (?, ?, ?, ?, ?, ?, ?) ON CONFLICT (hash) DO UPDATE SET entrega_id = excluded.entrega_id',
                    (c['hash'], eid, c['data'], msg, c['arquivos'], c['linhas'], json.dumps(c['areas'], ensure_ascii=False)))
            ids_antes = json.loads(con.execute('SELECT ids_privados_json FROM entrega WHERE id = ?', (eid,)).fetchone()[0])
            ids = list(dict.fromkeys(ids_antes + e['ids_privados']))
            con.execute('UPDATE entrega SET ids_privados_json = ? WHERE id = ?', (json.dumps(ids), eid))
            _recalcular(con, eid)
            for nome, termos in prismas_de(e, prismas).items():
                velho = con.execute('SELECT termos_json FROM entrega_prisma WHERE entrega_id = ? AND prisma = ?',
                                    (eid, nome)).fetchone()
                uniao = list(dict.fromkeys((json.loads(velho[0]) if velho else []) + termos))
                con.execute('INSERT INTO entrega_prisma (entrega_id, prisma, termos_json) VALUES (?, ?, ?) '
                            'ON CONFLICT (entrega_id, prisma) DO UPDATE SET termos_json = excluded.termos_json',
                            (eid, nome, json.dumps(uniao, ensure_ascii=False)))
            if linha is None:
                resultado['novas'] += 1
            elif novos:
                resultado['atualizadas'] += 1
        trajetoria.perfil_gravar(con, 'entregas_desde', {'desde': desde_gravado, 'ultima': agora.isoformat()})
    return resultado


def _recalcular(con: sqlite3.Connection, eid: int) -> None:
    """Totais da entrega a partir dos commits gravados; entrega sem commits some."""
    linhas = con.execute('SELECT data, arquivos, linhas, areas_json FROM commit_ WHERE entrega_id = ?', (eid,)).fetchall()
    if not linhas:
        con.execute('DELETE FROM entrega_prisma WHERE entrega_id = ?', (eid,))
        con.execute('DELETE FROM entrega WHERE id = ?', (eid,))
        return
    areas: Counter = Counter()
    for r in linhas:
        areas.update(json.loads(r['areas_json']))
    datas = sorted(r['data'] for r in linhas)
    con.execute('UPDATE entrega SET inicio = ?, fim = ?, commits = ?, arquivos = ?, linhas = ?, areas_json = ? '
                'WHERE id = ?',
                (datas[0], datas[-1], len(linhas), sum(r['arquivos'] for r in linhas), sum(r['linhas'] for r in linhas),
                 json.dumps([a for a, _ in areas.most_common(4)], ensure_ascii=False), eid))
