"""Qual modelo de IA a Luzia usa: provedor, modelo e chave, configuráveis pelo painel ou pela CLI.

- A escolha fica em `private/modelo.json` (fora do git).
- A chave fica no `.env` da raiz do repositório (fora do git) e nunca volta para a tela nem para logs.
- Cada provedor usa o SDK oficial, carregado só quando é o escolhido:
  Google Gemini (`google-genai`), Anthropic Claude (`anthropic`) e qualquer API compatível com OpenAI
  (`openai`: OpenAI, OpenRouter, Groq, Ollama local etc., com `base_url`).
"""

from __future__ import annotations

import importlib.util
import json
import os
import re
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
CFG = HERE / 'private' / 'modelo.json'
ENVS = [ROOT / '.env', ROOT.parent / 'ai4good' / '.env']

PROVEDORES = {
    'gemini': {'nome': 'Google Gemini', 'chave': 'GEMINI_API_KEY', 'sdk': 'google.genai', 'pip': 'google-genai',
               'sugestoes': ['gemini-3.5-flash-lite', 'gemini-2.5-flash', 'gemini-4-argon', 'gemini-4-carbon'], 'base_url': False},
    'anthropic': {'nome': 'Anthropic Claude', 'chave': 'ANTHROPIC_API_KEY', 'sdk': 'anthropic', 'pip': 'anthropic',
                  'sugestoes': ['claude-opus-5-5', 'claude-sonnet-5-5', 'claude-haiku-5-5'], 'base_url': False},
    'openai': {'nome': 'Compatível com OpenAI', 'chave': 'OPENAI_API_KEY', 'sdk': 'openai', 'pip': 'openai',
               'sugestoes': [], 'base_url': True},
}
PADRAO = {'provedor': 'gemini', 'modelo': 'gemini-3.5-flash-lite', 'base_url': ''}
# Modelos Claude que aceitam o fallback do servidor em caso de recusa (referência oficial da API).
CLAUDE_COM_FALLBACK = {'claude-fable-5-2', 'claude-fable-5-1', 'claude-opus-5-5', 'claude-opus-5', 'claude-sonnet-5-5'}
NOME_OK = re.compile(r'^[A-Za-z0-9._:/@-]{1,100}$')


def carregar_env() -> None:
    """Coloca no ambiente as chaves do .env que ainda não estão definidas."""
    nomes = {p['chave'] for p in PROVEDORES.values()}
    for env in ENVS:
        if not env.exists():
            continue
        for linha in env.read_text(encoding='utf-8').splitlines():
            nome, _, valor = linha.partition('=')
            nome = nome.strip()
            if nome in nomes and nome not in os.environ and valor.strip():
                os.environ[nome] = valor.strip().strip('"')


def config() -> dict:
    try:
        cfg = {**PADRAO, **json.loads(CFG.read_text(encoding='utf-8'))}
    except Exception:
        cfg = dict(PADRAO)
    if cfg['provedor'] not in PROVEDORES:
        cfg = dict(PADRAO)
    return cfg


def _gravar_chave(nome: str, valor: str) -> None:
    env = ENVS[0]
    linhas = env.read_text(encoding='utf-8').splitlines() if env.exists() else []
    linhas = [ln for ln in linhas if not ln.startswith(f'{nome}=')] + [f'{nome}={valor}']
    env.write_text('\n'.join(linhas) + '\n', encoding='utf-8')
    os.environ[nome] = valor


def salvar(provedor: str, modelo: str, base_url: str = '', chave: str = '') -> dict:
    if provedor not in PROVEDORES:
        raise ValueError('provedor inválido')
    if not NOME_OK.match(modelo or ''):
        raise ValueError('nome de modelo inválido')
    base_url = (base_url or '').strip()
    if base_url and not re.match(r'^https?://[^\s]{3,200}$', base_url):
        raise ValueError('base_url inválida')
    chave = (chave or '').strip()
    if chave:
        if len(chave) > 300 or any(c.isspace() for c in chave):
            raise ValueError('chave inválida')
        _gravar_chave(PROVEDORES[provedor]['chave'], chave)
    CFG.parent.mkdir(parents=True, exist_ok=True)
    CFG.write_text(json.dumps({'provedor': provedor, 'modelo': modelo,
                               'base_url': base_url if PROVEDORES[provedor]['base_url'] else ''},
                              ensure_ascii=False, indent=2), encoding='utf-8')
    return status()


def status() -> dict:
    """O que o painel pode mostrar: nunca a chave, só se ela existe."""
    carregar_env()
    cfg = config()
    prov = PROVEDORES[cfg['provedor']]
    chave = os.environ.get(prov['chave'], '')
    return {
        **cfg,
        'nome_provedor': prov['nome'],
        'chave_configurada': bool(chave),
        'sdk_instalado': importlib.util.find_spec(prov['sdk'].split('.')[0]) is not None and
                         (prov['sdk'] != 'google.genai' or importlib.util.find_spec('google.genai') is not None),
        'pip': prov['pip'],
        'provedores': {k: {'nome': v['nome'], 'sugestoes': v['sugestoes'], 'base_url': v['base_url'],
                           'chave_configurada': bool(os.environ.get(v['chave']))} for k, v in PROVEDORES.items()},
    }


