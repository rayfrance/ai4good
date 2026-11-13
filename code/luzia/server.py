"""Servidor local do painel da Luzia (biblioteca padrão; só escuta em 127.0.0.1:8501).

Serve a página `painel/` e uma API JSON montada a partir do banco SQLite, da trajetória,
dos prismas, dos avanços, das entregas, das leituras e dos pedidos de mudança.

Proteção contra outros sites abertos no navegador: só atende `Host` 127.0.0.1 nesta porta
(barra DNS rebinding) e só aceita POST com `Content-Type: application/json` vindo da própria página
(um site de fora não consegue mandar esse POST sem permissão de CORS, que este servidor nunca dá).

Entrada herdada do agente (`acesso.py`): `career-map` abre o painel com um link de uso único no fragmento
(`#entrar=<token>`), que a página troca por uma sessão de 30 dias em `/api/acesso/link`. Os arquivos do painel e as
rotas `ABERTAS_GET`/`ABERTAS_POST` (ping e acesso) não pedem sessão; qualquer outro caminho `/api...`, GET ou POST,
listado ou não, devolve 401 JSON sem um cookie `luzia_sessao` válido.
As proteções acima (Host, Origin/Sec-Fetch-Site, JSON, 64 KB) valem para todas as rotas, inclusive as de acesso.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import mimetypes
import os
import re
import secrets
import socket
from http.cookies import CookieError, SimpleCookie
import sys
from datetime import datetime, timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from luzia import (acesso, acoes, arquivos, banco, entregas, jogo, leituras, modelo, observer, pedidos, prismas,  # noqa: E402
                   pipeline, propriedade, trajetoria)

HERE = Path(__file__).resolve().parent
PAINEL = HERE / 'painel'
PORT = 8501
MODOS = ('ativo', 'passivo', 'sob_demanda')
AGENTES = observer.AGENTES
ENTREGAS_NA_TELA = 15
# Só 127.0.0.1: `localhost` pode resolver para ::1, onde outro processo local poderia escutar a mesma porta.
HOSTS_OK = {f'127.0.0.1:{PORT}'}
ORIGENS_OK = {f'http://{h}' for h in HOSTS_OK}
MAX_CORPO = 64 * 1024
AUTO_LEITURAS_MIN = 10  # leituras automáticas do painel: no máximo uma rodada a cada 10 minutos

# Rotas da API. Só as ABERTAS dispensam sessão; toda outra `/api...` (inclusive uma que ainda não exista) exige login.
ABERTAS_GET = ('/api/ping', '/api/acesso/estado')
ABERTAS_POST = ('/api/acesso/link', '/api/acesso/sair')
ROTAS_GET = ('/api/estado', '/api/sessao', '/api/avancos', '/api/entrega')
ROTAS_POST = ('/api/nivel', '/api/autoavaliacao', '/api/pedido', '/api/leituras', '/api/identidade',
              '/api/entrega/acender', '/api/entregas/ampliar', '/api/modo', '/api/agente', '/api/enviar', '/api/modelo',
              '/api/modelo/testar', '/api/descartar', '/api/restaurar', '/api/subir', '/api/acender', '/api/trecho',
              '/api/iniciar', '/api/privacidade')
PORTARIA = acesso.Portaria()  # links e sessões no banco privado; só o limite de links errados fica em memória
COOKIE_ATTRS = 'HttpOnly; SameSite=Strict; Path=/'  # sem Secure: o painel é http://127.0.0.1
COOKIE_MAX_AGE = acesso.SESSAO_MAX_S


# Identidade do painel: o chat só entrega um link de entrada a quem provar este segredo (ver `publicar_identidade`).
VERSAO = arquivos.versao_codigo()
SEGREDO: bytes | None = None
RE_DESAFIO = re.compile(r'^[0-9a-f]{32,128}$')


class ServidorPainel(ThreadingHTTPServer):
    """Servidor do painel com a porta só dele: sem SO_REUSEADDR e, no Windows, com SO_EXCLUSIVEADDRUSE, para que
    nenhum outro processo local ocupe 127.0.0.1:8501 junto com ele."""

    allow_reuse_address = False
    daemon_threads = True

    def server_bind(self) -> None:
        if hasattr(socket, 'SO_EXCLUSIVEADDRUSE'):
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        super().server_bind()


def caminho_identidade() -> Path:
    return arquivos.PRIVATE / 'painel.json'


def publicar_identidade() -> None:
    """Gera o segredo deste processo e grava em `private/painel.json` (com o PID). Só quem lê a pasta privada da pessoa
    (o chat dela) confere a prova do `/api/ping?desafio=`; um programa que ocupe a porta não sabe responder."""
    global SEGREDO
    SEGREDO = secrets.token_bytes(32)
    arquivos.gravar_json(caminho_identidade(), {'segredo': SEGREDO.hex(), 'pid': os.getpid(),
                                                'quando': datetime.now().isoformat(timespec='seconds')})


def resposta_ping(desafio: str) -> dict:
    """Sem desafio (ou sem segredo publicado): só `ok`. Com desafio: a prova HMAC, a versão do código, o esquema e o PID."""
    if SEGREDO is None or not RE_DESAFIO.match(desafio or ''):
        return {'ok': True}
    return {'ok': True, 'prova': hmac.new(SEGREDO, desafio.encode('ascii'), hashlib.sha256).hexdigest(),
            'versao': VERSAO, 'esquema': banco.ESQUEMA_VERSAO, 'pid': os.getpid()}


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
        avancos_todos = jogo.avancos(con)  # uma só lista de avanços para todas as entregas
        detalhes_git = [entregas.detalhe(con, e['id'], todos_avancos=avancos_todos) for e in entregas_git[:ENTREGAS_NA_TELA]]
        diag_entregas = None if entregas_git else entregas.diagnostico(con)
        tri = con.execute("SELECT modelo, quando, registro_json FROM chamada_modelo WHERE rotulo LIKE '%triage%' "
                          "ORDER BY id DESC LIMIT 1").fetchone()
        triagem_modelo = None
        if tri and tri['modelo']:
            try:
                reg = json.loads(tri['registro_json'] or '{}')
            except ValueError:
                reg = {}
            # Registro sem a marca veio de uma versão que sempre mascarava o envio.
            mascarado = reg.get('mascarar_modelo', True) if isinstance(reg, dict) else True
            triagem_modelo = {'modelo': tri['modelo'], 'quando': tri['quando'], 'mascarado': mascarado is not False}

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
            'nome_curto': prismas.nome_curto(nome),  # rótulo do painel e do chat; o nome completo vai no title
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
            # um prisma = uma habilidade: em quais habilidades este nome se divide ([] quando já é uma só)
            'divisao': prismas.partes(nome) if prismas.composto(nome) else [],
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
        'triagem_modelo': triagem_modelo,  # modelo e data da chamada da triagem (None se o registro não existe)
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
        'privacidade': {'mascarar_modelo': pipeline.mascarar_modelo(), 'termos': pipeline.termos_configurados()},
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

    def _cabecalhos_seguros(self) -> None:
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('X-Frame-Options', 'DENY')
        self.send_header('Referrer-Policy', 'no-referrer')

    def _json(self, data, code: int = 200, cabecalhos: list[tuple[str, str]] | None = None) -> None:
        body = json.dumps(data, ensure_ascii=False).encode('utf-8')
        self.send_response(code)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self._cabecalhos_seguros()
        cabecalhos = list(cabecalhos or [])
        renovada = getattr(self, '_sessao_renovada', None)
        if renovada and not any(n == 'Set-Cookie' for n, _ in cabecalhos):  # uso real: o cookie ganha mais 30 dias
            cabecalhos += self._cookie_sessao(renovada)
        for nome, valor in cabecalhos:
            self.send_header(nome, valor)
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    # ------------------------------------------------------------ login
    def _token(self) -> str | None:
        bruto = self.headers.get('Cookie') or ''
        if not bruto or len(bruto) > 4096:
            return None
        try:
            biscoito = SimpleCookie()
            biscoito.load(bruto)
        except CookieError:
            return None
        m = biscoito.get(acesso.COOKIE)
        return m.value if m is not None else None

    def _sessao_ok(self) -> bool:
        # Pedidos automáticos do painel (polling de 4 s, leituras automáticas) conferem a sessão sem renovar: uma aba
        # esquecida aberta cai após 30 dias sem um gesto da pessoa. Uso real renova a sessão e o cookie.
        automatico = (self.headers.get('X-Luzia-Auto') or '').strip() == '1'
        token = self._token()
        try:
            ok = PORTARIA.valida(token, renovar=not automatico)
        except acesso.AcessoIndisponivel as e:  # banco ocupado ou bloqueado: 503 com o motivo, a sessão continua
            self._acesso_indisponivel = str(e) or True
            return False
        if ok and not automatico:
            self._sessao_renovada = token
        return ok

    def _indisponivel(self, motivo: str = '') -> None:
        self._json({'erro': motivo or 'a Luzia não conseguiu conferir a sua sessão agora; tente de novo'}, 503,
                   [('Retry-After', '1')])

    def _negar(self) -> None:
        motivo = getattr(self, '_acesso_indisponivel', False)
        if motivo:
            return self._indisponivel(motivo if isinstance(motivo, str) else '')
        self._json({'erro': 'abra o painel pelo seu agente (/luzia:career-map)', 'login': True}, 401)

    @staticmethod
    def _protegida(path: str, abertas: tuple[str, ...]) -> bool:
        return path.lower().startswith('/api') and path not in abertas

    def _estado_acesso(self) -> dict:
        return {'sessao_valida': PORTARIA.valida(self._token(), renovar=False)}

    @staticmethod
    def _cookie_sessao(token: str) -> list[tuple[str, str]]:
        return [('Set-Cookie', f'{acesso.COOKIE}={token}; Max-Age={COOKIE_MAX_AGE}; {COOKIE_ATTRS}')]

    def _acesso(self, path: str, dados: dict) -> None:
        """Rotas abertas de acesso: trocar o link de uso único por uma sessão, e sair. Tokens nunca voltam nem vão ao log."""
        if path == '/api/acesso/link':
            r = PORTARIA.entrar_por_link(dados.get('token'))
            if r.indisponivel:
                return self._indisponivel(r.indisponivel)
            if r.limitado_s:
                return self._json({'erro': f'muitas tentativas: espere {r.limitado_s} s', 'segundos': r.limitado_s},
                                  429, [('Retry-After', str(r.limitado_s))])
            if not r.token:
                return self._json({'erro': 'este link já foi usado ou venceu: abra o painel pelo seu agente '
                                           '(/luzia:career-map)'}, 401)
            try:  # a sessão que este navegador trazia é trocada pela nova
                PORTARIA.fechar(self._token())
            except acesso.AcessoIndisponivel:
                pass
            return self._json({'ok': True}, 200, self._cookie_sessao(r.token))
        try:  # /api/acesso/sair: encerra só a sessão deste navegador
            PORTARIA.fechar(self._token())
        except acesso.AcessoIndisponivel as e:
            return self._indisponivel(str(e))
        return self._json({'ok': True}, 200, [('Set-Cookie', f'{acesso.COOKIE}=; Max-Age=0; {COOKIE_ATTRS}')])

    def _descartar_o_que_chegou(self) -> None:
        """Corpo declarado grande demais: lê (até 64 KB) só o que já chegou e fecha a conexão depois da resposta.
        Sem isso, fechar com bytes não lidos faz o Windows mandar RST e o cliente perde a resposta 413."""
        self.close_connection = True
        try:
            self.connection.settimeout(0.2)
            lido = 0
            while lido < MAX_CORPO:
                pedaco = self.rfile.read1(MAX_CORPO - lido)
                if not pedaco:
                    break
                lido += len(pedaco)
        except (OSError, ValueError):
            pass

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
        self._acesso_indisponivel = False
        self._sessao_renovada = None
        if self._barrar(post=False):
            return
        parsed = urlparse(self.path)
        path = parsed.path
        qs = parse_qs(parsed.query)
        if self._protegida(path, ABERTAS_GET) and not self._sessao_ok():
            return self._negar()
        if path == '/api/ping':
            return self._json(resposta_ping((qs.get('desafio') or [''])[0]))
        if path == '/api/acesso/estado':
            try:
                return self._json(self._estado_acesso())
            except acesso.AcessoIndisponivel as e:
                return self._indisponivel(str(e))
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
        self._cabecalhos_seguros()
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self) -> None:
        self._acesso_indisponivel = False
        self._sessao_renovada = None
        if self._barrar(post=True):
            return
        try:
            tamanho = int(self.headers.get('Content-Length', 0) or 0)
        except ValueError:
            return self._json({'erro': 'tamanho inválido'}, 400)
        if tamanho > MAX_CORPO:
            self._descartar_o_que_chegou()
            return self._json({'erro': 'pedido grande demais'}, 413)
        corpo = self.rfile.read(tamanho) if tamanho > 0 else b''
        path = self.path.split('?')[0]
        if path not in ABERTAS_POST and not self._sessao_ok():  # todo POST fora do acesso exige sessão
            return self._negar()
        try:
            dados = json.loads(corpo or b'{}')
            if not isinstance(dados, dict):
                raise ValueError
        except Exception:
            return self._json({'erro': 'json inválido'}, 400)
        try:
            if path in ABERTAS_POST:
                return self._acesso(path, dados)
            self._post(path, dados)
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
                if tipo in ('incluir', 'mudar_meta', 'dividir') and dados.get('propor', True):
                    p = pedidos.propor(con, p['id'], nivel=nivel, meta=meta)
                return p
            if acao not in ('ajustar', 'propor', 'aceitar', 'recusar'):
                raise ValueError('ação de pedido inválida')
            pid = numero('id', 'número do pedido')
            if pid is None:
                raise ValueError('informe o número do pedido')
            if acao in ('ajustar', 'propor'):
                partes, mover = dados.get('partes'), dados.get('mover')
                if partes is not None and not (isinstance(partes, list) and all(isinstance(x, str) for x in partes)):
                    raise ValueError('partes: envie a lista de nomes das habilidades')
                if mover is not None and not (isinstance(mover, dict)
                                              and all(isinstance(v, str) for v in mover.values())):
                    raise ValueError('mover: envie {centelha: habilidade}')
                return pedidos.propor(con, pid, nivel=numero('nivel', 'nível'), meta=numero('meta', 'meta'),
                                      partes=partes, mover=mover)
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
                if str(dados.get('acao', '')).strip().lower() == 'dividir_todos':
                    with trajetoria.abrir() as con:
                        return self._json({'ok': True, 'pedidos': pedidos.dividir_todos(con)})
                return self._json({'ok': True, 'pedido': self._pedido(dados)})
            except (ValueError, RuntimeError) as e:  # pedido duplicado, já decidido, id ou número inválido
                return self._json({'erro': str(e)}, 400)

        if path == '/api/leituras':
            alvos_raw = dados.get('alvos')
            alvos = [tuple(x) for x in alvos_raw] if isinstance(alvos_raw, list) else None
            with trajetoria.abrir() as con:
                if alvos is None:  # o que a tela mostra (prismas + entregas exibidas), nunca o banco inteiro
                    alvos = leituras.vencidas(con, None if dados.get('todas') else ENTREGAS_NA_TELA)
                if dados.get('auto'):
                    alvos = leituras.vencidas(con, ENTREGAS_NA_TELA)[:leituras.LOTES_AUTOMATICOS * leituras.TAMANHO_LOTE]
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
            try:
                dias = max(1, min(3650, int(dados.get('dias', 180) or 180)))
            except (TypeError, ValueError):
                return self._json({'erro': 'número de dias inválido'}, 400)
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

        if path == '/api/privacidade':
            ligado = dados.get('mascarar_modelo')
            if not isinstance(ligado, bool):
                return self._json({'erro': 'use mascarar_modelo: true ou false'}, 400)
            pipeline.definir_mascarar_modelo(ligado)
            return self._json({'ok': True, 'mascarar_modelo': pipeline.mascarar_modelo()})

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
                return self._json({'erro': 'centelha não encontrada'}, 404)
            if not jogo.enfileirar(a['id']):
                return self._json({'erro': 'esta centelha já foi acesa (e revisitada) ou está descartada'}, 400)
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
            try:
                res = cli.gerar_trecho(alvo, 'painel-acender')
            except Exception as e:  # sem modelo, sem chave ou sem internet: mensagem clara, nada gravado
                arquivos.registrar_erro('server acender', e)
                return self._json({'erro': f'não deu para acender centelhas sem o modelo ({modelo.resumo_erro(e)})'}, 400)
            if res.get('erro'):
                return self._json({'erro': res['erro']}, 400)
            ids = [f['id'] for f in res['feixes']]
            return self._json({'ok': True, 'skill': res['skill'], 'prisma': res['skill'], 'feixes': ids, 'avancos': ids})

        if path == '/api/iniciar':
            a = acoes.find(pipeline.load_state().get('plano', {}), str(dados.get('id', '')))
            if not a or not jogo.iniciar(a['id'], 'prompt copiado do painel'):
                return self._json({'erro': 'esta centelha não pode ser iniciada agora'}, 400)
            acoes.registrar_evento(a['id'], 'iniciada', skill=a.get('skill'), origem='painel')
            return self._json({'ok': True})

        return self._json({'erro': 'rota desconhecida'}, 404)


def main() -> None:
    httpd = ServidorPainel(('127.0.0.1', PORT), Handler)  # porta exclusiva antes de publicar o segredo
    publicar_identidade()
    httpd.serve_forever()


if __name__ == '__main__':
    main()
