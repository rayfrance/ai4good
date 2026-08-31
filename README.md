# AI4Good — Workspace da Disciplina

> Workspace acadêmico para a disciplina **Tópicos Avançados em Inteligência Artificial** (UFRPE).
> Inspirado em [lsfcin/workspace](https://github.com/lsfcin/workspace).

## O que é isso?

Este repositório centraliza **tudo** da disciplina em um único lugar organizado:

| Pasta | O que tem aqui |
|---|---|
| [`code/`](code/CONTEXT.md) | Código-fonte, notebooks e experimentos |
| [`papers/`](papers/CONTEXT.md) | Artigos científicos lidos e anotações |
| [`article/`](article/CONTEXT.md) | O artigo final (espelho do Overleaf) |
| [`core/`](core/CONTEXT.md) | Fluxos e templates reutilizáveis |
| [`tools/`](tools/CONTEXT.md) | Verificações e compilação local |

O arquivo [`AGENTS.md`](AGENTS.md) define as regras de navegação para agentes de IA.

## Princípio central

**O sistema de arquivos é a fonte da verdade.** Se algo importa para o projeto, é um arquivo aqui e está versionado. Nada importante fica só em memória de chat ou em configuração de máquina.

## Como trabalhar

### Código e experimentos
```bash
# Crie uma branch de feature antes de qualquer trabalho
git checkout develop
git checkout -b feature/nome-do-experimento

# Faça seu trabalho em code/
# Ao terminar:
git add .
git commit -m "feat: descrição do que foi feito"
git push origin feature/nome-do-experimento
```

### Artigo (Overleaf ↔ Git)
```bash
# Baixar as últimas mudanças do Overleaf para article/
git subtree pull --prefix article overleaf main --squash

# Depois de revisar e commitar mudanças no artigo, enviá-las ao Overleaf
git subtree push --prefix article overleaf main
```

### Verificar o workspace

```powershell
python tools\workspace_check.py
python tools\compile_article.py
```

O primeiro comando verifica a organização. O segundo compila o artigo quando o LaTeX estiver instalado.

## Branches (GitFlow simplificado)

| Branch | Uso |
|---|---|
| `main` | Versões estáveis (releases do artigo, código validado) |
| `develop` | Integração do trabalho em andamento |
| `feature/*` | Uma feature ou experimento por branch |

## Segredos

Tokens e senhas ficam em `.env` (não versionado). Veja `.env.example` para saber o que configurar.
