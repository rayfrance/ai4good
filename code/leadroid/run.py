"""Execução sem interface, para medir custo em processo limpo (exp.md).

Uso:  python -m leadroid.run --rotulo exp-1     (a partir de code/)
Lê a entrada de code/leadroid/private/entrada.json (fora do git):
  {"nivel": ..., "objetivo": ..., "horizonte": ..., "uso_ia": ...,
   "cv_pdf": "caminho", "linkedin_pdf": "caminho", "github": "usuario",
   "repo": "<caminho-do-repositorio>", "author": "Rayane", "limit": 40}
Imprime só o registro de custo e o plano anonimizado.
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

from . import pipeline, triage
from .privacy import Redactor


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument('--rotulo', default='cli')
    ap.add_argument('--entrada', default=str(pipeline.PRIVATE / 'entrada.json'))
    ap.add_argument('--salvar-plano', default='')
    args = ap.parse_args()

    pipeline.load_env()
    cfg = json.loads(Path(args.entrada).read_text(encoding='utf-8'))
    t0 = time.perf_counter()
    repo = Path(cfg['repo']) if cfg.get('repo') else None
    redactor = Redactor.from_file(pipeline.PRIVATE / 'termos.txt',
                                  extra=triage.repo_authors(repo) if repo else [])
    inputs = dict(cfg)
    inputs['cv_text'] = triage.read_pdf(Path(cfg['cv_pdf'])) if cfg.get('cv_pdf') else ''
    inputs['linkedin_text'] = triage.read_pdf(Path(cfg['linkedin_pdf'])) if cfg.get('linkedin_pdf') else ''
    inputs['github_data'] = triage.github_profile(cfg['github']) if cfg.get('github') else {}
    payload = pipeline.build_payload(inputs, redactor)
    result, record = pipeline.run_plan(payload, time.perf_counter() - t0, label=args.rotulo)
    print(json.dumps(record, ensure_ascii=False, indent=1))
    if args.salvar_plano:
        Path(args.salvar_plano).write_text(result.raw, encoding='utf-8')


if __name__ == '__main__':
    main()
