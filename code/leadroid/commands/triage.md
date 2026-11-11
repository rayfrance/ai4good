---
description: Triagem inicial de carreira (currículo, GitHub, histórico compartilhado entre IAs e commits locais com anonimização LGPD)
allowed-tools: Bash(python:*), Read
---

Execute a triagem inicial do **Leadroid** (`@triage`) rodando o motor do plugin no repositório:

```bash
python -m leadroid.cli triage --forcar
```
(Diretório de trabalho: `C:\Repositorio\ai4good-sem2\code`)

Apresente para a pessoa desenvolvedora:
1. O resumo calibrado de **onde ela está** vs. **aonde quer chegar** (destacando como o histórico compartilhado entre Claude/Codex/Obsidian calibrou o currículo);
2. O **mapa de skills (atual × alvo Pleno)**;
3. O **próximo passo imediato**;
4. Os números reais medidos na execução (**tempo total em s**, **pico de memória em MiB**, **tokens** e **itens mascarados por LGPD**).
