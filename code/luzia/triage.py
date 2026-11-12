"""Triagem: coleta local das fontes de carreira e do histórico compartilhado entre IAs.

Fontes autorizadas pela pessoa desenvolvedora:
1. Declaração de nível atual, objetivo, horizonte e uso de IA;
2. Currículo (PDF ou texto) e LinkedIn exportado (PDF);
3. Perfil público do GitHub (`rayfrance`);
4. Histórico compartilhado entre as IAs utilizadas (Claude Code `~/.claude`,
   Codex `~/.codex` e vault compartilhado `C:/Repositorio/Cerebro_Rayane`, onde
   a pessoa registra suas impressões, leituras como DDD e aprendizados do trabalho);
5. Metadados dos commits da própria pessoa no repositório local autorizado
   (repositório corporativo local). O código-fonte e o diff nunca são lidos para o modelo.
"""

from __future__ import annotations

import json
import subprocess
import urllib.request
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

EXT_AREA = {
    '.cs': 'C#/.NET', '.cshtml': 'ASP.NET MVC/Razor', '.razor': 'Blazor',
    '.js': 'JavaScript', '.ts': 'TypeScript', '.tsx': 'React/TypeScript', '.jsx': 'React',
    '.html': 'HTML', '.css': 'CSS', '.scss': 'CSS/Sass', '.sql': 'SQL',
    '.py': 'Python', '.ipynb': 'Python/Jupyter', '.json': 'configuração JSON',
    '.xml': 'configuração XML', '.csproj': 'build .NET', '.config': 'configuração .NET',
    '.yml': 'CI/CD YAML', '.yaml': 'CI/CD YAML', '.md': 'documentação', '.tex': 'LaTeX',
}


@dataclass
class CommitMeta:
    date: str
    subject: str
    files: int
    insertions: int
    deletions: int
    areas: list[str] = field(default_factory=list)


def read_pdf(data: bytes | Path | None) -> str:
    """Extrai o texto de um PDF ou arquivo texto."""
    if not data:
        return ''
    if isinstance(data, Path):
        if not data.exists():
            return ''
        if data.suffix.lower() in {'.txt', '.md'}:
            return data.read_text(encoding='utf-8', errors='replace').strip()
    from io import BytesIO

    from pypdf import PdfReader

    stream = BytesIO(data) if isinstance(data, bytes) else open(data, 'rb')
    with stream:
        reader = PdfReader(stream)
        return '\n'.join((page.extract_text() or '') for page in reader.pages).strip()


def github_profile(username: str, timeout: float = 8.0) -> dict:
    """Perfil público e linguagens dos repositórios recentes, pela API pública."""
    if not username:
        return {}

    def get(url: str):
        req = urllib.request.Request(url, headers={'User-Agent': 'luzia-plugin'})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode('utf-8'))

    user = get(f'https://api.github.com/users/{username}')
    repos = get(f'https://api.github.com/users/{username}/repos?sort=updated&per_page=15')
    langs = Counter(r['language'] for r in repos if r.get('language'))
    return {
        'usuario': username,
        'bio': user.get('bio') or '',
        'repos_publicos': user.get('public_repos', 0),
        'desde': (user.get('created_at') or '')[:4],
        'linguagens_recentes': dict(langs.most_common(6)),
        'repos_recentes': [
            {
                'nome': r.get('name') or '',
                'descricao': r.get('description') or '',
                'linguagem': r.get('language') or '',
            }
            for r in repos[:8]
        ],
    }


