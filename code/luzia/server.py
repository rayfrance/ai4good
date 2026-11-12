"""Servidor local do painel da Luzia (biblioteca padrão; só escuta em 127.0.0.1:8501).

Serve a página `painel/` e uma API JSON montada a partir do estado salvo, das ações,
das evidências e dos eventos mascarados da sessão.
"""

from __future__ import annotations

import json
import mimetypes
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from luzia import acoes, jogo, modelo, pipeline, propriedade  # noqa: E402

HERE = Path(__file__).resolve().parent
PAINEL = HERE / 'painel'
PORT = 8501
MODOS = ('ativo', 'passivo', 'sob_demanda')
AGENTES = ('claude-code', 'codex', 'cursor', 'antigravity', 'outro')


def repo_cwd() -> str:
    return pipeline.read_json(pipeline.PRIVATE / 'entrada.json', {}).get('repo', str(Path.home()))


def ultima_execucao() -> dict:
    if not pipeline.RUNS.exists():
        return {}
    linhas = [ln for ln in pipeline.RUNS.read_text(encoding='utf-8').splitlines() if ln.strip()]
    return json.loads(linhas[-1]) if linhas else {}


def proxima(lista: list[dict]) -> dict | None:
    """Próximo feixe: em andamento > na fila > maior valor em lúmens."""
    ordem = {'em_andamento': 0, 'na_fila': 1, 'sugerido': 2}
    pend = [a for a in lista if a.get('estado') in ordem]
    pend.sort(key=lambda a: (ordem[a['estado']], -int(a.get('valor_lm', 0))))
    return pend[0] if pend else None


