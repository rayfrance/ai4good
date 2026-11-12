"""Motor do jogo da Luzia: feixes, lúmens, degraus, rota e dossiê.

Regras em `docs/luzia-ux.md`. Tudo fica em `private/` (fora do git):
- `feixes.json`: catálogo persistente de feixes, com estado e histórico;
- `lumens.jsonl`: livro de lúmens (skill, lm, luz própria ou refletida, fonte);
- `degraus.json`: base de níveis, data do último degrau por skill e histórico de subidas;
- `autoavaliacao.json`: o nível atual de cada skill (declarado e confirmado pela pessoa).
"""

from __future__ import annotations

import json
import math
from datetime import datetime
from pathlib import Path

PRIVATE = Path(__file__).resolve().parent / 'private'
FEIXES = PRIVATE / 'feixes.json'
LUMENS = PRIVATE / 'lumens.jsonl'
DEGRAUS = PRIVATE / 'degraus.json'
AUTOAVAL = PRIVATE / 'autoavaliacao.json'
DOSSIES = PRIVATE / 'dossies'

LIMIAR_DEGRAU = 150
MIN_PROPRIA = 0.40
MULT = {4: 1.0, 3: 0.75, 2: 0.5}
PASSIVO = {'refletida': 10, 'prompt': 20, 'conversao': 30}
TETO_PASSIVO_DIA = 40
MOTIVOS = {'nao_faz_sentido': 'não faz sentido para mim', 'ja_domino': 'já domino', 'agora_nao': 'agora não'}
ESTADO_ANTIGO = {'conquistado': 'feita', 'em_andamento': 'em andamento', 'na_fila': 'pendente',
                 'sugerido': 'pendente', 'descartado': 'descartada'}


def agora() -> str:
    return datetime.now().isoformat(timespec='seconds')


def _ler(path: Path, padrao):
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except Exception:
        return padrao


def _gravar(path: Path, dados) -> None:
    PRIVATE.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(dados, ensure_ascii=False, indent=2), encoding='utf-8')


# ------------------------------------------------------------------ níveis e skills
def niveis(plan: dict) -> dict[str, dict]:
    auto = _ler(AUTOAVAL, {})
    out = {}
    for s in plan.get('skills', []):
        nome = s['nome']
        nivel = auto.get(nome)
        if nivel is None:
            nivel = s.get('autoavaliacao') if s.get('autoavaliacao') is not None else s.get('luzia_sugere', 0)
        out[nome] = {'nivel': int(nivel or 0), 'meta': int(s.get('alvo', 5)), 'sugere': s.get('luzia_sugere'),
                     'declarado': nome in auto}
    return out


def skill_de(nome: str, plan: dict) -> str:
    """Casa o nome de skill de um feixe com a skill do plano (tolerante a variações)."""
    nomes = [s['nome'] for s in plan.get('skills', [])]
    if nome in nomes:
        return nome
    base = (nome or '').lower()
    for n in nomes:
        chave = n.lower().split('(')[0].split('/')[0].strip()
        if chave and (chave in base or base in n.lower()):
            return n
    return nome


def valor(feixe: dict, plan: dict) -> tuple[int, list[list]]:
    """Valor em lúmens por regra visível: esforço + lacuna + prioridade."""
    nv = niveis(plan)
    skill = skill_de(feixe.get('skill', ''), plan)
    info = nv.get(skill, {'nivel': 0, 'meta': 0})
    lacuna_niveis = max(0, info['meta'] - info['nivel'])
    esforco = max(5, min(30, int(feixe.get('duracao_min') or 10)))
    lacunas = sorted(((max(0, v['meta'] - v['nivel']), k) for k, v in nv.items()), reverse=True)
    top2 = {k for _, k in lacunas[:2]}
    prio = 0 if lacuna_niveis == 0 else (10 if skill in top2 else 5)
    conta = [['esforço', f"{esforco} min", esforco],
             ['lacuna', f"{info['nivel']} → {info['meta']}", 15 * lacuna_niveis],
             ['prioridade', 'uma das maiores lacunas' if prio == 10 else ('lacuna no plano' if prio else 'skill na meta'), prio]]
    total = max(10, min(100, sum(c[2] for c in conta)))
    return total, conta