def shared_ai_history(
    vault_dir: Path = Path(r'C:\Repositorio\Cerebro_Rayane'),
    home_dir: Path | None = None,
) -> dict:
    """Lê o histórico compartilhado entre Claude Code, Codex e o vault de impressões (Gemini/Obsidian).

    Preserva a separação do contrato do ecossistema: distingue notas autorais da pessoa
    de blocos de revisão assistida por IA (`<!-- revisao-ia:inicio -->`).
    """
    home = home_dir or Path.home()
    out: dict = {
        'notas_autorais_vault': [],
        'sessoes_claude_code': [],
        'sessoes_codex': [],
        'plugins_agentes_ativos': [],
    }

    # 1. Vault compartilhado (Cerebro_Rayane: leitura-ddd, topicos-avancados-ia)
    frentes = vault_dir / '01-frentes'
    if frentes.exists():
        for md in sorted(frentes.rglob('*.md')):
            raw = md.read_text(encoding='utf-8', errors='replace')
            # Remove o bloco de revisão automática da IA para ficar só com a impressão/registro da autora
            autoral = raw.split('<!-- revisao-ia:inicio -->')[0].strip()
            if autoral:
                out['notas_autorais_vault'].append({
                    'frente': md.parent.name,
                    'arquivo': md.name,
                    'conteudo_autoral': autoral[:1800],
                })

    # 2. Histórico recente do Claude Code (~/.claude/history.jsonl)
    claude_hist = home / '.claude' / 'history.jsonl'
    if claude_hist.exists():
        entries = []
        for line in claude_hist.read_text(encoding='utf-8', errors='replace').splitlines()[-25:]:
            try:
                d = json.loads(line)
                disp = (d.get('display') or '').strip()
                proj = Path(d.get('project') or '').name
                if disp and len(disp) > 5:
                    entries.append({'projeto': proj, 'prompt': disp[:180]})
            except Exception:
                continue
        out['sessoes_claude_code'] = entries[-12:]

    # 3. Plugins instalados no Claude Code (~/.claude/plugins/installed_plugins.json)
    plugins_file = home / '.claude' / 'plugins' / 'installed_plugins.json'
    if plugins_file.exists():
        try:
            pdata = json.loads(plugins_file.read_text(encoding='utf-8'))
            out['plugins_agentes_ativos'] = list((pdata.get('plugins') or {}).keys())
        except Exception:
            pass

    # 4. Histórico de sessões interativas do Codex (~/.codex/session_index.jsonl)
    codex_idx = home / '.codex' / 'session_index.jsonl'
    if codex_idx.exists():
        codex_threads = []
        for line in codex_idx.read_text(encoding='utf-8', errors='replace').splitlines():
            try:
                d = json.loads(line)
                t = (d.get('thread_name') or '').strip()
                if t and not any(w in t for w in ('Watcher', 'Guardian', 'New voice chat')):
                    codex_threads.append({
                        'data': (d.get('updated_at') or '')[:10],
                        'tarefa': t[:120],
                    })
            except Exception:
                continue
        out['sessoes_codex'] = codex_threads[-18:]

    return out


def repo_authors(repo: Path) -> list[str]:
    """Nomes dos demais autores do repositório, para mascarar colegas."""
    out = subprocess.run(
        ['git', '-C', str(repo), 'log', '--all', '--format=%an'],
        capture_output=True, text=True, encoding='utf-8', errors='replace', check=True,
    ).stdout
    names = set()
    for name in out.splitlines():
        name = name.strip()
        if name and 'rayane' not in name.lower():
            names.add(name)
            names.update(p for p in name.split() if len(p) >= 4)
    return sorted(names)


def my_commits(repo: Path, author: str, limit: int = 40) -> list[CommitMeta]:
    """Metadados dos commits da pessoa (sem merges, sem diff)."""
    out = subprocess.run(
        ['git', '-C', str(repo), 'log', '--all', '--no-merges', f'--author={author}',
         f'-{limit}', '--date=short', '--numstat', '--format=@@%ad|%s'],
        capture_output=True, text=True, encoding='utf-8', errors='replace', check=True,
    ).stdout
    commits: list[CommitMeta] = []
    cur: CommitMeta | None = None
    areas: Counter = Counter()
    for line in out.splitlines():
        if line.startswith('@@'):
            if cur:
                cur.areas = [a for a, _ in areas.most_common(4)]
                commits.append(cur)
            date, _, subject = line[2:].partition('|')
            cur, areas = CommitMeta(date, subject, 0, 0, 0), Counter()
        elif line.strip() and cur:
            parts = line.split('\t')
            if len(parts) != 3:
                continue
            ins, dels, path = parts
            cur.files += 1
            cur.insertions += int(ins) if ins.isdigit() else 0
            cur.deletions += int(dels) if dels.isdigit() else 0
            ext = Path(path).suffix.lower()
            areas[EXT_AREA.get(ext, ext or 'outro')] += 1
    if cur:
        cur.areas = [a for a, _ in areas.most_common(4)]
        commits.append(cur)
    return [c for c in commits if not c.subject.startswith(('index on', 'WIP on'))]
