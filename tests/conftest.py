"""Fixtures comuns. Regra de ouro: nenhum teste unitário usa rede nem LLM de verdade."""

from __future__ import annotations

from collections.abc import Callable, Iterator, Sequence
from pathlib import Path
from typing import Any

import pytest
from langchain_core.messages import AIMessage

from agente import llm, servico
from agente.config import Config, obter_config
from agente.nodes import agente as no_agente
from agente.nodes import classificador as no_classificador
from agente.nodes import guardrails as no_guardrails
from agente.rag import retriever
from agente.tools import reservas

CACHES = [
    obter_config,
    llm.modelo_rapido,
    llm.modelo_forte,
    llm.modelo_juiz,
    llm.embeddings,
    retriever._criar_vectorstore,
    servico.obter_grafo,
    reservas._reservas,
]


def limpar_caches() -> None:
    for funcao in CACHES:
        funcao.cache_clear()


@pytest.fixture(autouse=True)
def ambiente(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Iterator[None]:
    """Ambiente isolado: provider fake, SQLite e Chroma em pasta temporária, sem Langfuse."""
    monkeypatch.setitem(Config.model_config, "env_file", None)  # ignora o .env da máquina
    variaveis = {
        "LLM_PROVIDER": "fake",
        "LLM_API_KEY": "",
        "EMBEDDINGS_PROVIDER": "fake",
        "MEMORIA_BACKEND": "sqlite",
        "RAG_BACKEND": "chroma",
        "SQLITE_PATH": str(tmp_path / "memoria.sqlite"),
        "CHROMA_DIR": str(tmp_path / "chroma"),
        "RAG_SCORE_MINIMO": "0.1",
        "LANGFUSE_PUBLIC_KEY": "",
        "LANGFUSE_SECRET_KEY": "",
        "LANGSMITH_TRACING": "false",
        "GUARDRAIL_INJECAO_LLM": "false",
        "USAR_CLASSIFICADOR": "true",
    }
    for nome, valor in variaveis.items():
        monkeypatch.setenv(nome, valor)
    for nome in ("OPENAI_API_KEY", "ANTHROPIC_API_KEY", "GOOGLE_API_KEY"):
        monkeypatch.delenv(nome, raising=False)
    limpar_caches()
    yield
    limpar_caches()


def chamada(nome: str, **args: Any) -> AIMessage:
    """Resposta do modelo pedindo uma ferramenta."""
    return AIMessage(content="", tool_calls=[{"name": nome, "args": args, "id": f"call_{nome}"}])


def intencao(valor: str) -> AIMessage:
    # with_structured_output usa tool calling por baixo: o fake devolve a "tool" do schema.
    return chamada("Classificacao", intencao=valor)


Modelos = Callable[..., None]


@pytest.fixture
def modelos(monkeypatch: pytest.MonkeyPatch) -> Modelos:
    """Roteiriza os modelos: modelos(forte=[...], rapido=[...]).

    Uma lista vazia faz o modelo falhar se for chamado, o que prova que ele não foi usado.
    """

    def configurar(
        forte: Sequence[AIMessage | str] = (), rapido: Sequence[AIMessage | str] = ()
    ) -> None:
        modelo_forte, modelo_rapido = llm.modelo_fake(forte), llm.modelo_fake(rapido)
        monkeypatch.setattr(no_agente, "modelo_forte", lambda: modelo_forte)
        monkeypatch.setattr(no_classificador, "modelo_rapido", lambda: modelo_rapido)
        monkeypatch.setattr(no_guardrails, "modelo_rapido", lambda: modelo_rapido)

    return configurar


@pytest.fixture
def base_faq() -> int:
    """Ingere o FAQ no Chroma temporário com embeddings fake."""
    from agente.rag.ingestao import ingerir

    return ingerir()
