"""Pedidos formais de mudança da trajetória (Tarefa 11): incluir, arquivar, reativar e mudar meta.

Regras (spec, seções 6 e 11):
- Um único pedido aberto ou proposto por prisma por vez.
- "Ajustar" (`propor` com novo nível/meta) pode se repetir sem limite; cada proposta fica guardada no histórico.
- Tipos `arquivar` e `reativar` não chamam o modelo.
- Em `incluir` e `mudar_meta`, a análise da Luzia é gravada como leitura com base (`alvo_tipo='pedido'`).
  Sem modelo (sem chave, sem internet, erro): a proposta sai do nível/meta pedidos pela pessoa (ou dos atuais),
  sem análise e sem avanços ("leitura indisponível"), fica `proposto` e pode ser aceita.
- `mudar_meta` nunca altera o nível atual nem os lúmens (e não cria `nivel_registro`).
- `arquivar` tira o prisma dos níveis da trajetória, preservando todos os lúmens, avanços e histórico; `reativar` devolve tudo.
- `aceitar` cria uma nova versão da trajetória (`trajetoria_versao`).
- `dividir` (13/11/2026, um prisma = uma habilidade): sem modelo, a divisão sai de `prismas.partes` e cada avanço vai
  para a parte que casa com as palavras dele; a pessoa ajusta (renomear parte, mover avanço) antes de aceitar.
  Aceito: cada parte vira prisma ativo com o nível e a meta do antigo (registro `pedido` no livro de níveis), os
  avanços mudam de prisma e o antigo é arquivado. Os lúmens antigos ficam no prisma arquivado (o livro só acrescenta):
  o progresso do nível novo conta a partir do aceite, sem perder histórico nem mudar o total de lúmens.
- Um prisma é uma habilidade só: `incluir` recusa nome composto e `reativar` recusa um prisma que já foi dividido.
"""

from __future__ import annotations

import json
import sqlite3
import time
from datetime import datetime

from . import acoes, arquivos, banco, jogo, leituras, modelo, pipeline, planner, prismas, trajetoria

TIPOS = ('incluir', 'arquivar', 'reativar', 'mudar_meta', 'dividir')


def _agora() -> str:
    return datetime.now().isoformat(timespec='seconds')


def _limpar(texto: str) -> str:
    """Texto real (visível para quem entrou); o envio ao modelo mascara conforme `mascarar_modelo`."""
    return str(texto or '').strip()


def _propostas_de(proposta_json: str | None) -> tuple[dict | None, list[dict]]:
    if not proposta_json:
        return None, []
    try:
        dados = json.loads(proposta_json)
    except ValueError:
        return None, []
    if not isinstance(dados, dict):
        return None, []
    hist = dados.get('historico')
    if isinstance(hist, list):
        atual = dados.get('atual') or (hist[-1] if hist else None)
        return atual, hist
    if any(k in dados for k in ('nivel_partida', 'meta', 'acoes', 'partes')):
        return dados, [dados]
    return None, []


def _montar_pedido(con: sqlite3.Connection, r: sqlite3.Row) -> dict:
    atual, hist = _propostas_de(r['proposta_json'])
    leitura_obj = None
    if r['leitura_id'] is not None:
        lr = con.execute('SELECT * FROM leitura WHERE id = ?', (r['leitura_id'],)).fetchone()
        if lr is not None:
            try:
                b = json.loads(lr['base_json'] or '{}')
            except ValueError:
                b = {}
            leitura_obj = {
                'id': int(lr['id']),
                'alvo_tipo': lr['alvo_tipo'],
                'alvo_id': lr['alvo_id'],
                'texto': lr['texto'],
                'base': b,
                'base_hash': lr['base_hash'],
                'modelo': lr['modelo'],
                'criado_em': lr['criado_em'],
                'vencida': False,
            }
    return {
        'id': int(r['id']),
        'tipo': r['tipo'],
        'prisma': r['prisma'],
        'motivo': r['motivo'] or '',
        'estado': r['estado'],
        'proposta': atual,
        'propostas': hist,
        'leitura_id': r['leitura_id'],
        'leitura': leitura_obj,
        'criado_em': r['criado_em'],
        'decidido_em': r['decidido_em'],
    }