# ------------------------------------------------------------------ catálogo de feixes
def sincronizar(plan: dict) -> dict[str, dict]:
    """Traz para o catálogo os feixes que a Luzia sugeriu, sem perder estados e histórico."""
    from . import acoes
    cat = _ler(FEIXES, {})
    antigos = acoes.status_map()  # eventos registrados antes do catálogo existir
    for f in acoes.derivadas(plan):
        atual = cat.get(f['id'])
        conteudo = {k: v for k, v in f.items() if k not in ('status', 'nota', 'resumo', 'quando')}
        if atual is None:
            st = antigos.get(f['id'], {}).get('status')
            cat[f['id']] = {**conteudo, 'estado': {'em andamento': 'em_andamento'}.get(st, 'sugerido'),
                            'criado_em': agora(), 'historico': [], 'tentativas': 0, 'lm_ganho': 0, 'revisitas': 0}
        else:
            atual.update({k: v for k, v in conteudo.items() if k not in ('titulo',) or not atual.get('renomeado')})
    for f in cat.values():
        if f.get('estado') != 'conquistado':
            f['valor_lm'], f['conta'] = valor(f, plan)
        f['skill_plano'] = skill_de(f.get('skill', ''), plan)
    _gravar(FEIXES, cat)
    return cat


def catalogo(plan: dict, descartados: bool = False) -> list[dict]:
    cat = sincronizar(plan)
    ordem = {'em_andamento': 0, 'na_fila': 1, 'sugerido': 2, 'conquistado': 3, 'descartado': 4}
    lista = [f for f in cat.values() if descartados or f.get('estado') != 'descartado']
    for f in lista:
        f['status'] = ESTADO_ANTIGO.get(f.get('estado'), 'pendente')
    return sorted(lista, key=lambda f: (ordem.get(f.get('estado'), 9), -int(f.get('valor_lm', 0))))


def _mudar(fid: str, estado: str | None, evento: str, **extra) -> dict | None:
    cat = _ler(FEIXES, {})
    f = cat.get(fid)
    if not f:
        return None
    if estado:
        f['estado'] = estado
    f.setdefault('historico', []).append({'quando': agora(), 'evento': evento, **extra})
    _gravar(FEIXES, cat)
    return f


def enfileirar(fid: str):
    return _mudar(fid, 'na_fila', 'enviado ao agente')


def iniciar(fid: str, onde: str = ''):
    cat = _ler(FEIXES, {})
    if cat.get(fid, {}).get('estado') == 'conquistado':
        return _mudar(fid, None, 'revisita iniciada', onde=onde)
    return _mudar(fid, 'em_andamento', 'iniciado', onde=onde)


def descartar(fid: str, motivo: str):
    return _mudar(fid, 'descartado', 'descartado', motivo=MOTIVOS.get(motivo, motivo))


def restaurar(fid: str):
    return _mudar(fid, 'sugerido', 'restaurado')


def motivos_descartados() -> list[dict]:
    return [{'titulo': f.get('titulo'), 'skill': f.get('skill'), 'motivo': (f.get('historico') or [{}])[-1].get('motivo')}
            for f in _ler(FEIXES, {}).values() if f.get('estado') == 'descartado']


# ------------------------------------------------------------------ lúmens
def lancar(skill: str, lm: int, luz: str, fonte: str, ref: str = '') -> dict:
    PRIVATE.mkdir(parents=True, exist_ok=True)
    rec = {'quando': agora(), 'skill': skill, 'lm': int(lm), 'luz': luz, 'fonte': fonte, 'ref': ref}
    with LUMENS.open('a', encoding='utf-8') as fh:
        fh.write(json.dumps(rec, ensure_ascii=False) + '\n')
    return rec


def livro() -> list[dict]:
    if not LUMENS.exists():
        return []
    out = []
    for linha in LUMENS.read_text(encoding='utf-8').splitlines():
        try:
            out.append(json.loads(linha))
        except Exception:
            continue
    return out


