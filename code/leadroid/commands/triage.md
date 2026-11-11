---
description: Luzia · triagem de carreira (currículo, GitHub, histórico entre IAs e commits, com LGPD local)
allowed-tools: Bash(cd:*), Bash(python:*)
---

Rode a Luzia (plugin de carreira) e mostre a saída **exatamente como veio**, sem resumir nem reescrever:

```bash
cd /c/Repositorio/ai4good-sem2/code && python -m leadroid.cli triage --rotulo triage
```

Depois, em uma linha, pergunte se a pessoa quer ajustar a autoavaliação no painel (/luzia:career-map).
Não leia, abra nem mostre arquivos ou código do repositório atual: a Luzia já entrega tudo mascarado (LGPD).
