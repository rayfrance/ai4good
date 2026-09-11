"""
conftest.py — configuração do pytest para o workspace ai4good.

Adiciona code/src/ ao sys.path para que os testes possam importar o pacote mlp
independente do diretório de onde o pytest é executado.
"""

import sys
from pathlib import Path

# Caminho para code/src/
_SRC = Path(__file__).resolve().parent / "code" / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))