def _nivel(valor, padrao: int) -> int:
    """Nível 0–5 vindo do modelo; valor ausente ou fora do formato fica com o padrão."""
    try:
        n = int(valor)
    except (TypeError, ValueError):
        n = int(padrao)
    return max(0, min(5, n))


def _ganho_niveis(con: sqlite3.Connection, tipo: str, nome: str, nivel_novo: int, meta_nova: int) -> int:
    """Diferença na soma de max(0, meta − nível) dos prismas ativos, antes × depois (spec, seção 11)."""
    ativos = {p['nome']: p for p in trajetoria.prismas(con)}
    antes = sum(max(0, p['meta'] - p['nivel']) for p in ativos.values())
    depois = sum(max(0, p['meta'] - p['nivel']) for k, p in ativos.items() if k != nome)
    if tipo != 'arquivar':
        depois += max(0, meta_nova - nivel_novo)
    return depois - antes


def abrir(con: sqlite3.Connection, tipo: str, prisma: str, motivo: str = '') -> dict:
    """Abre um pedido formal de mudança; recusa (ValueError) se já há pedido aberto ou proposto para o prisma."""
    if tipo not in TIPOS:
        raise ValueError(f'tipo de pedido inválido: {tipo!r}')
    nome = (prisma or '').strip()
    if not nome:
        raise ValueError('informe o nome do prisma')
    if tipo == 'incluir':
        nome = prismas.exigir_isolado(nome)
    elif tipo in ('dividir', 'reativar'):
        linha = con.execute('SELECT estado FROM prisma WHERE nome = ?', (nome,)).fetchone()
        if tipo == 'dividir':
            if linha is None:
                raise ValueError(f'prisma desconhecido: {nome}')
            if linha['estado'] != 'ativo':
                raise ValueError(f'o prisma {nome} está arquivado; só um prisma ativo pode ser dividido')
            if not prismas.composto(nome):
                raise ValueError(f'o prisma {nome} já é uma habilidade só')
        elif linha is not None and con.execute(
                "SELECT 1 FROM pedido WHERE tipo = 'dividir' AND estado = 'aceito' AND prisma = ?", (nome,)).fetchone():
            raise ValueError(f'o prisma {nome} foi dividido em habilidades; reative uma delas')
    motivo_limpo = _limpar((motivo or '').strip())
    with banco.transacao(con):
        aberto = con.execute(
            "SELECT id FROM pedido WHERE prisma = ? AND estado IN ('aberto', 'proposto')",
            (nome,),
        ).fetchone()
        if aberto is not None:
            raise ValueError(f'já existe um pedido em aberto para o prisma {nome}')
        quando = _agora()
        cur = con.execute(
            "INSERT INTO pedido (tipo, prisma, motivo, proposta_json, estado, criado_em) "
            "VALUES (?, ?, ?, ?, 'aberto', ?)",
            (tipo, nome, motivo_limpo, json.dumps({'atual': None, 'historico': []}, ensure_ascii=False), quando),
        )
        pid = int(cur.lastrowid)
    r = con.execute('SELECT * FROM pedido WHERE id = ?', (pid,)).fetchone()
    return _montar_pedido(con, r)


def _partes_validas(con: sqlite3.Connection, antigo: str, nomes: list[str]) -> list[str]:
    """Nomes das partes limpos: cada um uma habilidade só, sem repetir e sem bater com outro prisma (ValueError)."""
    limpos = [prismas.exigir_isolado(n) for n in nomes if _limpar(n)]
    if not limpos:
        raise ValueError('informe ao menos uma habilidade para o prisma novo')
    if len({n.casefold() for n in limpos}) != len(limpos):
        raise ValueError('as habilidades da divisão precisam ter nomes diferentes')
    if limpos == [antigo]:
        raise ValueError('a divisão precisa trocar o nome do prisma')
    for n in limpos:
        if con.execute('SELECT 1 FROM prisma WHERE nome = ?', (n,)).fetchone() is not None:
            raise ValueError(f'já existe um prisma {n}; escolha outro nome para esta parte')
    return limpos


