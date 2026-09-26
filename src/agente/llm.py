"""Fábrica de modelos: um modelo rápido (classificar, checar) e um forte (responder).

Por que dois? O classificador roda em toda mensagem e só precisa escolher um rótulo;
um modelo menor faz isso com menos custo e latência. O modelo forte fica reservado
para o que exige raciocínio: conversar e decidir quais ferramentas chamar.

`init_chat_model` deixa o provider configurável: trocar de OpenAI para Anthropic,
Google ou Ollama é só mudar o .env.
"""

from __future__ import annotations

import hashlib
import itertools
import math
import re
import unicodedata
from collections.abc import Sequence
from functools import lru_cache
from typing import Any

from langchain.chat_models import init_chat_model
from langchain_core.embeddings import Embeddings
from langchain_core.language_models import BaseChatModel
from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage

from agente.config import ErroConfiguracao, obter_config

MENSAGEM_DEMO = (
    "Estou no modo demonstração (LLM_PROVIDER=fake), então não entendo o que você "
    "escreveu. Configure um provider real no .env para conversar de verdade."
)


class ModeloFake(GenericFakeChatModel):
    """Modelo sem rede, para testes e para o modo demo.

    Devolve as mensagens da lista em ordem. `bind_tools` só devolve o próprio modelo:
    as `tool_calls` vêm prontas nas mensagens roteirizadas do teste.
    """

    def bind_tools(self, tools: Sequence[Any], **kwargs: Any) -> ModeloFake:
        return self


def modelo_fake(respostas: Sequence[AIMessage | str]) -> ModeloFake:
    mensagens = [r if isinstance(r, AIMessage) else AIMessage(content=r) for r in respostas]
    return ModeloFake(messages=iter(mensagens))


def _criar_modelo(nome: str, temperatura: float | None) -> BaseChatModel:
    config = obter_config()
    provider = config.llm_provider
    if provider == "fake":
        return ModeloFake(messages=itertools.repeat(AIMessage(content=MENSAGEM_DEMO)))

    kwargs: dict[str, Any] = {}
    if config.llm_api_key is not None:
        kwargs["api_key"] = config.llm_api_key.get_secret_value()
    if temperatura is not None:
        kwargs["temperature"] = temperatura
    if provider == "openai":
        # Responses API: necessária para usar ferramentas com os modelos de raciocínio.
        kwargs["use_responses_api"] = True
        if config.llm_reasoning_effort:
            kwargs["reasoning"] = {"effort": config.llm_reasoning_effort}
    if provider == "ollama":
        kwargs["base_url"] = config.ollama_base_url
    modelo: BaseChatModel = init_chat_model(nome, model_provider=provider, **kwargs)
    return modelo


@lru_cache
def modelo_rapido() -> BaseChatModel:
    config = obter_config()
    return _criar_modelo(config.llm_modelo_rapido, config.llm_temperatura)


@lru_cache
def modelo_forte() -> BaseChatModel:
    config = obter_config()
    return _criar_modelo(config.llm_modelo_forte, config.llm_temperatura)


@lru_cache
def modelo_juiz() -> BaseChatModel:
    config = obter_config()
    return _criar_modelo(config.llm_modelo_juiz or config.llm_modelo_forte, config.juiz_temperatura)


# --- Embeddings (usados pelo RAG) --------------------------------------------------------


class EmbeddingsFake(Embeddings):
    """Embeddings locais e determinísticos (saco de palavras com hashing).

    Não entendem sinônimos, mas palavras em comum aproximam os textos. Suficiente
    para testar o RAG no CI e no modo demo, sem rede.
    """

    dimensoes = 512

    def _vetor(self, texto: str) -> list[float]:
        sem_acento = unicodedata.normalize("NFKD", texto.lower()).encode("ascii", "ignore")
        vetor = [0.0] * self.dimensoes
        for palavra in re.findall(r"[a-z0-9]{3,}", sem_acento.decode()):
            # Radical simples: "cancelar" e "cancelamento" caem no mesmo balde.
            balde = int(hashlib.md5(palavra[:6].encode()).hexdigest(), 16) % self.dimensoes
            vetor[balde] += 1.0
        norma = math.sqrt(sum(v * v for v in vetor)) or 1.0
        return [v / norma for v in vetor]

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self._vetor(t) for t in texts]

    def embed_query(self, text: str) -> list[float]:
        return self._vetor(text)


@lru_cache
def embeddings() -> Embeddings:
    config = obter_config()
    provider = config.embeddings_provider or config.llm_provider
    chave = config.embeddings_api_key or config.llm_api_key
    if provider == "fake":
        return EmbeddingsFake()
    if provider == "openai":
        from langchain_openai import OpenAIEmbeddings

        return OpenAIEmbeddings(model=config.embeddings_modelo, openai_api_key=chave)
    if provider == "ollama":
        from langchain_ollama import OllamaEmbeddings

        return OllamaEmbeddings(model=config.embeddings_modelo, base_url=config.ollama_base_url)
    raise ErroConfiguracao(
        f"O provider '{provider}' não tem embeddings aqui. "
        "Defina EMBEDDINGS_PROVIDER=openai ou ollama no .env."
    )