def conquistar(fid: str, nota: int, resumo: str, plan: dict) -> dict:
    """Aplica a rubrica: ganha lúmens, ou volta como 'tente de novo'. Permite uma revisita para notas 2-3."""
    cat = sincronizar(plan)
    f = cat.get(fid)
    if not f:
        return {'erro': 'feixe não encontrado'}
    nota = max(0, min(4, int(nota)))
    skill = f.get('skill_plano') or f.get('skill', '')
    alvo = int(round(f['valor_lm'] * MULT.get(nota, 0)))
    revisita = f.get('estado') == 'conquistado'
    if revisita:
        if f.get('revisitas', 0) >= 1 or f.get('nota', 0) >= 4:
            return {'erro': 'este feixe já foi revisitado ou já tem nota máxima'}
        ganho = max(0, alvo - int(f.get('lm_ganho', 0)))
        f['revisitas'] = 1
    else:
        ganho = alvo
    if nota < 2 and not revisita:
        f['tentativas'] = int(f.get('tentativas', 0)) + 1
        f['estado'] = 'sugerido'
        f.setdefault('historico', []).append({'quando': agora(), 'evento': 'tente de novo', 'nota': nota, 'resumo': resumo})
        _gravar(FEIXES, cat)
        return {'ganho': 0, 'tente_de_novo': True, 'feixe': f}
    if ganho:
        lancar(skill, ganho, 'propria', 'feixe', fid)
    f['estado'] = 'conquistado'
    f['nota'] = max(nota, int(f.get('nota', 0)))
    f['lm_ganho'] = int(f.get('lm_ganho', 0)) + ganho
    f['resumo'] = resumo
    f.setdefault('historico', []).append({'quando': agora(), 'evento': 'revisitado' if revisita else 'conquistado',
                                          'nota': nota, 'lm': ganho, 'resumo': resumo})
    _gravar(FEIXES, cat)
    return {'ganho': ganho, 'feixe': f, 'pode_revisitar': f['nota'] in (2, 3) and not f.get('revisitas')}


def passivo(skill: str, tipo: str, sessao: str = '') -> int:
    """Reconhecimento no dia a dia: 'refletida' (o agente aplicou), 'prompt' (você dirigiu) ou 'conversao'."""
    hoje = agora()[:10]
    ja = sum(r['lm'] for r in livro() if r['skill'] == skill and r['fonte'].startswith('passivo') and r['quando'][:10] == hoje)
    if tipo != 'conversao' and ja >= TETO_PASSIVO_DIA:
        return 0
    lm = PASSIVO[tipo] if tipo != 'conversao' else PASSIVO['conversao']
    lm = min(lm, max(0, TETO_PASSIVO_DIA - ja)) if tipo != 'conversao' else lm
    if lm:
        lancar(skill, lm, 'refletida' if tipo == 'refletida' else 'propria', f'passivo-{tipo}', sessao)
    return lm


# ------------------------------------------------------------------ degraus e rota
def _degraus() -> dict:
    return _ler(DEGRAUS, {'base': {}, 'desde': {}, 'historico': [], 'marcos_dossie': []})


def garantir_base(plan: dict) -> dict:
    """A base da rota é o primeiro nível DECLARADO pela pessoa (nunca a sugestão da Luzia)."""
    d = _degraus()
    mudou = False
    for nome, v in niveis(plan).items():
        if v['declarado'] and nome not in d['base']:
            d['base'][nome] = v['nivel']
            mudou = True
        d['desde'].setdefault(nome, '')
    if mudou or not DEGRAUS.exists():
        _gravar(DEGRAUS, d)
    return d


def progresso_skill(skill: str, d: dict | None = None) -> dict:
    d = d or _degraus()
    desde = d.get('desde', {}).get(skill, '')
    regs = [r for r in livro() if r['skill'] == skill and r['quando'] > desde]
    total = sum(r['lm'] for r in regs)
    propria = sum(r['lm'] for r in regs if r['luz'] == 'propria')
    share = (propria / total) if total else 0.0
    return {'lm': total, 'propria': propria, 'refletida': total - propria, 'luz_propria': round(100 * share),
            'limiar': LIMIAR_DEGRAU, 'pronto': total >= LIMIAR_DEGRAU and share >= MIN_PROPRIA}


def rota(plan: dict) -> dict:
    d = garantir_base(plan)
    nv = niveis(plan)
    skills, total, feitos = [], 0, 0
    for nome, v in nv.items():
        base = int(d['base'].get(nome, v['nivel']))
        falta_total = max(0, v['meta'] - base)
        feitos_s = max(0, min(falta_total, v['nivel'] - base))
        total += falta_total
        feitos += feitos_s
        p = progresso_skill(nome, d)
        skills.append({'nome': nome, 'nivel': v['nivel'], 'meta': v['meta'], 'proximo': min(v['meta'], v['nivel'] + 1),
                       'na_meta': v['nivel'] >= v['meta'], **p})
    lm_total = sum(r['lm'] for r in livro())
    lm_propria = sum(r['lm'] for r in livro() if r['luz'] == 'propria')
    marcos = [math.ceil(total * k / 3) for k in (1, 2, 3)] if total else []
    return {'degraus_total': total, 'degraus_feitos': feitos, 'marcos': marcos, 'skills': skills,
            'lm_total': lm_total, 'luz_propria': round(100 * lm_propria / lm_total) if lm_total else 0,
            'pct': round(100 * feitos / total) if total else 100}