def _destinos(con: sqlite3.Connection, antigo: str, nomes: list[str], palavras: dict[str, list[str]],
              movidos: dict[str, str]) -> list[dict]:
    """Avanços do prisma antigo (todos os estados) com a parte de destino: a escolha da pessoa ou a classificação."""
    out = []
    for r in con.execute('SELECT * FROM avanco WHERE prisma = ? ORDER BY rowid', (antigo,)).fetchall():
        f = jogo._feixe(r, [])
        auto = prismas.classificar(f, nomes, palavras)
        para = movidos.get(r['id'], auto)
        out.append({'id': r['id'], 'titulo': f.get('titulo') or '', 'estado': r['estado'], 'para': para,
                    'sugestao': auto, 'movido': para != auto})
    return out


def _propor_dividir(con: sqlite3.Connection, r: sqlite3.Row, partes: list[str] | None,
                    mover: dict[str, str] | None) -> dict:
    """Proposta determinística (sem modelo) de dividir um prisma composto; cada ajuste fica no histórico."""
    pid, antigo = int(r['id']), r['prisma']
    linha = con.execute('SELECT * FROM prisma WHERE nome = ?', (antigo,)).fetchone()
    if linha is None:
        raise ValueError(f'prisma desconhecido: {antigo}')
    nv, mt = int(linha['nivel'] or 0), int(linha['meta'] if linha['meta'] is not None else 4)
    try:
        palavras_antigas = json.loads(linha['palavras_json'] or '[]')
    except ValueError:
        palavras_antigas = []
    _, hist = _propostas_de(r['proposta_json'])
    anterior = hist[-1] if hist and isinstance(hist[-1], dict) and hist[-1].get('partes') else None
    nomes_antes = [x['nome'] for x in anterior['partes']] if anterior else None
    pedidas = list(partes) if partes is not None else (nomes_antes or prismas.partes(antigo))
    nomes = _partes_validas(con, antigo, pedidas)
    # renomear uma parte (mesmo número de partes) leva junto os avanços que a pessoa já tinha movido para ela
    renome = dict(zip(nomes_antes, nomes)) if nomes_antes and len(nomes_antes) == len(nomes) else {}
    movidos = {a: renome.get(p, p) for a, p in ((anterior or {}).get('movidos') or {}).items()}
    movidos = {a: p for a, p in movidos.items() if p in nomes}
    ids = {row[0] for row in con.execute('SELECT id FROM avanco WHERE prisma = ?', (antigo,))}
    for a, p in (mover or {}).items():
        p = _limpar(p)
        if a not in ids:
            raise ValueError(f'a centelha {a} não é do prisma {antigo}')
        if p not in nomes:
            raise ValueError(f'a parte {p} não está nesta divisão ({", ".join(nomes)})')
        movidos[a] = p
    palavras = prismas.repartir_palavras(palavras_antigas, nomes)
    lacuna = max(0, mt - nv)
    prop = {
        'partes': [{'nome': n, 'nivel': nv, 'meta': mt, 'palavras': palavras[n]} for n in nomes],
        'avancos': _destinos(con, antigo, nomes, palavras, movidos),
        'movidos': movidos,
        'nivel_partida': nv,
        'meta': mt,
        'palavras_chave': palavras_antigas,
        'acoes': [],
        'ganho_niveis': lacuna * len(nomes) - lacuna,
        'quando': _agora(),
    }
    with banco.transacao(con):
        con.execute("UPDATE pedido SET proposta_json = ?, estado = 'proposto' WHERE id = ?",
                    (json.dumps({'atual': prop, 'historico': [*hist, prop]}, ensure_ascii=False), pid))
    return _montar_pedido(con, con.execute('SELECT * FROM pedido WHERE id = ?', (pid,)).fetchone())


