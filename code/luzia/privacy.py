"""Mascaramento local do que vai ao modelo de linguagem (LGPD), quando a pessoa liga o interruptor.

A proteção da tela é o login do painel (`acesso.py`): a dona dos dados vê tudo real. O envio ao modelo sai real por
padrão; com `mascarar_modelo` ligado (Ajustes no painel ou `privacidade mascarar-modelo on` no chat), todo payload passa
por `mascarar_estrutura` em `pipeline.run_plan` antes de sair da máquina. Arquivos versionados nunca recebem dados reais.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ('[EMAIL]', re.compile(r'[\w.+-]+@[\w-]+(?:\.[\w-]+)+')),
    ('[URL]', re.compile(r'(?:https?|file)://\S+|www\.\S+')),
    ('[CPF]', re.compile(r'\b\d{3}\.?\d{3}\.?\d{3}-?\d{2}\b')),
    ('[TELEFONE]', re.compile(r'(?:\+?55\s?)?\(?\d{2}\)?\s?9?\d{4}[-\s]?\d{4}\b')),
    ('[CEP]', re.compile(r'\b\d{5}-\d{3}\b')),
    ('[PR]', re.compile(r'\b(?:PR|Pull Request)\s*#?\d+\b', re.IGNORECASE)),
    ('[TICKET]', re.compile(r'#\d{3,}\b')),
    ('[HASH]', re.compile(r'\b[0-9a-f]{7,40}\b')),
]


# termos.txt lido uma vez por processo e relido só quando o arquivo muda (caminho, mtime, tamanho): o painel pede o
# estado a cada 4 s e cada leitura/entrega abria o arquivo de novo.
_TERMOS: dict[Path, tuple[tuple[int, int], list[str]]] = {}


def _termos_do_arquivo(path: Path | None) -> list[str]:
    if not path:
        return []
    try:
        info = path.stat()
    except OSError:
        _TERMOS.pop(path, None)
        return []
    marca = (info.st_mtime_ns, info.st_size)
    guardado = _TERMOS.get(path)
    if guardado and guardado[0] == marca:
        return list(guardado[1])
    termos = [t for t in (ln.strip() for ln in path.read_text(encoding='utf-8').splitlines()) if t and not t.startswith('#')]
    _TERMOS[path] = (marca, termos)
    return list(termos)


def mascarar_estrutura(obj, redactor: 'Redactor', manter: frozenset[str] | set[str] = frozenset(), limpar=None):
    """Cópia de `obj` com todo texto mascarado. Chaves em `manter` com valor de texto ficam como estão (ids e nomes de
    prisma que a resposta do modelo precisa devolver iguais); dicionários e listas sob elas são mascarados também.
    `limpar`: função aplicada antes do `redact` (ex.: tirar números de ticket)."""
    if isinstance(obj, dict):
        return {k: (v if k in manter and isinstance(v, str) else mascarar_estrutura(v, redactor, manter, limpar))
                for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [mascarar_estrutura(v, redactor, manter, limpar) for v in obj]
    if isinstance(obj, str):
        return redactor.redact(limpar(obj) if limpar else obj)
    return obj


@dataclass
class Redactor:
    """Mascara padrões de dados pessoais, termos de empresa/clientes e nomes de colegas."""

    terms: list[str] = field(default_factory=list)
    colleagues: list[str] = field(default_factory=list)
    hits: dict[str, int] = field(default_factory=dict)

    @classmethod
    def from_file(
        cls,
        path: Path | None,
        extra_colleagues: list[str] | None = None,
        keep_names: set[str] | None = None,
    ) -> 'Redactor':
        # `keep_names`: identidades da própria pessoa (do perfil e de private/entrada.json); nunca nomes no código.
        keep = {t.casefold() for k in (keep_names or set()) for t in [k, *k.split()]}
        terms = _termos_do_arquivo(path)
        colleagues = [c for c in (extra_colleagues or []) if len(c) >= 4 and c.casefold() not in keep]
        uniq_terms = sorted({t for t in terms if len(t) >= 3}, key=len, reverse=True)
        uniq_cols = sorted(set(colleagues), key=len, reverse=True)
        return cls(terms=uniq_terms, colleagues=uniq_cols)

    def redact(self, text: str) -> str:
        for label, pattern in _PATTERNS:
            text, n = pattern.subn(label, text)
            if n:
                self.hits[label] = self.hits.get(label, 0) + n
        for term in self.terms:
            pat = re.escape(term) if len(term) >= 4 else r'\b' + re.escape(term) + r'\b'
            pattern = re.compile(pat, re.IGNORECASE)
            text, n = pattern.subn('[EMPRESA/PRODUTO]', text)
            if n:
                self.hits['[EMPRESA/PRODUTO]'] = self.hits.get('[EMPRESA/PRODUTO]', 0) + n
        for col in self.colleagues:
            pattern = re.compile(r'\b' + re.escape(col) + r'\b', re.IGNORECASE)
            text, n = pattern.subn('[COLEGA]', text)
            if n:
                self.hits['[COLEGA]'] = self.hits.get('[COLEGA]', 0) + n
        return text


class SemMascara(Redactor):
    """Redator que não muda nada: o envio ao modelo com o interruptor `mascarar_modelo` desligado (padrão)."""

    def redact(self, text: str) -> str:
        return text
