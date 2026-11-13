"""Um prisma = uma habilidade (decisão de produto de 13/11/2026): divisão determinística de nomes compostos.

Nada aqui chama o modelo nem abre o banco. Regras, na ordem:
1. `MAPA_DIVISAO`: os nomes compostos que a triagem já criou, com a divisão revisada à mão (o mapa manda).
2. `INDIVISIVEIS`: nomes que parecem compostos, mas são uma habilidade só ("Testes e Qualidade", "C# / .NET").
3. Regra genérica para nomes novos: parênteses com lista ("Front-end (JS / Razor / React)" → as três), depois
   " / " entre habilidades e, em cada pedaço, " e " entre habilidades. Parênteses com uma sigla só
   ("Domain-Driven Design (DDD)") não dividem.

A classificação de um avanço (para qual parte ele vai) usa só as palavras de cada parte no título e nos conceitos;
empate fica com a primeira parte empatada e nenhum acerto fica com a primeira parte (a pessoa confere antes de aceitar).
"""

from __future__ import annotations

import re

# Divisão revisada dos nomes atuais (planner.SKILLS_OBRIGATORIAS antigos). Lista de partes, na ordem de exibição.
MAPA_DIVISAO: dict[str, list[str]] = {
    'Testes e Qualidade / SQL': ['Testes e Qualidade', 'SQL'],
    'Arquitetura .NET / Clean Architecture': ['Arquitetura .NET', 'Clean Architecture'],
    'Front-end (JS / Razor / React)': ['JavaScript', 'Razor', 'React'],
    'Back-end C# / .NET e Integrações': ['C# / .NET', 'Integrações'],
    # "Fluxo com IA" é o modo de trabalhar da própria Programação Agêntica, não outra habilidade: só troca o nome.
    'Programação Agêntica e Fluxo com IA': ['Programação Agêntica'],
}

# Parecem compostos, mas são uma habilidade só (a regra genérica não os divide).
INDIVISIVEIS = frozenset({'Testes e Qualidade', 'C# / .NET', 'Domain-Driven Design (DDD)'})

# Palavras padrão de cada habilidade isolada (o observador e as entregas casam por elas).
PALAVRAS_PARTE: dict[str, list[str]] = {
    'Domain-Driven Design (DDD)': ['Domain', 'Aggregate', 'ValueObject', 'Value Object', 'Entity', 'Repository',
                                   'BoundedContext', 'DomainEvent', 'agregado', 'objeto de valor', 'entidade',
                                   'subdomínio', 'contexto delimitado', 'DDD'],
    'Testes e Qualidade': ['Test', 'xunit', 'nunit', 'Assert', 'Mock', 'Fact', 'teste', 'cobertura', 'qualidade'],
    'SQL': ['SQL', 'SELECT', 'JOIN', 'índice', 'query', 'consulta', 'stored procedure', 'tabela'],
    'Arquitetura .NET': ['Interface', 'Application', 'Infrastructure', 'DependencyInjection', 'IServiceCollection',
                         'camada', 'injeção de dependência', 'arquitetura'],
    'Clean Architecture': ['UseCase', 'Use Case', 'caso de uso', 'clean architecture', 'desacopl', 'Ports', 'Adapters'],
    'C# / .NET': ['async Task', 'LINQ', 'C#', '.NET', 'csharp', 'Controller', '.cs'],
    'Integrações': ['HttpClient', 'Integration', 'integração', 'endpoint', 'retry', 'webhook'],
    'JavaScript': ['JavaScript', '.js', 'fetch(', 'jQuery', 'addEventListener', 'modal'],
    'Razor': ['Razor', '.cshtml', '@model', 'Partial', 'ViewComponent'],
    'React': ['React', 'useState', 'useEffect', '.jsx', '.tsx', 'componente', 'props'],
    'Programação Agêntica': ['CLAUDE.md', 'AGENTS.md', '.claude', 'subagente', 'hook', 'skill', 'plan mode', 'agente'],
}