def propor(con: sqlite3.Connection, pedido_id: int, nivel: int | None = None, meta: int | None = None,
           partes: list[str] | None = None, mover: dict[str, str] | None = None) -> dict:
    """Gera (ou ajusta) a proposta de mudança da Luzia e registra no histórico de propostas do pedido.

    `partes` e `mover` só valem para `dividir`: os nomes das habilidades e {id do avanço: parte de destino}.
    """
    r = con.execute('SELECT * FROM pedido WHERE id = ?', (int(pedido_id),)).fetchone()
    if r is None:
        raise ValueError(f'pedido desconhecido: {pedido_id}')
    if r['estado'] in ('aceito', 'recusado'):
        raise ValueError(f"este pedido já foi {r['estado']}")
    if r['tipo'] == 'dividir':
        return _propor_dividir(con, r, partes, mover)

    pid = int(r['id'])
    tipo = r['tipo']
    nome = r['prisma']
    _, hist = _propostas_de(r['proposta_json'])
    atual_prisma = con.execute('SELECT * FROM prisma WHERE nome = ?', (nome,)).fetchone()
    nv_atual = int(atual_prisma['nivel'] or 0) if atual_prisma is not None else 0
    mt_atual = int(atual_prisma['meta'] if atual_prisma is not None and atual_prisma['meta'] is not None else 4)
    try:
        palavras_atuais = json.loads(atual_prisma['palavras_json'] or '[]') if atual_prisma is not None else []
    except ValueError:
        palavras_atuais = []

    if tipo in ('arquivar', 'reativar'):
        nv_prop = nv_atual
        mt_prop = int(meta) if meta is not None else mt_atual
        prop = {
            'nivel_partida': nv_prop,
            'meta': mt_prop,
            'palavras_chave': palavras_atuais,
            'acoes': [],
            'ganho_niveis': _ganho_niveis(con, tipo, nome, nv_prop, mt_prop),
            'quando': _agora(),
        }
        novo_hist = [*hist, prop]
        with banco.transacao(con):
            con.execute(
                "UPDATE pedido SET proposta_json = ?, estado = 'proposto' WHERE id = ?",
                (json.dumps({'atual': prop, 'historico': novo_hist}, ensure_ascii=False), pid),
            )
        r_novo = con.execute('SELECT * FROM pedido WHERE id = ?', (pid,)).fetchone()
        return _montar_pedido(con, r_novo)

    # Tipos 'incluir' e 'mudar_meta' consultam o modelo e gravam leitura com base
    b = leituras.base(con, 'pedido', str(pid))
    b_hash = leituras.hash_base(b)
    nv_pedido = nv_atual if tipo == 'mudar_meta' else (int(nivel) if nivel is not None else None)
    mt_pedido = int(meta) if meta is not None else None
    payload = {
        'base': b,
        'pedido': {
            'id': pid,
            'tipo': tipo,
            'prisma': nome,
            'motivo': r['motivo'] or '',
            'nivel_atual': nv_atual if atual_prisma is not None else None,
            'meta_atual': mt_atual if atual_prisma is not None else None,
            'nivel_solicitado': nv_pedido,
            'meta_solicitada': mt_pedido,
        },
    }
    t0 = time.perf_counter()
    indisponivel = ''
    try:
        res, rec = pipeline.run_plan(
            payload,
            prep_seconds=time.perf_counter() - t0,
            label='pedido-propor',
            save_current_state=False,
            schema=planner.PEDIDO_SCHEMA,
            intro='Fatos da trajetória atual e pedido de mudança feito pela pessoa desenvolvedora:',
        )
        dados_llm = res.plan if isinstance(res.plan, dict) else {}
    except Exception as e:  # sem modelo, sem chave ou sem internet: a proposta sai dos valores da própria pessoa
        arquivos.registrar_erro('pedidos.propor', e)
        res, rec, dados_llm = None, {}, {}
        indisponivel = f'análise indisponível: {modelo.resumo_erro(e)}'

    if tipo == 'mudar_meta':
        nv_final = nv_atual
    elif nv_pedido is not None:
        nv_final = max(0, min(5, nv_pedido))
    else:
        nv_final = _nivel(dados_llm.get('nivel_partida'), nv_atual if indisponivel else (nv_atual or 1))

    if mt_pedido is not None:
        mt_final = max(0, min(5, mt_pedido))
    else:
        mt_final = _nivel(dados_llm.get('meta'), mt_atual or 4)

    palavras = [str(w).strip() for w in (dados_llm.get('palavras_chave') or palavras_atuais) if str(w).strip()]
    if not palavras and indisponivel:  # fato, não leitura: as palavras do próprio nome do prisma
        palavras = [w for w in nome.replace('/', ' ').split() if len(w) >= 4]
    acoes_brutas = [a for a in (dados_llm.get('acoes') or []) if isinstance(a, dict) and a.get('titulo')][:3]
    for a in acoes_brutas:
        a['skill'] = nome
        a['dimensao'] = None
    # Só texto do modelo vira leitura; sem análise do modelo, nada de frase montada fingindo ser a Luzia.
    analise = _limpar(dados_llm.get('analise') or '') if isinstance(dados_llm.get('analise'), str) else ''

    prop = {
        'nivel_partida': nv_final,
        'meta': mt_final,
        'palavras_chave': palavras,
        'acoes': acoes_brutas,
        'analise': analise,
        'ganho_niveis': _ganho_niveis(con, tipo, nome, nv_final, mt_final),
        'quando': (rec or {}).get('quando') or _agora(),
    }
    if indisponivel:
        prop['leitura_indisponivel'] = indisponivel
    novo_hist = [*hist, prop]
    modelo_nome = (rec or {}).get('modelo') or getattr(res, 'model', '') or 'desconhecido'
    quando = prop['quando']

    with banco.transacao(con):
        lid = None
        if analise:
            cur_l = con.execute(
                'INSERT INTO leitura (alvo_tipo, alvo_id, texto, base_json, base_hash, modelo, criado_em) '
                "VALUES ('pedido', ?, ?, ?, ?, ?, ?)",
                (str(pid), analise, json.dumps(b, ensure_ascii=False, sort_keys=True), b_hash, modelo_nome, quando),
            )
            lid = int(cur_l.lastrowid)
        con.execute(  # a leitura ligada é sempre a desta proposta (ou nenhuma): uma análise velha não fica
            "UPDATE pedido SET proposta_json = ?, leitura_id = ?, estado = 'proposto' WHERE id = ?",
            (json.dumps({'atual': prop, 'historico': novo_hist}, ensure_ascii=False), lid, pid),
        )
    r_novo = con.execute('SELECT * FROM pedido WHERE id = ?', (pid,)).fetchone()
    return _montar_pedido(con, r_novo)


