"""Entregas detectadas no histórico git local (só fatos, sem IA).

Uma entrega é um bloco semântico fechado de commits da pessoa:
1. merge de PR (`Merged PR <n>: <título>` ou `Merge pull request #<n> from <branch>`): os commits dela em
   `merge^1..merge^2`;
2. sem merge (squash, commits direto na principal): commits com o mesmo id de ticket (`AB#123` ou `#123`);
3. senão, 1 commit = 1 entrega.

Só entram commits cujo autor casa com uma identidade da pessoa (`casa_identidade`); a data é a data de autor.
LGPD: título e mensagem passam pelo `Redactor` antes de ir ao banco e nunca carregam número de PR/ticket nem hash;
esses ids ficam só em `entrega.ids_privados_json` e `commit_.hash` (banco privado).
"""

from __future__ import annotations

import hashlib
import json
import re
import sqlite3
import subprocess
import unicodedata
from collections import Counter
from datetime import datetime, timedelta
from pathlib import Path

from . import arquivos, banco, jogo, propriedade, trajetoria, triage
from .privacy import Redactor

SEP_REG, SEP_CAMPO = '\x1e', '\x1f'
FORMATO = '--format=%x1e%H%x1f%P%x1f%an%x1f%ae%x1f%aI%x1f%B%x1f'
RE_MERGED_PR = re.compile(r'^Merged PR (\d+):\s*(.*)', re.IGNORECASE)
RE_GH_PR = re.compile(r'^Merge pull request #(\d+) from (\S+)', re.IGNORECASE)
RE_TICKET = re.compile(r'(?<![\w#])(?:AB)?#(\d+)')
RE_IDS = re.compile(r'(?<![\w#])(?:AB)?#\d+|\b(?:PR|Pull Request)\s*#?\d+', re.IGNORECASE)
RE_CHAVE_TICKET = re.compile(r'(?<![A-Za-z0-9])[A-Z][A-Z0-9]{1,9}-\d+(?![A-Za-z0-9])')  # ABC-1234
PREFIXOS_DE_RAMO = {'feature', 'feat', 'fix', 'bugfix', 'hotfix', 'chore', 'refactor', 'release'}
MAX_MENSAGEM = 300
IGNORADOS = {'node_modules', 'vendor', '.venv', 'venv', 'dist', 'bin', 'obj', 'packages'}
LOCKS = {'package-lock.json', 'yarn.lock', 'pnpm-lock.yaml', 'poetry.lock', 'composer.lock', 'gemfile.lock',
         'packages.lock.json', 'cargo.lock'}
SOBREPOSICAO = timedelta(days=2)  # a busca incremental volta um pouco: datas de autor podem ficar para trás


# ------------------------------------------------------------------ identidades
def _sem_acento(texto: str) -> str:
    return ''.join(c for c in unicodedata.normalize('NFKD', texto) if not unicodedata.combining(c)).casefold()


def _palavras(texto: str) -> list[str]:
    return re.findall(r'\w+', _sem_acento(texto or ''))


def casa_identidade(identidade: str, nome: str, mail: str) -> bool:
    """Uma identidade casa com o autor "Nome <email>" como no `git log --author`, mas sem falso positivo:
    com '@' é o e-mail exato (sem diferenciar maiúsculas); sem '@', toda palavra dela aparece no nome do autor
    (sem acento e sem diferenciar maiúsculas; palavra inteira, então 'Ana' não casa com 'Mariana')."""
    ident = (identidade or '').strip()
    if not ident:
        return False
    if '@' in ident:
        return ident.casefold() == (mail or '').strip().casefold()
    pal = _palavras(ident)
    return bool(pal) and set(pal) <= set(_palavras(nome))


def _git_config(repo: Path | None, chave: str) -> str:
    if repo is None:
        return ''
    try:
        return _git(repo, 'config', '--get', chave).strip()
    except (subprocess.CalledProcessError, OSError):
        return ''