_PARENTESES = re.compile(r'^(?P<base>.*?)\s*\((?P<dentro>[^()]+)\)\s*$')
_BARRA = re.compile(r'\s+/\s+')
_E = re.compile(r'\s+e\s+')
_LISTA = re.compile(r'\s*[/,]\s*')


def _limpo(nome) -> str:
    return re.sub(r'\s+', ' ', str(nome or '')).strip()


def partes(nome: str) -> list[str]:
    """As habilidades isoladas de um nome de prisma (o próprio nome, numa lista, quando já é uma habilidade só)."""
    nome = _limpo(nome)
    if not nome:
        return []
    if nome in MAPA_DIVISAO:
        return list(MAPA_DIVISAO[nome])
    if nome in INDIVISIVEIS:
        return [nome]
    m = _PARENTESES.match(nome)
    if m:
        itens = [i for i in (_limpo(x) for x in _LISTA.split(m['dentro'])) if i]
        if len(itens) >= 2:
            return list(dict.fromkeys(itens))
        return [nome]  # sigla ou complemento: "Domain-Driven Design (DDD)"
    out: list[str] = []
    for pedaco in _BARRA.split(nome):
        pedaco = _limpo(pedaco)
        if pedaco in INDIVISIVEIS:
            out.append(pedaco)
            continue
        out.extend(_limpo(x) for x in _E.split(pedaco))
    out = [p for p in dict.fromkeys(out) if p]
    return out or [nome]


_SIGLA = re.compile(r'^[\w.#+-]{2,10}$')


def nome_curto(nome: str) -> str:
    """Rótulo curto do prisma (painel e chat usam o mesmo; o nome completo fica no title ou no detalhe).

    Sigla entre parênteses ("Domain-Driven Design (DDD)" → "DDD"); senão o nome sem os parênteses, se couber em 20
    caracteres; senão o trecho após o último " / "; senão os 18 primeiros caracteres com "…".
    O painel (`nomeCurto` em painel/luzia.js) só repete esta regra para nomes que não vieram no estado.
    """
    n = _limpo(nome)
    m = _PARENTESES.match(n)
    if m and _SIGLA.match(m['dentro'].strip()):
        return m['dentro'].strip()
    base = (m['base'] if m else n).strip()
    if len(base) <= 20:
        return base
    ultimo = _BARRA.split(base)[-1].strip()
    if ultimo != base and 2 <= len(ultimo) <= 20:
        return ultimo
    return base[:18].strip() + '…'


def composto(nome: str) -> bool:
    """True quando o nome junta habilidades (ou tem um nome isolado revisado no mapa)."""
    return partes(nome) != [_limpo(nome)]


def exigir_isolado(nome: str) -> str:
    """O nome limpo, ou ValueError dizendo em quais habilidades ele se divide."""
    limpo = _limpo(nome)
    if composto(limpo):
        sugestao = ', '.join(f'"{p}"' for p in partes(limpo))
        raise ValueError(f'um prisma é uma habilidade só: "{limpo}" junta assuntos; use {sugestao}')
    return limpo


def _casa(palavra: str, texto: str) -> bool:
    """Mesma borda do observador: a palavra não pode começar no meio de outra."""
    return len(palavra) >= 2 and re.search(r'(?<![A-Za-z])' + re.escape(palavra), texto, re.IGNORECASE) is not None


def palavras_padrao(parte: str) -> list[str]:
    return list(PALAVRAS_PARTE.get(parte, [])) or [w for w in re.split(r'[\s/()]+', parte) if len(w) >= 3]


def _pontos(parte: str, extras: list[str], texto: str) -> int:
    palavras = list(dict.fromkeys([*palavras_padrao(parte), *extras]))
    return (2 if _casa(parte, texto) else 0) + sum(1 for w in palavras if w.casefold() != parte.casefold() and _casa(w, texto))


def _melhor(nomes: list[str], pontos: list[int]) -> str:
    alto = max(pontos) if pontos else 0
    return nomes[pontos.index(alto)] if alto > 0 else nomes[0]