def _recalcular_valores_avancos(con: sqlite3.Connection, plan: dict) -> None:
    nv = jogo.niveis(plan, con)
    nomes = list(nv)
    for r in con.execute("SELECT * FROM avanco WHERE estado != 'conquistado'"):
        f = jogo._feixe(r, [])
        val, conta = jogo.valor(f, plan, nv, nomes)
        con.execute(
            'UPDATE avanco SET valor_lm = ?, conta_json = ? WHERE id = ?',
            (val, json.dumps(conta, ensure_ascii=False), r['id']),
        )


def aceitar(con: sqlite3.Connection, pedido_id: int) -> dict:
    """Aceita o pedido proposto: atualiza o prisma, registra nível/avanços se couber e cria nova versão da trajetória."""
    r = con.execute('SELECT * FROM pedido WHERE id = ?', (int(pedido_id),)).fetchone()
    if r is None:
        raise ValueError(f'pedido desconhecido: {pedido_id}')
    if r['estado'] in ('aceito', 'recusado'):
        raise ValueError(f"este pedido já foi {r['estado']}")

    pid = int(r['id'])
    tipo = r['tipo']
    nome = r['prisma']
    prop, _ = _propostas_de(r['proposta_json'])
    if prop is None:
        if tipo in ('arquivar', 'reativar', 'dividir'):
            propor(con, pid)
            r = con.execute('SELECT * FROM pedido WHERE id = ?', (pid,)).fetchone()
            prop, _ = _propostas_de(r['proposta_json'])
        else:
            raise ValueError('gere uma proposta antes de aceitar o pedido')

    quando = _agora()
    with banco.transacao(con):
        existente = con.execute('SELECT * FROM prisma WHERE nome = ?', (nome,)).fetchone()
        plan = trajetoria.perfil_ler(con, 'plano') or {}

        if tipo == 'incluir':
            nv = int(prop.get('nivel_partida', 0))
            mt = int(prop.get('meta', 4))
            palavras = list(prop.get('palavras_chave') or [])
            if existente is None:
                con.execute(
                    "INSERT INTO prisma (nome, palavras_json, nivel, meta, estado, origem, ultimo_nivel_em, criado_em) "
                    "VALUES (?, ?, ?, ?, 'ativo', 'pedido', ?, ?)",
                    (nome, json.dumps(palavras, ensure_ascii=False), nv, mt, quando, quando),
                )
                con.execute(
                    "INSERT INTO nivel_registro (prisma, de, para, quando, origem) VALUES (?, NULL, ?, ?, 'pedido')",
                    (nome, nv, quando),
                )
            else:
                de_nv = int(existente['nivel'] or 0)
                con.execute(
                    "UPDATE prisma SET palavras_json = ?, nivel = ?, meta = ?, estado = 'ativo', ultimo_nivel_em = ? WHERE nome = ?",
                    (json.dumps(palavras, ensure_ascii=False), nv, mt, quando, nome),
                )
                if de_nv != nv:
                    con.execute(
                        "INSERT INTO nivel_registro (prisma, de, para, quando, origem) VALUES (?, ?, ?, ?, 'pedido')",
                        (nome, de_nv, nv, quando),
                    )
            nv_map = jogo.niveis(plan, con)
            nomes_skills = list(nv_map)
            for a in prop.get('acoes') or []:
                fid = acoes.aid('pedido', f"{nome}|{a.get('titulo', '')}")
                feixe_novo = {
                    **a,
                    'id': fid,
                    'skill': nome,
                    'skill_plano': nome,
                    'origem': 'pedido',
                    'estado': 'sugerido',
                    'criado_em': quando,
                }
                feixe_novo['valor_lm'], feixe_novo['conta'] = jogo.valor(feixe_novo, plan, nv_map, nomes_skills)
                jogo._inserir_avanco(con, feixe_novo)

        elif tipo == 'mudar_meta':
            if existente is None:
                raise ValueError(f'prisma desconhecido: {nome}')
            mt = int(prop.get('meta', existente['meta'] or 4))
            con.execute('UPDATE prisma SET meta = ? WHERE nome = ?', (mt, nome))
            nv_map = jogo.niveis(plan, con)
            nomes_skills = list(nv_map)
            for a in prop.get('acoes') or []:
                fid = acoes.aid('pedido', f"{nome}|{a.get('titulo', '')}")
                feixe_novo = {
                    **a,
                    'id': fid,
                    'skill': nome,
                    'skill_plano': nome,
                    'origem': 'pedido',
                    'estado': 'sugerido',
                    'criado_em': quando,
                }
                feixe_novo['valor_lm'], feixe_novo['conta'] = jogo.valor(feixe_novo, plan, nv_map, nomes_skills)
                jogo._inserir_avanco(con, feixe_novo)

        elif tipo == 'dividir':
            _aceitar_dividir(con, nome, existente, prop, plan, quando)
            plan = trajetoria.perfil_ler(con, 'plano') or {}

        elif tipo == 'arquivar':
            if existente is None:
                raise ValueError(f'prisma desconhecido: {nome}')
            con.execute("UPDATE prisma SET estado = 'arquivado' WHERE nome = ?", (nome,))

        elif tipo == 'reativar':
            if existente is None:
                raise ValueError(f'prisma desconhecido: {nome}')
            mt = int(prop.get('meta', existente['meta'] or 4))
            con.execute("UPDATE prisma SET estado = 'ativo', meta = ? WHERE nome = ?", (mt, nome))

        _recalcular_valores_avancos(con, plan)
        versao_num = trajetoria.acrescentar_versao(con, 'pedido', pid)
        con.execute("UPDATE pedido SET estado = 'aceito', decidido_em = ? WHERE id = ?", (quando, pid))

    r_novo = con.execute('SELECT * FROM pedido WHERE id = ?', (pid,)).fetchone()
    out = _montar_pedido(con, r_novo)
    out['versao'] = versao_num
    return out


