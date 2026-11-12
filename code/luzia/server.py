"""Servidor local do painel da Luzia (biblioteca padrão; só escuta em 127.0.0.1:8501).

Serve a página `painel/` e uma API JSON montada a partir do banco SQLite, da trajetória,
dos prismas, dos avanços, das entregas, das leituras e dos pedidos de mudança.

Proteção contra outros sites abertos no navegador: só atende `Host` localhost/127.0.0.1 nesta porta
(barra DNS rebinding) e só aceita POST com `Content-Type: application/json` vindo da própria página
(um site de fora não consegue mandar esse POST sem permissão de CORS, que este servidor nunca dá).
"""

from __future__ import annotations

import json
import mimetypes
import sys
from datetime import datetime, timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from luzia import (acoes, arquivos, banco, entregas, jogo, leituras, modelo, observer, pedidos,  # noqa: E402
                   pipeline, propriedade, trajetoria)

HERE = Path(__file__).resolve().parent
PAINEL = HERE / 'painel'
PORT = 8501
MODOS = ('ativo', 'passivo', 'sob_demanda')
AGENTES = observer.AGENTES
HOSTS_OK = {f'localhost:{PORT}', f'127.0.0.1:{PORT}'}
ORIGENS_OK = {f'http://{h}' for h in HOSTS_OK}
MAX_CORPO = 64 * 1024
AUTO_LEITURAS_MIN = 10  # leituras automáticas do painel: no máximo uma rodada a cada 10 minutos


def repo_cwd() -> str:
    return pipeline.read_json(pipeline.PRIVATE / 'entrada.json', {}).get('repo', str(Path.home()))


def ultima_execucao() -> dict:
    if not pipeline.RUNS.exists():
        return {}
    linhas = [ln for ln in pipeline.RUNS.read_text(encoding='utf-8').splitlines() if ln.strip()]
    return json.loads(linhas[-1]) if linhas else {}


def proxima(lista: list[dict]) -> dict | None:
    """Próximo avanço: em andamento > na fila > maior valor em lúmens."""
    ordem = {'em_andamento': 0, 'na_fila': 1, 'sugerido': 2}
    pend = [a for a in lista if a.get('estado') in ordem]
    pend.sort(key=lambda a: (ordem[a['estado']], -int(a.get('valor_lm', 0))))
    return pend[0] if pend else None


def _enriquecer_avanco(a: dict, cwd: str) -> dict:
    a['link'] = acoes.deep_link(a['id'], cwd)
    a['comando'] = f"/luzia:fazer {a['id']}"
    a['prompt_completo'] = acoes.prompt_completo(a)
    return a


def _espectro(nivel: int, total: int = 5) -> list[int]:
    n = max(0, min(total, int(nivel or 0)))
    return [1 if i <= n else 0 for i in range(1, total + 1)]


