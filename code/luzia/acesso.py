"""Senha local do painel e sessões em memória (biblioteca padrão).

- A senha é criada no primeiro acesso ao painel (mínimo 8 caracteres, com confirmação) e fica só como hash
  PBKDF2-HMAC-SHA256 (600 000 iterações, sal aleatório de 16 bytes) em `private/acesso.json`, gravado de forma atômica.
  A conferência usa `hmac.compare_digest` (tempo constante).
- Sessão: token aleatório (`secrets.token_urlsafe(32)`) que só existe no cookie do navegador e, como SHA-256, na memória
  do servidor (token → último uso e versão do acesso). Expira após 30 min sem uso; cada uso renova. Reiniciar o servidor
  derruba todas.
- Força bruta: 5 erros seguidos travam a entrada por 60 s. O contador só zera com a senha certa, então depois da trava
  cada novo erro trava de novo.
- Redefinir (`senha` no chat/CLI, que já roda como a pessoa no sistema): apaga a senha e soma 1 à `versao` de
  `acesso.json`; toda sessão aberta com a versão antiga deixa de valer, inclusive em outro processo. Criar a senha também
  soma 1. Mudar a versão zera as tentativas erradas e a trava.
- Uma sessão por vez: entrar de novo encerra a sessão anterior.
- Hash com menos iterações que `ITERACOES` é refeito no próximo login certo (sem mudar a versão).
- Erro passageiro ao ler `acesso.json` (Windows: arquivo sendo trocado) é tentado de novo; se persistir, vira
  `AcessoIndisponivel` (o servidor responde 503), sem derrubar sessões nem contar como tentativa errada.
- Nada aqui grava ou devolve a senha, o hash ou o token em log ou resposta.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import secrets
import threading
import time
import unicodedata
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from . import arquivos

ALGORITMO = 'pbkdf2_sha256'
ITERACOES = 600_000
TAMANHO_SAL = 16
MIN_SENHA = 8
MAX_SENHA = 1024
SESSAO_MAX_S = 30 * 60
TENTATIVAS = 5
TRAVA_S = 60
COOKIE = 'luzia_sessao'
LEITURAS = 4             # tentativas de ler acesso.json antes de desistir
ESPERA_LEITURA_S = 0.05
_CRIAR = threading.Lock()


class SenhaJaExiste(RuntimeError):
    """Já há uma senha (ou um acesso.json que não dá para ler): criar outra exige redefinir pelo chat."""


class AcessoIndisponivel(RuntimeError):
    """`acesso.json` existe mas não deu para ler agora (erro de sistema passageiro): tente de novo."""


def caminho() -> Path:
    return arquivos.PRIVATE / 'acesso.json'


def _ler() -> tuple[dict, bool]:
    """(dados, legível). Arquivo ausente = vazio e legível; corrompido = vazio e ilegível (cópia guardada ao lado)."""
    p = caminho()
    for tentativa in range(LEITURAS):
        try:
            texto = p.read_text(encoding='utf-8')
            break
        except FileNotFoundError:
            return {}, True
        except OSError:
            if tentativa == LEITURAS - 1:
                arquivos.registrar_erro('acesso ler acesso.json', 'OSError')
                raise AcessoIndisponivel('não deu para ler a senha agora; tente de novo') from None
            time.sleep(ESPERA_LEITURA_S * (tentativa + 1))
    try:
        dados = json.loads(texto)
    except ValueError:
        arquivos.ler_json(p, {})  # guarda a cópia do arquivo ruim e registra só o tipo do erro
        return {}, False
    return (dados, True) if isinstance(dados, dict) else ({}, False)


def _versao_de(dados: dict) -> int:
    try:
        return int(dados.get('versao') or 0)
    except (TypeError, ValueError):
        return 0


def _situacao() -> tuple[int, bool]:
    """(versão, há senha) numa só leitura do arquivo."""
    dados, legivel = _ler()
    return _versao_de(dados), (not legivel or 'senha' in dados)


def _senha_valida(s) -> bool:
    try:
        return (isinstance(s, dict) and s.get('algoritmo') == ALGORITMO and int(s.get('iteracoes')) >= 1
                and len(bytes.fromhex(s['sal'])) >= TAMANHO_SAL and len(bytes.fromhex(s['hash'])) == 32)
    except (KeyError, TypeError, ValueError):
        return False


def versao() -> int:
    return _situacao()[0]


def tem_senha() -> bool:
    """True quando há senha, ou quando `acesso.json` existe mas não dá para ler (não deixa criar outra por cima)."""
    return _situacao()[1]


def _normalizar(senha: str) -> bytes:
    return unicodedata.normalize('NFC', senha).encode('utf-8')


def _derivar(senha: str, sal: bytes, iteracoes: int) -> bytes:
    return hashlib.pbkdf2_hmac('sha256', _normalizar(senha), sal, iteracoes)


def validar_nova(senha, confirmacao) -> str:
    if not isinstance(senha, str) or not isinstance(confirmacao, str):
        raise ValueError('informe a senha e a confirmação')
    if len(senha) < MIN_SENHA:
        raise ValueError(f'a senha precisa ter pelo menos {MIN_SENHA} caracteres')
    if len(senha) > MAX_SENHA:
        raise ValueError(f'a senha pode ter no máximo {MAX_SENHA} caracteres')
    if not hmac.compare_digest(_normalizar(senha), _normalizar(confirmacao)):
        raise ValueError('a confirmação não é igual à senha')
    return senha


def _registro(senha: str, criada_em: str | None = None) -> dict:
    sal = secrets.token_bytes(TAMANHO_SAL)
    iteracoes = max(int(ITERACOES), 1)
    return {'algoritmo': ALGORITMO, 'iteracoes': iteracoes, 'sal': sal.hex(),
            'hash': _derivar(senha, sal, iteracoes).hex(),
            'criada_em': criada_em or datetime.now().isoformat(timespec='seconds')}


def criar_senha(senha, confirmacao) -> None:
    """Grava o hash da senha nova (versão + 1). Só quando ainda não existe senha (SenhaJaExiste); regra inválida:
    ValueError. No primeiro uso e depois de `senha apagar`, quem chegar primeiro ao painel cria a senha."""
    validar_nova(senha, confirmacao)
    with _CRIAR:  # dois pedidos juntos no mesmo servidor: só o primeiro cria
        v, existe = _situacao()
        if existe:
            raise SenhaJaExiste('a senha do painel já existe')
        arquivos.gravar_json(caminho(), {'versao': v + 1, 'senha': _registro(senha)})


def _refazer_hash_se_fraco(senha: str) -> None:
    """Hash com menos iterações que o mínimo atual: regrava com sal novo e `ITERACOES`, mantendo a versão."""
    with _CRIAR:
        dados, legivel = _ler()
        s = dados.get('senha') if legivel else None
        if not _senha_valida(s) or int(s['iteracoes']) >= ITERACOES:
            return
        arquivos.gravar_json(caminho(), {**dados, 'senha': _registro(senha, s.get('criada_em'))})


def conferir(senha) -> bool:
    """Compara a senha com o hash guardado em tempo constante; sem senha (ou arquivo ilegível): False."""
    if not isinstance(senha, str) or not senha or len(senha) > MAX_SENHA:
        return False
    dados, legivel = _ler()
    s = dados.get('senha') if legivel else None
    if not _senha_valida(s):
        return False
    calculado = _derivar(senha, bytes.fromhex(s['sal']), int(s['iteracoes']))
    return hmac.compare_digest(calculado, bytes.fromhex(s['hash']))


def apagar_senha() -> int:
    """Apaga a senha e invalida as sessões abertas (versão + 1). Devolve a nova versão."""
    nova = versao() + 1
    arquivos.gravar_json(caminho(), {'versao': nova, 'redefinida_em': datetime.now().isoformat(timespec='seconds')})
    return nova


def _chave(token: str) -> str:
    return hashlib.sha256(token.encode('utf-8')).hexdigest()


@dataclass
class Entrada:
    token: str | None = None
    restantes: int = TENTATIVAS
    travado_s: int = 0
    sem_senha: bool = False
    indisponivel: bool = False


class Portaria:
    """Sessões e trava de tentativas, só em memória do servidor; `relogio` é injetável nos testes."""

    def __init__(self, relogio=time.monotonic):
        self.relogio = relogio
        self._sessoes: dict[str, tuple[float, int]] = {}  # sha256(token) → (último uso, versão do acesso)
        self._erros = 0
        self._travado_ate = 0.0
        self._versao_tentativas: int | None = None  # versão do acesso a que o contador de erros se refere
        self._trava = threading.Lock()

    # ------------------------------------------------------------ sessões
    def abrir(self, unica: bool = True) -> str:
        """Nova sessão; `unica` encerra as anteriores (uma sessão por vez)."""
        token = secrets.token_urlsafe(32)
        v = versao()
        with self._trava:
            if unica:
                self._sessoes.clear()
            self._limpar()
            self._sessoes[_chave(token)] = (self.relogio(), v)
        return token

    def _limpar(self) -> None:
        agora = self.relogio()
        for k in [k for k, (uso, _) in self._sessoes.items() if agora - uso > SESSAO_MAX_S]:
            del self._sessoes[k]

    def valida(self, token: str | None, renovar: bool = True) -> bool:
        """Sessão válida? `AcessoIndisponivel` (leitura passageira) sobe sem apagar a sessão."""
        if not token or not isinstance(token, str) or len(token) > 256:
            return False
        chave = _chave(token)
        with self._trava:
            if chave not in self._sessoes:
                return False
        v_atual, senha = _situacao()
        with self._trava:
            dado = self._sessoes.get(chave)
            if dado is None:
                return False
            uso, v = dado
            agora = self.relogio()
            if agora - uso > SESSAO_MAX_S or v != v_atual or not senha:
                del self._sessoes[chave]
                return False
            if renovar:
                self._sessoes[chave] = (agora, v)
            return True

    def fechar(self, token: str | None) -> None:
        if token and isinstance(token, str):
            with self._trava:
                self._sessoes.pop(_chave(token), None)

    def fechar_todas(self) -> None:
        with self._trava:
            self._sessoes.clear()

    # ------------------------------------------------------------ entrada
    def _acompanhar_versao(self, v: int) -> None:
        """Senha criada ou apagada (versão nova): as tentativas erradas e a trava recomeçam do zero."""
        if self._versao_tentativas is not None and v != self._versao_tentativas:
            self._erros = 0
            self._travado_ate = 0.0
        self._versao_tentativas = v

    def _restante(self) -> int:
        resto = self._travado_ate - self.relogio()
        return max(0, int(-(-resto // 1)))  # arredonda para cima

    def travado_s(self) -> int:
        try:
            v = versao()
        except AcessoIndisponivel:
            return self._restante()
        with self._trava:
            self._acompanhar_versao(v)
            return self._restante()

    def entrar(self, senha) -> Entrada:
        """Confere a senha (um pedido por vez); 5 erros seguidos travam por 60 s; erro de leitura não conta."""
        with self._trava:
            try:
                v, existe = _situacao()
                self._acompanhar_versao(v)
                espera = self._restante()
                if espera:
                    return Entrada(restantes=0, travado_s=espera)
                if not existe:
                    return Entrada(sem_senha=True)
                certa = conferir(senha)
            except AcessoIndisponivel:
                return Entrada(indisponivel=True, restantes=max(0, TENTATIVAS - self._erros))
            if not certa:
                self._erros += 1
                if self._erros >= TENTATIVAS:
                    self._travado_ate = self.relogio() + TRAVA_S
                    return Entrada(restantes=0, travado_s=TRAVA_S)
                return Entrada(restantes=TENTATIVAS - self._erros)
            self._erros = 0
            self._travado_ate = 0.0
        try:
            _refazer_hash_se_fraco(senha)
        except (AcessoIndisponivel, OSError) as e:  # a senha está certa: o hash é refeito no próximo login
            arquivos.registrar_erro('acesso refazer hash', e)
        return Entrada(token=self.abrir())