def _aceitar_dividir(con: sqlite3.Connection, antigo: str, existente, prop: dict, plan: dict, quando: str) -> None:
    """Dentro da transação de `aceitar`: cria as partes com nível e meta herdados, move os avanços e arquiva o antigo."""
    if existente is None:
        raise ValueError(f'prisma desconhecido: {antigo}')
    if existente['estado'] != 'ativo':
        raise ValueError(f'o prisma {antigo} não está mais ativo')
    partes_prop = [x for x in prop.get('partes') or [] if isinstance(x, dict) and x.get('nome')]
    nomes = _partes_validas(con, antigo, [x['nome'] for x in partes_prop])
    nv, mt = int(existente['nivel'] or 0), int(existente['meta'] if existente['meta'] is not None else 4)
    palavras = {x['nome']: list(x.get('palavras') or []) for x in partes_prop}
    escolhidos = {a['id']: a['para'] for a in prop.get('avancos') or [] if a.get('para') in nomes}
    destinos = _destinos(con, antigo, nomes, palavras, escolhidos)  # avanço novo depois da proposta: classificação
    for n in nomes:
        con.execute("INSERT INTO prisma (nome, palavras_json, nivel, meta, estado, origem, ultimo_nivel_em, criado_em) "
                    "VALUES (?, ?, ?, ?, 'ativo', 'pedido', ?, ?)",
                    (n, json.dumps(palavras.get(n, []), ensure_ascii=False), nv, mt, quando, quando))
        con.execute("INSERT INTO nivel_registro (prisma, de, para, quando, origem) VALUES (?, NULL, ?, ?, 'pedido')",
                    (n, nv, quando))
    for a in destinos:
        conteudo = json.loads(con.execute('SELECT conteudo_json FROM avanco WHERE id = ?', (a['id'],)).fetchone()[0] or '{}')
        conteudo.update(skill=a['para'], prisma_fixo=a['para'], dividido_de=antigo)
        con.execute('UPDATE avanco SET prisma = ?, conteudo_json = ? WHERE id = ?',
                    (a['para'], json.dumps(conteudo, ensure_ascii=False), a['id']))
    con.execute("UPDATE prisma SET estado = 'arquivado' WHERE nome = ?", (antigo,))
    skills = plan.get('skills') if isinstance(plan.get('skills'), list) else []
    if any(isinstance(s, dict) and s.get('nome') == antigo for s in skills):  # o plano salvo passa a falar das partes
        novas = []
        for s in skills:
            if isinstance(s, dict) and s.get('nome') == antigo:
                novas.extend({**s, 'nome': n, 'palavras_chave': palavras.get(n, []), 'dividido_de': antigo} for n in nomes)
            else:
                novas.append(s)
        trajetoria.perfil_gravar(con, 'plano', {**plan, 'skills': novas})