def subir(skill: str, plan: dict) -> dict:
    """Confirma um degrau pronto: sobe o nível declarado, zera o progresso da skill e checa marco."""
    d = garantir_base(plan)
    p = progresso_skill(skill, d)
    if not p['pronto']:
        return {'erro': f"ainda não: {p['lm']}/{LIMIAR_DEGRAU} lm e {p['luz_propria']}% de luz própria (mínimo {int(MIN_PROPRIA * 100)}%)"}
    auto = _ler(AUTOAVAL, {})
    nv = niveis(plan)
    d['base'].setdefault(skill, nv[skill]['nivel'])  # a base guarda o nível de antes da primeira subida
    novo = min(nv[skill]['meta'], nv[skill]['nivel'] + 1)
    auto[skill] = novo
    _gravar(AUTOAVAL, auto)
    d['desde'][skill] = agora()
    d['historico'].append({'quando': agora(), 'skill': skill, 'para': novo, 'lm': p['lm'], 'luz_propria': p['luz_propria']})
    _gravar(DEGRAUS, d)
    r = rota(plan)
    marco = None
    for i, m in enumerate(r['marcos'], 1):
        if r['degraus_feitos'] >= m and i not in d.get('marcos_dossie', []):
            d.setdefault('marcos_dossie', []).append(i)
            _gravar(DEGRAUS, d)
            marco = {'n': i, 'dossie': str(dossie(plan, f'marco {i} de 3'))}
    return {'skill': skill, 'para': novo, 'rota': r, 'marco': marco}


def ritmo(plan: dict, horizonte: str = '') -> dict:
    """Calibragem (não cronograma): feixes por semana para chegar no prazo que a pessoa imagina."""
    r = rota(plan)
    faltam = sum(max(0, s['meta'] - s['nivel']) * LIMIAR_DEGRAU - (s['lm'] if not s['na_meta'] else 0) for s in r['skills'])
    meses = next((int(t) for t in str(horizonte).split() if t.isdigit()), 12)
    pend = [f for f in _ler(FEIXES, {}).values() if f.get('estado') in ('sugerido', 'na_fila')]
    medio = (sum(int(f.get('valor_lm', 40)) for f in pend) / len(pend)) if pend else 40
    semanas = max(1.0, meses * 4.33)
    return {'lm_faltam': max(0, faltam), 'meses': meses, 'feixes_semana': max(1, math.ceil(faltam / (medio * semanas)))}


# ------------------------------------------------------------------ dossiê
def dossie(plan: dict, titulo: str = 'agora') -> Path:
    r = rota(plan)
    cat = _ler(FEIXES, {})
    conq = [f for f in cat.values() if f.get('estado') == 'conquistado']
    d = _degraus()
    linhas = [
        f'# Dossiê de evidências · {titulo} · {agora()[:10]}', '',
        f"Rota: **{r['degraus_feitos']} de {r['degraus_total']} degraus** até Plena · {r['lm_total']} lm · {r['luz_propria']}% de luz própria.", '',
        '## Degraus subidos',
    ]
    linhas += [f"- {h['quando'][:10]} · {h['skill']} → {h['para']} ({h['lm']} lm, {h['luz_propria']}% luz própria)" for h in d['historico']] or ['- nenhum ainda']
    linhas += ['', '## Feixes conquistados (evidência avaliada pela rubrica 0–4)']
    for f in sorted(conq, key=lambda x: x.get('historico', [{}])[-1].get('quando', '')):
        linhas.append(f"- **{f.get('titulo')}** · {f.get('skill_plano') or f.get('skill')} · nota {f.get('nota')}/4 · {f.get('lm_ganho')} lm — {f.get('resumo', '')}")
    if not conq:
        linhas.append('- nenhum ainda')
    linhas += ['', '## Por skill']
    for s in r['skills']:
        linhas.append(f"- {s['nome']}: nível {s['nivel']} (meta {s['meta']}) · {s['lm']} lm desde o último degrau · {s['luz_propria']}% luz própria")
    linhas += ['', '_Gerado localmente pela Luzia a partir das evidências registradas; não substitui a avaliação do seu líder._']
    DOSSIES.mkdir(parents=True, exist_ok=True)
    caminho = DOSSIES / f"dossie-{agora()[:10]}-{titulo.replace(' ', '-')}.md"
    caminho.write_text('\n'.join(linhas) + '\n', encoding='utf-8')
    return caminho