def _entrada_autor() -> list[str]:
    try:
        cfg = json.loads((arquivos.PRIVATE / 'entrada.json').read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return []
    bruto = cfg.get('author') if isinstance(cfg, dict) else None
    return [bruto] if isinstance(bruto, str) else [a for a in (bruto or []) if isinstance(a, str)]


def identidades(con: sqlite3.Connection, repo: Path | None = None) -> list[str]:
    """Nomes e e-mails que a pessoa usa no git: `author` de `entrada.json`, `user.name` e `user.email` do git
    no repositório autorizado e as acrescentadas depois (`perfil('identidades')`). A união fica no perfil."""
    repo = repo if repo is not None else _repo_configurado()
    guardadas = trajetoria.perfil_ler(con, 'identidades')
    guardadas = [str(i) for i in guardadas] if isinstance(guardadas, list) else []
    candidatas = [*_entrada_autor(), _git_config(repo, 'user.name'), _git_config(repo, 'user.email'), *guardadas]
    out: list[str] = []
    vistas: set[str] = set()
    for i in candidatas:
        i = (i or '').strip()
        if i and i.casefold() not in vistas:
            vistas.add(i.casefold())
            out.append(i)
    if out and {i.casefold() for i in out} != {i.casefold() for i in guardadas}:
        with banco.transacao(con):
            trajetoria.perfil_gravar(con, 'identidades', out)
    return out


def acrescentar_identidade(con: sqlite3.Connection, identidade: str) -> list[str]:
    """Acrescenta um nome ou e-mail às identidades; a próxima leitura das entregas refaz a janela inteira."""
    ident = (identidade or '').strip()
    if not ident or len(ident) > 120:
        raise ValueError('informe um nome ou e-mail do git (até 120 caracteres)')
    atuais = identidades(con)
    if ident.casefold() not in {i.casefold() for i in atuais}:
        with banco.transacao(con):
            trajetoria.perfil_gravar(con, 'identidades', [*atuais, ident])
    return identidades(con)


def mascarar_identidade(identidade: str) -> str:
    """Para a tela: e-mail nunca aparece inteiro (nem o domínio, que pode ser o da empresa)."""
    ident = (identidade or '').strip()
    if '@' in ident:
        return (ident[:1] or '?') + '***@***'
    return ident


def _assinatura(repo: Path, ids: list[str]) -> str:
    """Hash do repositório e das identidades usadas numa leitura: se mudar, a janela inteira é lida de novo."""
    base = json.dumps([str(Path(repo).resolve()).casefold(), sorted({i.casefold() for i in ids})], ensure_ascii=False)
    return hashlib.sha1(base.encode('utf-8')).hexdigest()[:16]


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


def _principal(repo: Path) -> str:
    """Ramo principal: origin/HEAD, senão main/master/develop, senão HEAD. Entrega é bloco fechado (já integrado)."""
    try:
        ref = _git(repo, 'symbolic-ref', '--quiet', 'refs/remotes/origin/HEAD').strip()
        if ref:
            return ref
    except subprocess.CalledProcessError:
        pass
    for nome in ('main', 'master', 'develop'):
        try:
            _git(repo, 'rev-parse', '--verify', '--quiet', f'refs/heads/{nome}')
            return f'refs/heads/{nome}'
        except subprocess.CalledProcessError:
            continue
    return 'HEAD'


def _meu(reg: dict, ids: list[str]) -> bool:
    return any(casa_identidade(i, reg['nome'], reg['mail']) for i in ids)


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


RE_ITEM = re.compile(r'(?<![\w#])(?:user[ \t]+story|bug|task|pbi|feature|tarefa|item)[ \t]*#?[ \t]*(\d+)[ \t]*(?:[:\-–—][ \t]*)?',
                     re.IGNORECASE)
RE_NUMERO_ID = re.compile(r'(?<![\w#!])(?:(?:AB)?#|!)(\d+)|\b(?:PR|Pull Request)[ \t]*#?(\d+)|(?<![\w.,-])(\d{4,})(?![\w.,-])',
                          re.IGNORECASE)
RE_TAG_INICIAL = re.compile(r'^\s*(\[[^\]\n]{1,60}\])')


def tag_inicial(titulo: str) -> str | None:
    """A etiqueta entre colchetes no início ("[Módulo X] ..."): texto de produto, não id; o `Redactor` a mascara
    se o termo estiver em `termos.txt`."""
    m = RE_TAG_INICIAL.match(titulo or '')
    return m.group(1) if m else None


def limpar_ids(texto: str) -> tuple[str, list[str]]:
    """(texto sem referências a itens de trabalho, ids removidos sem repetição). Números pequenos que fazem parte
    do texto ("3 telas", "v2") ficam."""
    ids: list[str] = []

    def _item(m: re.Match) -> str:
        ids.append(m.group(1))
        return ''

    def _num(m: re.Match) -> str:
        ids.append(next(g for g in m.groups() if g))
        return ''

    texto = RE_ITEM.sub(_item, texto)
    texto = RE_NUMERO_ID.sub(_num, texto)
    texto = RE_CHAVE_TICKET.sub('', texto)
    texto = re.sub(r'\(\s*\)', '', texto)
    texto = re.sub(r'[ \t]{2,}', ' ', texto).strip(' \t:-')
    return texto, list(dict.fromkeys(ids))


def _limpar(texto: str) -> str:
    """Tira números de PR/ticket/item do texto (eles só podem existir em `ids_privados`)."""
    return limpar_ids(texto)[0]


def _chave(prefixo: str, semente: str) -> str:
    return f'{prefixo}-{hashlib.sha1(semente.encode()).hexdigest()[:12]}'


def _entrega(chave: str, titulo: str, fonte: str, regs: list[dict], ids: list[str]) -> dict:
    regs = sorted(regs, key=lambda r: r['data'])
    ids_tk = [i for r in regs for i in RE_TICKET.findall(r['mensagem'])]
    titulo, ids_titulo = limpar_ids(titulo)
    ids = ids + ids_titulo
    return {'chave': chave, 'titulo': titulo or 'Entrega', 'inicio': regs[0]['data'], 'fim': regs[-1]['data'],
            'commits': [_commit(r) for r in regs], 'fonte': fonte,
            'ids_privados': list(dict.fromkeys(ids + (ids_tk if fonte == 'merge-pr' else [])))}


def _titulo_do_ramo(ramo: str) -> str:
    """Título legível a partir do nome do ramo, sem a chave do ticket nem qualquer palavra com número."""
    nome = RE_CHAVE_TICKET.sub(' ', ramo.split('/', 1)[-1])
    palavras = nome.replace('-', ' ').replace('_', ' ').replace('/', ' ').split()
    palavras = [p for p in palavras if not any(c.isdigit() for c in p)]
    if palavras and palavras[0].lower() in PREFIXOS_DE_RAMO:
        palavras = palavras[1:]
    return ' '.join(palavras)


def _titulo_pr(assunto: str, corpo: str) -> tuple[str, str] | None:
    """(id, título) se o assunto é de merge de PR."""
    m = RE_MERGED_PR.match(assunto)
    if m:
        return m.group(1), m.group(2)
    m = RE_GH_PR.match(assunto)
    if m:
        titulo = corpo.strip().splitlines()[0] if corpo.strip() else _titulo_do_ramo(m.group(2))
        return m.group(1), titulo
    return None


def detectar(repo: Path, identidades: list[str], desde: str) -> list[dict]:
    """Entregas da pessoa desde `desde` (data ISO, por data de autor), das mais antigas às mais novas.

    Cada entrega: chave, titulo, inicio, fim, commits [{hash, data, mensagem, arquivos, linhas, areas, caminhos}],
    fonte ('merge-pr' | 'ticket' | 'commit') e ids_privados (números de PR/ticket, só para o banco privado).
    """
    meus = [i.strip() for i in identidades if i and i.strip()]
    if not meus:
        return []
    repo = Path(repo)
    # Sem `--since`: o git para de andar no primeiro commit velho e perde commits de data fora de ordem.
    todos = _ler(repo, _principal(repo), numstat=False)
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


def _ignorado(caminho: str) -> bool:
    partes = caminho.replace(chr(92), '/').lower().split('/')
    return bool(IGNORADOS & set(partes[:-1])) or partes[-1] in LOCKS or partes[-1].endswith('.lock')


def prismas_de(entrega: dict, prismas: list[dict]) -> dict[str, list[str]]:
    textos = [t for c in entrega['commits']
              for t in (c['mensagem'], *(p for p in c['caminhos'] if not _ignorado(p)))]
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


def _limpar_titulos_guardados(con: sqlite3.Connection, redator: Redactor) -> None:
    """Títulos já gravados por versões antigas ganham a limpeza de ids; os números vão para `ids_privados`."""
    for r in con.execute('SELECT id, titulo, ids_privados_json FROM entrega').fetchall():
        if not r['titulo']:
            continue
        limpo, ids = limpar_ids(r['titulo'])
        limpo = redator.redact(limpo or 'Entrega')
        if limpo == r['titulo'] and not ids:
            continue
        antes = json.loads(r['ids_privados_json'] or '[]')
        con.execute('UPDATE entrega SET titulo = ?, ids_privados_json = ? WHERE id = ?',
                    (limpo, json.dumps(list(dict.fromkeys(antes + ids))), r['id']))


def atualizar(con: sqlite3.Connection, dias: int = 90) -> dict:
    """Detecta e grava as entregas. Primeira execução: últimos `dias`; depois só o que é novo.

    Pedir mais `dias` que a janela guardada (`perfil('entregas_desde')`) alarga a janela para trás. A janela guarda o
    hash do repositório e das identidades e quantos commits da pessoa o banco tem: se o hash mudar ou nada tiver
    casado, a próxima leitura refaz a janela inteira (não só o que veio depois da última).
    Retorna {'novas': entregas criadas, 'atualizadas': entregas que ganharam commits}.
    """
    resultado = {'novas': 0, 'atualizadas': 0}
    repo = _repo_configurado()
    if repo is None:
        return resultado
    minhas = identidades(con, repo)
    if not minhas:
        return resultado
    agora = datetime.now().replace(microsecond=0)
    alvo = agora - timedelta(days=dias)
    assinatura = _assinatura(repo, minhas)
    janela = trajetoria.perfil_ler(con, 'entregas_desde') or {}
    janela = janela if isinstance(janela, dict) else {}
    incremental = bool(janela.get('desde') and janela.get('ultima') and alvo.isoformat() >= janela['desde']
                       and janela.get('identidades') == assinatura and int(janela.get('meus') or 0) > 0)
    if incremental:
        busca = datetime.fromisoformat(janela['ultima']) - SOBREPOSICAO
        desde_gravado = janela['desde']
    else:  # primeira leitura, janela maior, outra identidade ou nada casou da última vez: a janela inteira
        desde_gravado = min(alvo.isoformat(), janela['desde']) if janela.get('desde') else alvo.isoformat()
        busca = datetime.fromisoformat(desde_gravado)
    try:
        achadas = detectar(repo, minhas, busca.isoformat(timespec='seconds'))
    except (subprocess.CalledProcessError, OSError) as erro:  # não é repositório git, ou git ausente
        arquivos.registrar_erro('entregas.atualizar', erro)
        return {**resultado, 'aviso': 'não consegui ler o histórico git deste repositório'}
    redator = _redator(repo, minhas)
    prismas = trajetoria.prismas(con)

    with banco.transacao(con):
        _limpar_titulos_guardados(con, redator)
        tocadas: set[int] = set()
        antigas: dict[int, int] = {}
        for e in achadas:
            linha = con.execute('SELECT id FROM entrega WHERE chave = ?', (e['chave'],)).fetchone()
            novos = 0
            if linha is None:
                cur = con.execute("INSERT INTO entrega (chave, titulo, fonte) VALUES (?, ?, ?)",
                                  (e['chave'], redator.redact(e['titulo']), e['fonte']))
                eid = cur.lastrowid
            else:
                eid = linha['id']
                con.execute('UPDATE entrega SET titulo = ? WHERE id = ? AND titulo IS NOT ?',
                            (redator.redact(e['titulo']), eid, redator.redact(e['titulo'])))
            for c in e['commits']:
                antes = con.execute('SELECT entrega_id FROM commit_ WHERE hash = ?', (c['hash'],)).fetchone()
                if antes is None or antes['entrega_id'] != eid:
                    novos += 1
                    if antes is not None and antes['entrega_id'] not in (None, eid):
                        antigas[antes['entrega_id']] = eid  # saiu de outra entrega (ex.: o PR chegou depois)
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
                tocadas.add(eid)
        for velha, destino in antigas.items():  # só depois de todos os commits terem mudado de lugar
            if _recalcular(con, velha, destino=destino):
                tocadas.add(velha)
        resultado['atualizadas'] = len(tocadas)
        meus = int(con.execute('SELECT COUNT(*) FROM commit_').fetchone()[0])  # só há commits da pessoa
        trajetoria.perfil_gravar(con, 'entregas_desde', {'desde': desde_gravado, 'ultima': agora.isoformat(),
                                                         'identidades': assinatura, 'meus': meus})
    return resultado


def diagnostico(con: sqlite3.Connection) -> dict:
    """Por que não há entregas: repositório autorizado, identidades (e-mails mascarados) e a janela já lida."""
    repo = _repo_configurado()
    janela = trajetoria.perfil_ler(con, 'entregas_desde') or {}
    janela = janela if isinstance(janela, dict) else {}
    return {
        'repo_configurado': repo is not None,
        'identidades': [mascarar_identidade(i) for i in identidades(con, repo)],
        'janela_desde': str(janela.get('desde') or '')[:10],
        'ultima_leitura': str(janela.get('ultima') or '')[:10],
        'commits_seus': int(janela.get('meus') or 0),
    }


def _recalcular(con: sqlite3.Connection, eid: int, destino: int | None = None) -> bool:
    """Totais da entrega a partir dos commits gravados; entrega sem commits some (reapontando avanços)."""
    linhas = con.execute('SELECT data, arquivos, linhas, areas_json FROM commit_ WHERE entrega_id = ?', (eid,)).fetchall()
    if not linhas:
        con.execute('UPDATE avanco SET entrega_id = ? WHERE entrega_id = ?', (destino, eid))
        con.execute('DELETE FROM entrega_prisma WHERE entrega_id = ?', (eid,))
        con.execute('DELETE FROM entrega WHERE id = ?', (eid,))
        return False
    areas: Counter = Counter()
    for r in linhas:
        areas.update(json.loads(r['areas_json']))
    datas = sorted(r['data'] for r in linhas)
    con.execute('UPDATE entrega SET inicio = ?, fim = ?, commits = ?, arquivos = ?, linhas = ?, areas_json = ? '
                'WHERE id = ?',
                (datas[0], datas[-1], len(linhas), sum(r['arquivos'] for r in linhas), sum(r['linhas'] for r in linhas),
                 json.dumps([a for a, _ in areas.most_common(4)], ensure_ascii=False), eid))
    return True


# ------------------------------------------------------------------ ligação com o jogo (Tarefa 9)
def _duracao_dias(inicio: str | None, fim: str | None) -> int:
    if not inicio or not fim:
        return 0
    try:
        d_ini = datetime.fromisoformat(inicio[:19]).date()
        d_fim = datetime.fromisoformat(fim[:19]).date()
        return max(0, (d_fim - d_ini).days)
    except ValueError:
        return 0


def _fatos(r: sqlite3.Row) -> dict:
    try:
        areas = json.loads(r['areas_json'] or '[]')
    except ValueError:
        areas = []
    return {
        'inicio': r['inicio'] or '',
        'fim': r['fim'] or '',
        'duracao_dias': _duracao_dias(r['inicio'], r['fim']),
        'commits': int(r['commits'] or 0),
        'arquivos': int(r['arquivos'] or 0),
        'linhas': int(r['linhas'] or 0),
        'areas': areas,
    }


def _prismas_entrega(con: sqlite3.Connection, eid: int) -> list[dict]:
    out = []
    for r in con.execute('SELECT prisma, termos_json FROM entrega_prisma WHERE entrega_id = ? ORDER BY rowid', (eid,)):
        try:
            termos = json.loads(r['termos_json'] or '[]')
        except ValueError:
            termos = []
        out.append({'nome': r['prisma'], 'prisma': r['prisma'], 'termos': termos})
    return out


def _propriedade_entrega(con: sqlite3.Connection, r: sqlite3.Row, commits: list[dict], avancos_feitos: list[dict]) -> dict:
    plano = trajetoria.perfil_ler(con, 'plano') or {}
    p1 = plano.get('p1_direcao_prompt')
    dims: dict[str, dict | None] = {}
    if isinstance(p1, dict) and p1.get('nota') is not None:
        dims['P1'] = {'nota': int(p1['nota']), 'tipo': 'inferido · geral', 'base': p1.get('base', '')}
    else:
        dims['P1'] = None
    dims['P2'] = propriedade.p2_entrega(commits)

    por_id = {a['id']: a for a in avancos_feitos}
    alvos_legado = {x for x in (r['titulo'], str(r['id']), r['chave']) if x}
    for dim in ('P3', 'P4'):
        candidatos: list[dict] = []
        for a in avancos_feitos:
            if a.get('estado') == 'conquistado' and a.get('dimensao') == dim and a.get('nota') is not None:
                hist = a.get('historico') or []
                resumo = a.get('resumo') or next((h.get('resumo') for h in reversed(hist) if h.get('resumo')), '')
                quando = next((h.get('quando') for h in reversed(hist) if h.get('quando')), a.get('criado_em') or '')
                candidatos.append({'nota': int(a['nota']), 'resumo': resumo, 'quando': quando})
        for ev in con.execute("SELECT avanco_id, quando, nota, resumo, extra_json FROM avanco_evento "
                              "WHERE evento IN ('concluida', 'conquistado', 'revisitado') AND nota IS NOT NULL"):
            try:
                extra = json.loads(ev['extra_json'] or '{}')
            except ValueError:
                extra = {}
            extra = extra if isinstance(extra, dict) else {}
            av = por_id.get(ev['avanco_id'])
            dim_ev = extra.get('dimensao') or (av.get('dimensao') if av else None)
            if dim_ev != dim:
                continue
            if av is not None or extra.get('entrega') in alvos_legado:
                candidatos.append({'nota': int(ev['nota']), 'resumo': ev['resumo'] or '', 'quando': ev['quando'] or ''})
        if candidatos:
            melhor = max(candidatos, key=lambda c: int(c.get('nota', 0)))
            n = int(melhor.get('nota', 0))
            dims[dim] = {
                'nota': n * 25,
                'tipo': 'evidência',
                'base': f"{propriedade.RUBRICA.get(n, '')} — “{melhor.get('resumo', '')}” ({(melhor.get('quando') or '')[:10]})",
            }
        else:
            dims[dim] = None

    com_base = [d['nota'] for d in dims.values() if d]
    indice = round(sum(com_base) / len(com_base)) if com_base else None
    return {'dimensoes': dims, 'indice': indice, 'base': f'{len(com_base)} de 4 dimensões'}


def _lumens_ligados(con: sqlite3.Connection, r: sqlite3.Row, prismas_nomes: set[str], ids_avancos: set[str]) -> list[dict]:
    refs = {str(r['id']), r['chave'], *ids_avancos} | ({r['titulo']} if r['titulo'] else set())
    janela_ini = janela_fim = ''
    if r['inicio'] and r['fim']:
        try:
            janela_ini = (datetime.fromisoformat(r['inicio'][:19]).date() - timedelta(days=1)).isoformat()
            janela_fim = (datetime.fromisoformat(r['fim'][:19]).date() + timedelta(days=1)).isoformat() + 'T23:59:59'
        except ValueError:
            pass
    out = []
    for row in con.execute('SELECT id, quando, prisma, lm, luz, fonte, ref FROM lumen ORDER BY quando, id'):
        ref = row['ref'] or ''
        fonte = str(row['fonte'] or '')
        por_ref = bool(ref and ref in refs)
        por_janela = bool(
            row['prisma'] in prismas_nomes
            and (fonte.startswith('passivo') or fonte == 'conversao')
            and janela_ini and janela_ini <= (row['quando'] or '') <= janela_fim
        )
        if por_ref or por_janela:
            out.append({
                'id': row['id'], 'quando': row['quando'], 'prisma': row['prisma'], 'skill': row['prisma'],
                'lm': int(row['lm']), 'luz': row['luz'], 'fonte': fonte, 'ref': ref,
            })
    return out


def detalhe(con: sqlite3.Connection, entrega_id: int, incluir_leitura: bool = True,
            todos_avancos: list[dict] | None = None) -> dict | None:
    """Detalhe completo de uma entrega ligada ao jogo (sem hashes nem ids privados).

    `todos_avancos`: a lista de avanços já carregada por quem chama várias entregas de uma vez (evita recarregá-la em cada uma).
    """
    r = con.execute('SELECT * FROM entrega WHERE id = ?', (int(entrega_id),)).fetchone()
    if r is None:
        return None
    eid = int(r['id'])
    fatos = _fatos(r)
    prismas_lista = _prismas_entrega(con, eid)
    prismas_nomes = {p['nome'] for p in prismas_lista}

    commits = []
    for c in con.execute('SELECT data, mensagem, arquivos, linhas, areas_json FROM commit_ WHERE entrega_id = ? ORDER BY data, rowid', (eid,)):
        try:
            areas = json.loads(c['areas_json'] or '[]')
        except ValueError:
            areas = []
        commits.append({
            'data': c['data'], 'mensagem': c['mensagem'],
            'arquivos': int(c['arquivos'] or 0), 'linhas': int(c['linhas'] or 0), 'areas': areas,
        })

    todos_avancos = todos_avancos if todos_avancos is not None else jogo.avancos(con)
    avancos_feitos = [
        a for a in todos_avancos
        if a.get('entrega_id') == eid or (a.get('entrega_id') is None and r['titulo'] and a.get('entrega') == r['titulo'])
    ]
    ids_feitos = {a['id'] for a in avancos_feitos}
    avancos_uteis = [
        a for a in todos_avancos
        if a['id'] not in ids_feitos
        and a.get('estado') in ('em_andamento', 'na_fila', 'sugerido')
        and (a.get('skill_plano') or a.get('skill')) in prismas_nomes
    ][:3]

    lumens = _lumens_ligados(con, r, prismas_nomes, ids_feitos)
    prop = _propriedade_entrega(con, r, commits, avancos_feitos)

    det = {
        'id': eid,
        'titulo': r['titulo'] or 'Entrega',
        'fonte': r['fonte'],
        'inicio': fatos['inicio'],
        'fim': fatos['fim'],
        'fatos': fatos,
        'commits': commits,
        'prismas': prismas_lista,
        'avancos_feitos': avancos_feitos,
        'avancos_uteis': avancos_uteis,
        'lumens_ligados': lumens,
        'propriedade': prop,
        'leitura': None,
    }
    if incluir_leitura:  # a base da leitura reaproveita este detalhe, em vez de calculá-lo de novo
        from . import leituras
        det['leitura'] = leituras.obter(con, 'entrega', str(eid), atual=leituras.base(con, 'entrega', str(eid), det=det))
    return det


def listar(con: sqlite3.Connection) -> list[dict]:
    """Entregas mais recentes primeiro, com resumo dos fatos e prismas atravessados."""
    out = []
    for r in con.execute('SELECT * FROM entrega ORDER BY fim DESC, inicio DESC, id DESC'):
        eid = int(r['id'])
        fatos = _fatos(r)
        out.append({
            'id': eid,
            'titulo': r['titulo'] or 'Entrega',
            'fonte': r['fonte'],
            'inicio': fatos['inicio'],
            'fim': fatos['fim'],
            'fatos': fatos,
            'prismas': _prismas_entrega(con, eid),
        })
    return out