def extrair_json(texto: str) -> dict:
    texto = (texto or '').strip()
    if texto.startswith('```'):
        texto = texto.split('\n', 1)[1] if '\n' in texto else texto
        texto = texto.rsplit('```', 1)[0]
    ini, fim = texto.find('{'), texto.rfind('}')
    return json.loads(texto[ini:fim + 1] if ini >= 0 and fim > ini else texto)


def chamar(prompt: str, system: str) -> dict:
    """Uma chamada ao modelo configurado. Devolve texto, tokens, segundos e o modelo que respondeu."""
    carregar_env()
    cfg = config()
    prov = PROVEDORES[cfg['provedor']]
    chave = os.environ.get(prov['chave'], '')
    if not chave and cfg['provedor'] != 'openai':
        raise RuntimeError(f"Falta a chave {prov['chave']}: configure em Ajustes > Modelo da Luzia.")
    if importlib.util.find_spec(prov['sdk'].split('.')[0]) is None:
        raise RuntimeError(f"O SDK de {prov['nome']} não está instalado: pip install {prov['pip']}")
    t0 = time.perf_counter()
    ULTIMO_ERRO_PRINCIPAL.clear()
    if cfg['provedor'] == 'gemini':
        texto, tin, tout, usado = _gemini(cfg['modelo'], prompt, system, chave)
    elif cfg['provedor'] == 'anthropic':
        texto, tin, tout, usado = _claude(cfg['modelo'], prompt, system, chave)
    else:
        texto, tin, tout, usado = _openai(cfg['modelo'], prompt, system, chave, cfg.get('base_url', ''))
    aviso = ''
    if usado != cfg['modelo'] and cfg['provedor'] == 'gemini':
        aviso = f"{cfg['modelo']} não respondeu ({ULTIMO_ERRO_PRINCIPAL.get('erro', 'erro')}); quem respondeu foi o reserva {usado}."
    return {'texto': texto, 'tokens_in': tin, 'tokens_out': tout, 'segundos': time.perf_counter() - t0,
            'modelo': usado, 'provedor': cfg['provedor'], 'configurado': cfg['modelo'], 'aviso': aviso}


ULTIMO_ERRO_PRINCIPAL: dict = {}


def resumo_erro(e: Exception) -> str:
    """Mensagem curta do erro, sem nada que pareça chave."""
    s = re.sub(r'AIza[0-9A-Za-z_-]+|sk-[0-9A-Za-z_-]+', '[chave]', str(e))
    if 'RESOURCE_EXHAUSTED' in s and 'limit: 0' in s:
        return 'cota zero para este modelo no plano da sua chave (ex.: plano gratuito); ative o faturamento ou escolha outro modelo'
    if 'RESOURCE_EXHAUSTED' in s:
        return 'cota esgotada no momento (limite de uso da chave)'
    if 'NOT_FOUND' in s or '404' in s:
        return 'modelo não encontrado para esta chave'
    if 'PERMISSION' in s or '403' in s or 'API_KEY' in s.upper() and 'INVALID' in s.upper():
        return 'chave sem permissão ou inválida'
    return s[:160]


def _gemini(modelo: str, prompt: str, system: str, chave: str):
    from google import genai
    from google.genai import types

    client = genai.Client(api_key=chave, http_options=types.HttpOptions(timeout=45_000))
    erro = None
    for m in dict.fromkeys([modelo, 'gemini-2.5-flash']):
        try:
            resp = client.models.generate_content(
                model=m, contents=prompt,
                config=types.GenerateContentConfig(system_instruction=system, temperature=0.2,
                                                   response_mime_type='application/json'),
            )
            u = resp.usage_metadata
            return resp.text or '', getattr(u, 'prompt_token_count', 0) or 0, getattr(u, 'candidates_token_count', 0) or 0, m
        except Exception as e:  # tenta o modelo reserva do mesmo provedor, mas registra por quê
            erro = e
            if m == modelo:
                ULTIMO_ERRO_PRINCIPAL['erro'] = resumo_erro(e)
    raise RuntimeError(f'Gemini falhou: {resumo_erro(erro)}')


def _claude(modelo: str, prompt: str, system: str, chave: str):
    import anthropic

    client = anthropic.Anthropic(api_key=chave, timeout=180.0)
    kwargs = dict(model=modelo, max_tokens=16000, system=system,
                  messages=[{'role': 'user', 'content': prompt}],
                  output_config={'effort': 'medium'})
    if modelo in CLAUDE_COM_FALLBACK:
        resp = client.beta.messages.create(betas=['server-side-fallback-2026-07-01'], fallbacks='default', **kwargs)
    else:
        resp = client.messages.create(**kwargs)
    if resp.stop_reason == 'refusal':
        raise RuntimeError('o modelo recusou a solicitação')
    texto = ''.join(b.text for b in resp.content if b.type == 'text')
    return texto, resp.usage.input_tokens, resp.usage.output_tokens, resp.model


def _openai(modelo: str, prompt: str, system: str, chave: str, base_url: str):
    from openai import OpenAI

    client = OpenAI(api_key=chave or 'sem-chave', base_url=base_url or None, timeout=180.0)
    resp = client.chat.completions.create(
        model=modelo,
        messages=[{'role': 'system', 'content': system}, {'role': 'user', 'content': prompt}],
        response_format={'type': 'json_object'},
    )
    u = resp.usage
    return (resp.choices[0].message.content or '', getattr(u, 'prompt_tokens', 0) or 0,
            getattr(u, 'completion_tokens', 0) or 0, resp.model or modelo)