def estado() -> dict:
    state = pipeline.load_state()
    plan = state.get('plano', {})
    if not plan:
        return {'vazio': True}
    autoaval = jogo.autoavaliacao()
    cwd = repo_cwd()
    lista = [_enriquecer_avanco(a, cwd) for a in acoes.todas(plan, descartados=True)]

    with trajetoria.abrir() as con:
        rota_jogo = jogo.rota(plan, con)
        por_skill = {s['nome']: s for s in rota_jogo['skills']}
        d = jogo._degraus(con)
        versoes = trajetoria.versoes(con)
        todos_prismas_db = trajetoria.prismas(con, incluir_arquivados=True)
        leituras_prismas = {p['nome']: leituras.obter(con, 'prisma', p['nome']) for p in todos_prismas_db}
        lista_pedidos = pedidos.listar(con)
        entregas_git = entregas.listar(con)
        detalhes_git = [entregas.detalhe(con, e['id']) for e in entregas_git[:15]]
        diag_entregas = None if entregas_git else entregas.diagnostico(con)

    diag = plan.get('diagnostico_fontes', {})
    plan_skills_map = {s['nome']: s for s in plan.get('skills', []) if isinstance(s, dict) and s.get('nome')}
    prismas_out = []
    for p in todos_prismas_db:
        nome = p['nome']
        s_plan = plan_skills_map.get(nome, {})
        voce = autoaval.get(nome)
        prog = por_skill.get(nome) or {
            'nome': nome,
            'nivel': p['nivel'],
            'meta': p['meta'],
            'proximo': min(p['meta'], p['nivel'] + 1),
            'na_meta': p['nivel'] >= p['meta'],
            **jogo.progresso_skill(nome, d),
        }
        subidas = [h for h in d.get('historico', []) if h['skill'] == nome]
        prismas_out.append({
            'nome': nome,
            'estado': p['estado'],
            'origem': p['origem'],
            'palavras': p.get('palavras', []),
            'voce': voce if voce is not None else p['nivel'],
            'autoavaliada': voce is not None,
            'alvo': p['meta'],
            'meta': p['meta'],
            'nivel': p['nivel'],
            'sugere': s_plan.get('luzia_sugere', p['nivel']),
            'evidencia': s_plan.get('evidencia', ''),
            'espectro': _espectro(p['nivel']),
            'leitura': leituras_prismas.get(nome),
            **prog,
            'avancos_conquistados': prog.get('feixes', 0),
            'degraus': subidas,
            'niveis_conquistados': subidas,
        })

    skills_ativas = [p for p in prismas_out if p['estado'] == 'ativo']
    cfg = pipeline.read_json(pipeline.PRIVATE / 'entrada.json', {})

    entregas_out = []
    for det in detalhes_git:
        if not det:
            continue
        prop = det.get('propriedade', {})
        entregas_out.append({
            'id': det['id'],
            'titulo': det['titulo'],
            'tarefa': det['titulo'],
            'fonte': det.get('fonte', 'git'),
            'fatos': det['fatos'],
            'prismas': det['prismas'],
            'skills': [x['prisma'] for x in det['prismas']],
            'indice': prop.get('indice'),
            'base': prop.get('base', ''),
            'dimensoes': prop.get('dimensoes', {}),
            'propriedade': prop,
            'leitura': det.get('leitura'),
            'avancos_feitos': [a['id'] for a in det.get('avancos_feitos', [])],
            'avancos_uteis': [a['id'] for a in det.get('avancos_uteis', [])],
            'acoes': [a['id'] for a in det.get('avancos_uteis', [])],
            'lumens_ligados': det.get('lumens_ligados', []),
        })
    indices = [e['indice'] for e in entregas_out if e.get('indice') is not None]
    # Leituras vencidas ou faltando, contadas no que esta tela já calculou (sem recalcular as bases).
    leituras_vencidas = sum(1 for p in todos_prismas_db if p['estado'] == 'ativo'
                            and (not leituras_prismas.get(p['nome']) or leituras_prismas[p['nome']]['vencida']))
    leituras_vencidas += sum(1 for e in entregas_out if not e.get('leitura') or e['leitura'].get('vencida'))

    lm_recentes = list(reversed(jogo.livro(limite=12)))
    modo_atual = pipeline.read_json(pipeline.OBSERVER_CFG, {}).get('modo', 'ativo')
    modo_nome = observer.NOMES_FOCO.get(modo_atual, modo_atual)

    r_ritmo = jogo.ritmo(plan, cfg.get('horizonte', ''))
    r_ritmo['avancos_semana'] = r_ritmo.get('feixes_semana', 1)

    return {
        'perfil': {
            'onde': plan.get('onde_esta', {}).get('resumo', ''),
            'rotulos': list(pipeline.rotulos(state)),
            'meta': plan.get('aonde_quer_chegar', {}).get('resumo', ''),
            'lacuna': plan.get('aonde_quer_chegar', {}).get('lacuna_principal', ''),
            'diagnostico': diag,
        },
        'trajetoria': {
            'versao_atual': versoes[-1]['numero'] if versoes else 1,
            'versoes': versoes,
            'resumo': rota_jogo,
        },
        'rota': rota_jogo,
        'ritmo': r_ritmo,
        'modelo': modelo.status(),
        'modelo_pronto': modelo.pronto(),
        'leituras_vencidas': leituras_vencidas,
        'regras': {
            'limiar': jogo.LIMIAR_DEGRAU,
            'min_propria': int(jogo.MIN_PROPRIA * 100),
            'min_feixes': jogo.MIN_FEIXES_DEGRAU,
            'min_avancos': jogo.MIN_FEIXES_DEGRAU,
            'teto_passivo_dia': jogo.TETO_PASSIVO_DIA,
            'passivo': jogo.PASSIVO,
            'motivos': jogo.MOTIVOS,
            'rubrica': propriedade.RUBRICA,
        },
        'autoavaliada': bool(autoaval),
        'propriedade_media': round(sum(indices) / len(indices)) if indices else None,
        'prismas': prismas_out,
        'skills': skills_ativas,
        'avancos': lista,
        'acoes': lista,
        'proxima': proxima(lista),
        'entregas': entregas_out,
        'entregas_diagnostico': diag_entregas,
        'lumens': lm_recentes,
        'pedidos': lista_pedidos,
        'como_e_medido': propriedade.COMO_E_MEDIDO,
        'feitas': sum(1 for a in lista if a.get('estado') == 'conquistado'),
        'fila': [f['id'] for f in acoes.fila()],
        'modo': modo_atual,
        'modo_nome': modo_nome,
        'foco_opcoes': observer.NOMES_FOCO,
        'agente': pipeline.read_json(pipeline.OBSERVER_CFG, {}).get('agente', 'claude-code'),
        'execucao': {
            k: ultima_execucao().get(k)
            for k in ('tempo_total_s', 'pico_memoria_mib', 'tokens_entrada', 'tokens_saida', 'versao', 'quando', 'modelo')
        },
        'atualizado_em': state.get('atualizado_em', ''),
    }