def repartir_palavras(palavras: list[str], nomes: list[str]) -> dict[str, list[str]]:
    """Palavras do prisma antigo para cada parte (a que casa com as palavras da parte), mais as padrão da parte.

    Palavra que não casa com nenhuma parte fica com a primeira (nada se perde; a pessoa pode ajustar).
    """
    out = {n: [] for n in nomes}
    for w in palavras or []:
        w = _limpo(w)
        if not w:
            continue
        pontos = []
        for n in nomes:
            padrao = [p.casefold() for p in palavras_padrao(n)]
            wc = w.casefold()
            pontos.append(sum(1 for p in padrao if p == wc or (len(p) >= 3 and (p in wc or wc in p)))
                          + (1 if wc in n.casefold() else 0))
        out[_melhor(nomes, pontos)].append(w)
    return {n: list(dict.fromkeys([*ws, *palavras_padrao(n)])) for n, ws in out.items()}


def classificar(avanco: dict, nomes: list[str], palavras: dict[str, list[str]] | None = None) -> str:
    """Para qual parte vai um avanço: as palavras de cada parte no título e nos conceitos (sem modelo)."""
    if len(nomes) == 1:
        return nomes[0]
    # Um conceito que é o próprio nome composto casa com todas as partes: não ajuda a decidir.
    conceitos = [c for c in (avanco.get('conceitos') or []) if isinstance(c, str) and not composto(c)]
    texto = ' '.join([str(avanco.get('titulo') or ''), *conceitos])
    palavras = palavras or {}
    return _melhor(nomes, [_pontos(n, palavras.get(n, []), texto) for n in nomes])


def dividir_skills(skills: list[dict]) -> list[dict]:
    """Skills de uma triagem com cada nome composto trocado pelas habilidades isoladas (nível, alvo e evidência herdados).

    Uma parte que já aparece na lista não se repete. Valida a regra "um prisma = uma habilidade" no que o modelo devolve.
    """
    out: list[dict] = []
    vistos: set[str] = set()
    for s in skills or []:
        if not isinstance(s, dict) or not isinstance(s.get('nome'), str):
            out.append(s)
            continue
        nomes = partes(s['nome'])
        if nomes == [_limpo(s['nome'])]:
            if nomes[0] not in vistos:
                vistos.add(nomes[0])
                out.append(s)
            continue
        por_parte = repartir_palavras(list(s.get('palavras_chave') or []), nomes)
        for n in nomes:
            if n in vistos:
                continue
            vistos.add(n)
            out.append({**s, 'nome': n, 'palavras_chave': por_parte[n], 'dividido_de': s['nome']})
    return out


def dividir_plano(plan: dict) -> dict:
    """Plano da triagem sem prismas compostos: skills divididas e cada ação na habilidade que ela de fato trata."""
    if not isinstance(plan, dict):
        return plan
    skills = plan.get('skills')
    if not isinstance(skills, list) or not any(isinstance(s, dict) and composto(s.get('nome') or '') for s in skills):
        return plan
    novas = dividir_skills(skills)
    palavras = {s['nome']: list(s.get('palavras_chave') or []) for s in novas if isinstance(s, dict) and s.get('nome')}

    def ajustar(a: dict) -> None:
        if isinstance(a, dict) and isinstance(a.get('skill'), str) and composto(a['skill']):
            a['skill'] = classificar(a, partes(a['skill']), palavras)

    for marco in plan.get('plano') or []:
        for a in (marco.get('acoes') or []) if isinstance(marco, dict) else []:
            ajustar(a)
    for t in plan.get('tarefas_recentes') or []:
        if not isinstance(t, dict):
            continue
        for a in t.get('acoes') or []:
            ajustar(a)
        if isinstance(t.get('skills'), list):
            t['skills'] = list(dict.fromkeys(p for s in t['skills'] for p in (partes(s) if isinstance(s, str) else [s])))
    for op in plan.get('oportunidades_tarefa_atual') or []:
        if isinstance(op, dict):
            ajustar(op.get('acao') or {})
            if isinstance(op.get('skill_alvo'), str) and composto(op['skill_alvo']):
                op['skill_alvo'] = (op.get('acao') or {}).get('skill') or partes(op['skill_alvo'])[0]
    return {**plan, 'skills': novas}