def dividir_todos(con: sqlite3.Connection) -> list[dict]:
    """Abre e propõe um pedido `dividir` para cada prisma ativo composto que ainda não tem pedido em aberto."""
    out = []
    abertos = {r[0] for r in con.execute("SELECT prisma FROM pedido WHERE estado IN ('aberto', 'proposto')")}
    for p in trajetoria.prismas(con):
        if p['nome'] in abertos or not prismas.composto(p['nome']):
            continue
        ped = abrir(con, 'dividir', p['nome'], 'um prisma por habilidade')
        try:
            ped = propor(con, ped['id'])
        except ValueError as e:  # parte com nome já usado: o pedido fica aberto para a pessoa ajustar os nomes
            ped = {**ped, 'erro': str(e)}
        out.append(ped)
    return out


def recusar(con: sqlite3.Connection, pedido_id: int) -> dict:
    """Recusa o pedido sem tocar nos prismas, avanços, níveis ou versões da trajetória."""
    r = con.execute('SELECT * FROM pedido WHERE id = ?', (int(pedido_id),)).fetchone()
    if r is None:
        raise ValueError(f'pedido desconhecido: {pedido_id}')
    if r['estado'] == 'aceito':
        raise ValueError('este pedido já foi aceito')
    pid = int(r['id'])
    with banco.transacao(con):
        con.execute("UPDATE pedido SET estado = 'recusado', decidido_em = ? WHERE id = ?", (_agora(), pid))
    r_novo = con.execute('SELECT * FROM pedido WHERE id = ?', (pid,)).fetchone()
    return _montar_pedido(con, r_novo)


def listar(con: sqlite3.Connection) -> list[dict]:
    """Todos os pedidos de mudança, do mais recente ao mais antigo."""
    return [_montar_pedido(con, r) for r in con.execute('SELECT * FROM pedido ORDER BY id DESC')]
