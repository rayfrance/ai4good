"""
Módulo de clientes para modelos de linguagem.
Fornece clientes para Gemini (Google) e Ollama (Local).
"""

import os
import json
import logging
from abc import ABC, abstractmethod
from typing import Optional
from pathlib import Path

# Configuração de logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Tentativa de carregar .env da raiz do projeto
try:
    from dotenv import load_dotenv
    env_path = Path(__file__).resolve().parents[2] / '.env'
    load_dotenv(env_path)
except ImportError:
    logger.warning("Biblioteca python-dotenv não encontrada. Carregamento de arquivo .env ignorado.")


class BaseLLMClient(ABC):
    """Classe base abstrata para clientes de LLM."""

    def __init__(self, model_name: str):
        """
        Inicializa o cliente base.

        Args:
            model_name: O nome do modelo.
        """
        self._model_name = model_name

    @property
    def model_name(self) -> str:
        """Retorna o nome do modelo em uso."""
        return self._model_name

    @abstractmethod
    def generate(self, prompt: str, system_prompt: str = '') -> str:
        """
        Gera uma resposta baseada no prompt fornecido.

        Args:
            prompt: O texto do prompt principal.
            system_prompt: O prompt de sistema opcional.

        Returns:
            A resposta em texto gerada pelo LLM.
        """
        pass


class GeminiClient(BaseLLMClient):
    """Cliente para a API do Google Gemini."""

    def __init__(self, model_name: str = 'gemini-2.0-flash', api_key: Optional[str] = None):
        """
        Inicializa o cliente Gemini.

        Args:
            model_name: O nome do modelo Gemini a ser utilizado.
            api_key: Chave de API do Google. Se None, tenta ler de GEMINI_API_KEY.
        """
        super().__init__(model_name)
        self.api_key = api_key or os.environ.get('GEMINI_API_KEY')
        
        if not self.api_key:
            raise ValueError("Chave de API do Gemini não fornecida e a variável GEMINI_API_KEY não foi encontrada.")
            
        try:
            from google import genai
            self.client = genai.Client(api_key=self.api_key)
            self.types_module = genai.types
        except ImportError:
            raise ImportError("Biblioteca google-genai não encontrada. Por favor, instale-a para usar o GeminiClient.")

    def generate(self, prompt: str, system_prompt: str = '') -> str:
        """Gera uma resposta usando o modelo Gemini."""
        logger.info(f"Enviando prompt para o modelo Gemini: {self.model_name}")
        
        config_kwargs = {"temperature": 0.9}
        if system_prompt:
            config_kwargs["system_instruction"] = system_prompt
            
        try:
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=prompt,
                config=self.types_module.GenerateContentConfig(**config_kwargs)
            )
            return response.text
        except Exception as e:
            logger.error(f"Erro ao gerar resposta com Gemini: {e}")
            raise RuntimeError(f"Falha ao comunicar com a API do Gemini: {e}")


class OllamaClient(BaseLLMClient):
    """Cliente para servidor local Ollama via HTTP."""

    def __init__(self, model_name: str = 'llama3.1:8b'):
        """
        Inicializa o cliente Ollama.

        Args:
            model_name: O nome do modelo Ollama a ser utilizado.
        """
        super().__init__(model_name)
        self.endpoint = "http://localhost:11434/api/generate"

    def generate(self, prompt: str, system_prompt: str = '') -> str:
        """Gera uma resposta usando o servidor local Ollama."""
        try:
            import requests
        except ImportError:
            raise ImportError("Biblioteca requests não encontrada. Por favor, instale-a para usar o OllamaClient.")
            
        logger.info(f"Enviando prompt para o modelo Ollama: {self.model_name}")
        
        payload = {
            "model": self.model_name,
            "prompt": prompt,
            "stream": False
        }
        if system_prompt:
            payload["system"] = system_prompt
            
        try:
            response = requests.post(self.endpoint, json=payload)
            response.raise_for_status()
            result = response.json()
            return result.get('response', '')
        except requests.exceptions.ConnectionError:
            error_msg = "Não foi possível conectar ao servidor Ollama. O servidor local está em execução na porta 11434?"
            logger.error(error_msg)
            raise ConnectionError(error_msg)
        except Exception as e:
            logger.error(f"Erro ao gerar resposta com Ollama: {e}")
            raise RuntimeError(f"Falha ao comunicar com o servidor Ollama: {e}")


def get_client(provider: str, model_name: str = '') -> BaseLLMClient:
    """
    Função fábrica para criar o cliente LLM apropriado.

    Args:
        provider: O provedor de LLM ('gemini' ou 'ollama').
        model_name: Opcional. O nome do modelo a ser utilizado (substitui o padrão).

    Returns:
        Uma instância de um cliente derivado de BaseLLMClient.
    """
    provider = provider.lower().strip()
    
    kwargs = {}
    if model_name:
        kwargs['model_name'] = model_name
        
    if provider == 'gemini':
        return GeminiClient(**kwargs)
    elif provider == 'ollama':
        return OllamaClient(**kwargs)
    else:
        raise ValueError(f"Provedor LLM desconhecido ou não suportado: '{provider}'. Escolha 'gemini' ou 'ollama'.")


if __name__ == '__main__':
    print("Iniciando testes dos clientes LLM...")
    
    # Teste do Gemini
    try:
        print("\\n--- Testando GeminiClient ---")
        gemini = get_client('gemini')
        print(f"Modelo configurado: {gemini.model_name}")
        resp = gemini.generate("Diga 'Olá, mundo' de forma criativa.", "Você é um assistente entusiasta.")
        print(f"Resposta:\\n{resp}")
    except Exception as e:
        print(f"Erro no teste Gemini: {e}")
        
    # Teste do Ollama
    try:
        print("\\n--- Testando OllamaClient ---")
        ollama = get_client('ollama')
        print(f"Modelo configurado: {ollama.model_name}")
        resp = ollama.generate("Explique o que é um loop for em uma frase simples.", "Você é um instrutor de programação.")
        print(f"Resposta:\\n{resp}")
    except Exception as e:
        print(f"Erro no teste Ollama: {e}")
