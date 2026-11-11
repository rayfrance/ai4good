"""Anonimização local, antes de qualquer dado sair da máquina.

Tudo que vai para o modelo de linguagem passa por `Redactor.redact`. A mesma
função é usada na tela em modo apresentação, para não projetar dados pessoais
nem nomes da empresa, produto interno, colegas ou clientes (LGPD).
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
        keep = {k.lower() for k in (keep_names or {'rayane', 'france', 'tasy', 'jev', 'brevo', 'mv'})}
        terms: list[str] = []
        if path and path.exists():
            for line in path.read_text(encoding='utf-8').splitlines():
                line = line.strip()
                if line and not line.startswith('#'):
                    terms.append(line)
        colleagues = [
            c for c in (extra_colleagues or [])
            if len(c) >= 4 and c.lower() not in keep and 'rayane' not in c.lower()
        ]
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