def sessao() -> dict:
    evs = list(reversed(pipeline.session_events(40)))
    return {'eventos': evs, 'intervencoes': sum(1 for e in evs if e.get('interveio'))}


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *_):
        pass

    def _json(self, data, code: int = 200) -> None:
        body = json.dumps(data, ensure_ascii=False).encode('utf-8')
        self.send_response(code)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Cache-Control', 'no-store')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _drenar(self) -> None:
        try:
            n = min(MAX_CORPO, int(self.headers.get('Content-Length', 0) or 0))
            if n > 0:
                self.rfile.read(n)
        except Exception:
            pass

    def _barrar(self, post: bool) -> bool:
        """True (e já responde) quando o pedido não vem da própria página local."""
        if (self.headers.get('Host') or '').lower() not in HOSTS_OK:
            if post:
                self._drenar()
            self._json({'erro': 'host não permitido'}, 403)
            return True
        if not post:
            return False
        origem = (self.headers.get('Origin') or '').lower()
        site = self.headers.get('Sec-Fetch-Site') or 'same-origin'
        if (origem and origem not in ORIGENS_OK) or site not in ('same-origin', 'none'):
            self._drenar()
            self._json({'erro': 'origem não permitida'}, 403)
            return True
        if not (self.headers.get('Content-Type') or '').lower().startswith('application/json'):
            self._drenar()
            self._json({'erro': 'use Content-Type: application/json'}, 415)
            return True
        return False

    def _api(self, funcao) -> None:
        try:
            self._json(funcao())
        except Exception as e:
            arquivos.registrar_erro(f'server {self.path.split("?")[0]}', e)
            self._json({'erro': f'a Luzia não conseguiu montar esta tela ({type(e).__name__})'}, 500)

    def do_GET(self) -> None:
        if self._barrar(post=False):
            return
        parsed = urlparse(self.path)
        path = parsed.path
        qs = parse_qs(parsed.query)
        if path == '/api/ping':
            return self._json({'ok': True})
        if path == '/api/estado':
            return self._api(estado)
        if path == '/api/sessao':
            return self._api(sessao)
        if path == '/api/avancos':
            try:
                plan = pipeline.load_state().get('plano', {})
                jogo.sincronizar(plan)
                est_f = (qs.get('estado') or [''])[0] or None
                pri_raw = (qs.get('prisma') or qs.get('skill') or [''])[0] or None
                pri_f = jogo.skill_de(pri_raw, plan) if pri_raw else None
                tip_f = (qs.get('tipo') or [''])[0] or None
                cwd = repo_cwd()
                with trajetoria.abrir() as con:
                    itens = [_enriquecer_avanco(a, cwd) for a in jogo.avancos(con, estado=est_f, prisma=pri_f, tipo=tip_f)]
                return self._json({'avancos': itens})
            except Exception as e:
                arquivos.registrar_erro('server GET /api/avancos', e)
                return self._json({'erro': str(e)}, 500)
        if path == '/api/entrega':
            eid_str = (qs.get('id') or [''])[0]
            if not eid_str.isdigit():
                return self._json({'erro': 'id de entrega inválido'}, 400)
            try:
                plan = pipeline.load_state().get('plano', {})
                jogo.sincronizar(plan)
                cwd = repo_cwd()
                with trajetoria.abrir() as con:
                    det = entregas.detalhe(con, int(eid_str))
                if not det:
                    return self._json({'erro': 'entrega não encontrada'}, 404)
                det['avancos_feitos'] = [_enriquecer_avanco(a, cwd) for a in det.get('avancos_feitos', [])]
                det['avancos_uteis'] = [_enriquecer_avanco(a, cwd) for a in det.get('avancos_uteis', [])]
                return self._json(det)
            except Exception as e:
                arquivos.registrar_erro('server GET /api/entrega', e)
                return self._json({'erro': str(e)}, 500)
        arquivo = PAINEL / ('index.html' if path in ('/', '') else path.lstrip('/'))
        if not arquivo.resolve().is_relative_to(PAINEL.resolve()) or not arquivo.is_file():
            self.send_error(404)
            return
        body = arquivo.read_bytes()
        self.send_response(200)
        self.send_header('Content-Type', mimetypes.guess_type(arquivo.name)[0] or 'application/octet-stream')
        self.send_header('Cache-Control', 'no-store')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self) -> None:
        if self._barrar(post=True):
            return
        try:
            tamanho = int(self.headers.get('Content-Length', 0) or 0)
        except ValueError:
            return self._json({'erro': 'tamanho inválido'}, 400)
        if tamanho > MAX_CORPO:
            return self._json({'erro': 'pedido grande demais'}, 413)
        try:
            dados = json.loads(self.rfile.read(tamanho) or b'{}')
            if not isinstance(dados, dict):
                raise ValueError
        except Exception:
            return self._json({'erro': 'json inválido'}, 400)
        try:
            self._post(self.path.split('?')[0], dados)
        except Exception as e:
            arquivos.registrar_erro(f'server POST {self.path.split("?")[0]}', e)
            self._json({'erro': f'não deu certo ({type(e).__name__})'}, 500)

    @staticmethod
    def _pedido(dados: dict) -> dict:
        """Uma ação de pedido de mudança; erro de uso levanta ValueError (vira 400 com a mensagem)."""
        def numero(chave: str, rotulo: str) -> int | None:
            v = dados.get(chave)
            if v is None or v == '':
                return None
            if isinstance(v, bool) or not str(v).lstrip('#').isdigit():
                raise ValueError(f'{rotulo} inválido: use um número')
            return int(str(v).lstrip('#'))

        acao = str(dados.get('acao', '')).strip().lower()
        with trajetoria.abrir() as con:
            if acao == 'abrir':
                tipo = str(dados.get('tipo', '')).strip()
                prisma = str(dados.get('prisma') or dados.get('skill') or '').strip()
                nivel, meta = numero('nivel', 'nível'), numero('meta', 'meta')
                p = pedidos.abrir(con, tipo, prisma, str(dados.get('motivo', '')).strip())
                if tipo in ('incluir', 'mudar_meta') and dados.get('propor', True):
                    p = pedidos.propor(con, p['id'], nivel=nivel, meta=meta)
                return p
            if acao not in ('ajustar', 'propor', 'aceitar', 'recusar'):
                raise ValueError('ação de pedido inválida')
            pid = numero('id', 'número do pedido')
            if pid is None:
                raise ValueError('informe o número do pedido')
            if acao in ('ajustar', 'propor'):
                return pedidos.propor(con, pid, nivel=numero('nivel', 'nível'), meta=numero('meta', 'meta'))
            if acao == 'aceitar':
                return pedidos.aceitar(con, pid)
            return pedidos.recusar(con, pid)

    def _post(self, path: str, dados: dict) -> None:
        if path in ('/api/nivel', '/api/autoavaliacao'):
            if 'prisma' in dados or 'skill' in dados:
                nome = str(dados.get('prisma') or dados.get('skill') or '')
                nv = dados.get('nivel')
                if isinstance(nv, bool) or not isinstance(nv, int):
                    return self._json({'erro': 'nível inválido'}, 400)
                mapa = {nome: nv}
            elif isinstance(dados.get('niveis'), dict):
                mapa = dados['niveis']
            else:
                mapa = dados
            if any(isinstance(v, bool) or not isinstance(v, int) for v in mapa.values()):
                return self._json({'erro': 'nível inválido'}, 400)
            niveis = {str(k): max(0, min(5, v)) for k, v in mapa.items()}
            with trajetoria.abrir() as con:
                atuais = {p['nome']: p['nivel'] for p in trajetoria.prismas(con, incluir_arquivados=True)}
                if any(nome not in atuais for nome in niveis):
                    return self._json({'erro': 'prisma desconhecido'}, 400)
                declarados = trajetoria.declarados(con)
                for nome, nivel in niveis.items():
                    if atuais[nome] != nivel or nome not in declarados:
                        trajetoria.declarar_nivel(con, nome, nivel)
            return self._json({'ok': True})

        if path == '/api/pedido':
            try:
                return self._json({'ok': True, 'pedido': self._pedido(dados)})
            except (ValueError, RuntimeError) as e:  # pedido duplicado, já decidido, id ou número inválido
                return self._json({'erro': str(e)}, 400)

        if path == '/api/leituras':
            alvos_raw = dados.get('alvos')
            alvos = [tuple(x) for x in alvos_raw] if isinstance(alvos_raw, list) else None
            with trajetoria.abrir() as con:
                if dados.get('auto'):  # o painel pede sozinho ao abrir: só com modelo e no máximo 1 vez a cada 10 min
                    if not modelo.pronto():
                        return self._json({'ok': True, 'geradas': 0, 'sem_modelo': True})
                    with banco.transacao(con):
                        ultima = trajetoria.perfil_ler(con, 'leituras_auto_em') or ''
                        agora = datetime.now()
                        if ultima and agora - datetime.fromisoformat(ultima) < timedelta(minutes=AUTO_LEITURAS_MIN):
                            return self._json({'ok': True, 'geradas': 0, 'adiado': True})
                        trajetoria.perfil_gravar(con, 'leituras_auto_em', agora.isoformat(timespec='seconds'))
                geradas = leituras.gerar(con, alvos=alvos)
            return self._json({'ok': True, 'geradas': geradas})

        if path == '/api/identidade':
            with trajetoria.abrir() as con:
                try:
                    entregas.acrescentar_identidade(con, str(dados.get('identidade') or ''))
                except ValueError as e:
                    return self._json({'erro': str(e)}, 400)
                return self._json({'ok': True, 'identidades': entregas.diagnostico(con)['identidades']})

        if path == '/api/entrega/acender':
            eid = str(dados.get('id', ''))
            if not eid.isdigit():
                return self._json({'erro': 'id de entrega inválido'}, 400)
            from luzia import cli
            res = cli.acender_entrega(int(eid), 'painel-acender-entrega')
            if res.get('erro'):
                return self._json({'erro': res['erro']}, 400)
            return self._json({'ok': True, 'avancos': [a['id'] for a in res['avancos']]})

        if path == '/api/entregas/ampliar':
            dias = max(1, min(3650, int(dados.get('dias', 180) or 180)))
            with trajetoria.abrir() as con:
                res = entregas.atualizar(con, dias=dias)
            return self._json({'ok': True, 'atualizacao': res})

        if path == '/api/modo':
            modo = dados.get('modo')
            if modo not in MODOS:
                return self._json({'erro': 'modo inválido'}, 400)
            cfg = pipeline.read_json(pipeline.OBSERVER_CFG, {})
            cfg['modo'] = modo
            arquivos.gravar_json(pipeline.OBSERVER_CFG, cfg)
            return self._json({'ok': True, 'modo': modo, 'modo_nome': observer.NOMES_FOCO.get(modo, modo)})

        if path == '/api/agente':
            agente = dados.get('agente')
            if agente not in AGENTES:
                return self._json({'erro': 'agente inválido'}, 400)
            cfg = pipeline.read_json(pipeline.OBSERVER_CFG, {})
            cfg['agente'] = agente
            arquivos.gravar_json(pipeline.OBSERVER_CFG, cfg)
            return self._json({'ok': True})

        if path == '/api/enviar':
            a = acoes.find(pipeline.load_state().get('plano', {}), str(dados.get('id', '')))
            if not a:
                return self._json({'erro': 'avanço não encontrado'}, 404)
            if not jogo.enfileirar(a['id']):
                return self._json({'erro': 'este avanço já foi conquistado (e revisitado) ou está descartado'}, 400)
            acoes.enfileirar(a['id'], a.get('titulo', ''))
            return self._json({'ok': True})

        if path == '/api/modelo':
            try:
                st = modelo.salvar(str(dados.get('provedor', '')), str(dados.get('modelo', '')).strip(),
                                   str(dados.get('base_url', '')), str(dados.get('chave', '')))
            except ValueError as e:
                return self._json({'erro': str(e)}, 400)
            return self._json({'ok': True, 'modelo': st})

        if path == '/api/modelo/testar':
            try:
                r = modelo.chamar('Responda só com o JSON {"ok": true}.', 'Responda só com JSON.')
                return self._json({'ok': True, 'segundos': round(r['segundos'], 1), 'modelo': f"{r['provedor']}/{r['modelo']}",
                                   'aviso': r.get('aviso', '')})
            except Exception as e:
                return self._json({'erro': str(e)[:200]}, 400)

        if path in ('/api/descartar', '/api/restaurar'):
            fid = str(dados.get('id', ''))[:8]
            if path == '/api/descartar':
                if dados.get('motivo') not in jogo.MOTIVOS:
                    return self._json({'erro': 'motivo inválido'}, 400)
                jogo.descartar(fid, dados['motivo'])
                acoes.desenfileirar(fid)
            else:
                jogo.restaurar(fid)
            return self._json({'ok': True})

        if path == '/api/subir':
            plan = pipeline.load_state().get('plano', {})
            alvo = str(dados.get('prisma') or dados.get('skill') or '')
            res = jogo.subir(jogo.skill_de(alvo, plan), plan)
            return self._json({k: v for k, v in res.items() if k != 'rota'}, 400 if res.get('erro') else 200)

        if path in ('/api/acender', '/api/trecho'):
            from luzia import cli
            alvo = str(dados.get('prisma') or dados.get('skill') or '')[:120]
            res = cli.gerar_trecho(alvo, 'painel-acender')
            if res.get('erro'):
                return self._json({'erro': res['erro']}, 400)
            ids = [f['id'] for f in res['feixes']]
            return self._json({'ok': True, 'skill': res['skill'], 'prisma': res['skill'], 'feixes': ids, 'avancos': ids})

        if path == '/api/iniciar':
            a = acoes.find(pipeline.load_state().get('plano', {}), str(dados.get('id', '')))
            if not a or not jogo.iniciar(a['id'], 'prompt copiado do painel'):
                return self._json({'erro': 'este avanço não pode ser iniciado agora'}, 400)
            acoes.registrar_evento(a['id'], 'iniciada', skill=a.get('skill'), origem='painel')
            return self._json({'ok': True})

        return self._json({'erro': 'rota desconhecida'}, 404)


def main() -> None:
    ThreadingHTTPServer(('127.0.0.1', PORT), Handler).serve_forever()


if __name__ == '__main__':
    main()