def estado() -> dict:
    state = pipeline.load_state()
    plan = state.get('plano', {})
    if not plan:
        return {'vazio': True}
    autoaval = pipeline.read_json(pipeline.AUTOAVAL, {})
    rota_jogo = jogo.rota(plan)
    por_skill = {s['nome']: s for s in rota_jogo['skills']}
    d = jogo._degraus()
    diag = plan.get('diagnostico_fontes', {})
    skills = []
    for s in plan.get('skills', []):
        voce = autoaval.get(s['nome'])
        skills.append({
            'nome': s['nome'], 'voce': voce if voce is not None else s.get('luzia_sugere'),
            'autoavaliada': voce is not None, 'alvo': s.get('alvo'), 'sugere': s.get('luzia_sugere'),
            'evidencia': s.get('evidencia', ''), **por_skill.get(s['nome'], {}),
            'degraus': [h for h in d.get('historico', []) if h['skill'] == s['nome']],
        })
    cfg = pipeline.read_json(pipeline.PRIVATE / 'entrada.json', {})

    cwd = repo_cwd()
    lista = acoes.todas(plan, descartados=True)
    for a in lista:
        a['link'] = acoes.deep_link(a['id'], cwd)
        a['comando'] = f"/luzia:fazer {a['id']}"
        a['prompt_completo'] = acoes.prompt_completo(a)

    commits = (plan.get('_commits_dia') or []) + ((state.get('payload_anonimizado') or {}).get('commits_recentes') or [])
    evs = acoes.evidencias()
    entregas = []
    for t in plan.get('tarefas_recentes', []):
        p = propriedade.entrega(t, commits, plan.get('p1_direcao_prompt'), evs)
        entregas.append({'tarefa': t.get('tarefa'), 'skills': t.get('skills', []),
                         'risco': t.get('risco_debito_tecnico', ''), **p,
                         'acoes': [a['id'] for a in lista if a.get('entrega') == t.get('tarefa')]})
    indices = [e['indice'] for e in entregas if e['indice'] is not None]

    lm_recentes = list(reversed(jogo.livro()))[:12]

    return {
        'perfil': {'onde': plan.get('onde_esta', {}).get('resumo', ''),
                   'meta': plan.get('aonde_quer_chegar', {}).get('resumo', ''),
                   'lacuna': plan.get('aonde_quer_chegar', {}).get('lacuna_principal', ''),
                   'diagnostico': diag},
        'rota': rota_jogo,
        'ritmo': jogo.ritmo(plan, cfg.get('horizonte', '')),
        'modelo': modelo.status(),
        'regras': {'limiar': jogo.LIMIAR_DEGRAU, 'min_propria': int(jogo.MIN_PROPRIA * 100),
                   'passivo': jogo.PASSIVO, 'motivos': jogo.MOTIVOS},
        'autoavaliada': bool(autoaval),
        'propriedade_media': round(sum(indices) / len(indices)) if indices else None,
        'skills': skills,
        'acoes': lista,
        'proxima': proxima(lista),
        'entregas': entregas,
        'lumens': lm_recentes,
        'como_e_medido': propriedade.COMO_E_MEDIDO,
        'feitas': sum(1 for a in lista if a.get('estado') == 'conquistado'),
        'fila': [f['id'] for f in acoes.fila()],
        'modo': pipeline.read_json(pipeline.OBSERVER_CFG, {}).get('modo', 'ativo'),
        'agente': pipeline.read_json(pipeline.OBSERVER_CFG, {}).get('agente', 'claude-code'),
        'execucao': {k: ultima_execucao().get(k) for k in ('tempo_total_s', 'pico_memoria_mib', 'tokens_entrada', 'tokens_saida', 'versao', 'quando', 'modelo')},
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

    def do_GET(self) -> None:
        path = self.path.split('?')[0]
        if path == '/api/ping':
            return self._json({'ok': True})
        if path == '/api/estado':
            return self._json(estado())
        if path == '/api/sessao':
            return self._json(sessao())
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
        tamanho = int(self.headers.get('Content-Length', 0) or 0)
        try:
            dados = json.loads(self.rfile.read(tamanho) or b'{}')
        except Exception:
            return self._json({'erro': 'json inválido'}, 400)
        path = self.path.split('?')[0]
        if path == '/api/autoavaliacao':
            niveis = {str(k): max(0, min(5, int(v))) for k, v in dados.items()}
            pipeline.AUTOAVAL.parent.mkdir(parents=True, exist_ok=True)
            pipeline.AUTOAVAL.write_text(json.dumps(niveis, ensure_ascii=False, indent=2), encoding='utf-8')
            return self._json({'ok': True})
        if path == '/api/modo':
            modo = dados.get('modo')
            if modo not in MODOS:
                return self._json({'erro': 'modo inválido'}, 400)
            cfg = pipeline.read_json(pipeline.OBSERVER_CFG, {})
            cfg['modo'] = modo
            pipeline.OBSERVER_CFG.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding='utf-8')
            return self._json({'ok': True})
        if path == '/api/agente':
            agente = dados.get('agente')
            if agente not in AGENTES:
                return self._json({'erro': 'agente inválido'}, 400)
            cfg = pipeline.read_json(pipeline.OBSERVER_CFG, {})
            cfg['agente'] = agente
            pipeline.OBSERVER_CFG.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding='utf-8')
            return self._json({'ok': True})
        if path == '/api/enviar':
            a = acoes.find(pipeline.load_state().get('plano', {}), str(dados.get('id', '')))
            if not a:
                return self._json({'erro': 'ação não encontrada'}, 404)
            acoes.enfileirar(a['id'], a.get('titulo', ''))
            jogo.enfileirar(a['id'])
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
            res = jogo.subir(jogo.skill_de(str(dados.get('skill', '')), plan), plan)
            return self._json({k: v for k, v in res.items() if k != 'rota'}, 400 if res.get('erro') else 200)
        if path == '/api/iniciar':
            acoes.registrar_evento(str(dados.get('id', ''))[:8], 'iniciada', origem='painel')
            return self._json({'ok': True})
        return self._json({'erro': 'rota desconhecida'}, 404)


def main() -> None:
    ThreadingHTTPServer(('127.0.0.1', PORT), Handler).serve_forever()


if __name__ == '__main__':
    main()
