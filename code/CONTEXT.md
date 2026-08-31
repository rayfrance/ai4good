# code/ — Código e Experimentos

> Leia este arquivo antes de criar ou modificar qualquer coisa nesta pasta.

## O que fica aqui

Todo o código produzido durante a disciplina:

- **`notebooks/`** — Jupyter notebooks dos experimentos, nomeados com prefixo numérico
  (ex: `01-exploracao-dados.ipynb`, `02-treinamento-modelo.ipynb`)
- **`src/`** — Módulos Python reutilizáveis (funções, classes, utilitários)
- **`scripts/`** — Scripts standalone para execução direta (pré-processamento, avaliação)
- **`data/`** — Dados de entrada (apenas exemplos pequenos; datasets grandes ficam fora do git)

## Convenções

- Notebooks com **prefixo numérico** refletem a ordem lógica dos experimentos
- Módulos Python em `snake_case`
- Cada experimento importante vira uma **branch** `feature/exp-nome-do-experimento`
- Dependências declaradas em `requirements.txt` (ou `pyproject.toml` se usar Poetry)

## O que NÃO fica aqui

- Tokens, chaves de API, senhas → ficam em `.env` na raiz
- Datasets grandes → ficam fora do repositório (documente onde estão em `data/README.md`)
- Outputs gerados (modelos treinados, plots) → pasta `outputs/` na raiz (gitignored)
