"""Busca na base de conhecimento (pgvector ou Chroma, conforme RAG_BACKEND)."""

from __future__ import annotations

import threading
from dataclasses import asdict, dataclass
from functools import lru_cache
from typing import Any

from langchain_core.vectorstores import VectorStore

from agente.config import obter_config
from agente.llm import embeddings

# O lru_cache não impede duas threads (sessões do Streamlit, evals em paralelo) de criarem
# o store ao mesmo tempo, e o PGVector não aceita ser definido duas vezes.
_lock = threading.Lock()


@dataclass(frozen=True)
class Trecho:
    texto: str
    fonte: str
    score: float

    def como_dict(self) -> dict[str, Any]:
        return asdict(self)


def obter_vectorstore() -> VectorStore:
    with _lock:
        return _criar_vectorstore()


@lru_cache
def _criar_vectorstore() -> VectorStore:
    config = obter_config()
    if config.rag_backend == "chroma":
        from langchain_chroma import Chroma

        store: VectorStore = Chroma(
            collection_name=config.rag_colecao,
            embedding_function=embeddings(),
            persist_directory=str(config.chroma_dir),
            collection_metadata={"hnsw:space": "cosine"},
        )
        return store

    from langchain_postgres import PGVector

    url = config.database_url.replace("postgresql://", "postgresql+psycopg://", 1)
    store = PGVector(
        embeddings=embeddings(), collection_name=config.rag_colecao, connection=url, use_jsonb=True
    )
    return store


def buscar(pergunta: str, k: int | None = None) -> list[Trecho]:
    """Devolve os `k` trechos mais parecidos com a pergunta, acima do score mínimo.

    O score mínimo evita mandar lixo para o modelo: se nada relevante vier, é melhor
    o agente dizer "não sei" do que responder com um trecho que não tem a ver.
    """
    config = obter_config()
    resultados = obter_vectorstore().similarity_search_with_relevance_scores(
        pergunta, k=k or config.rag_k
    )
    return [
        Trecho(texto=doc.page_content, fonte=doc.metadata["fonte"], score=round(score, 3))
        for doc, score in resultados
        if score >= config.rag_score_minimo
    ]
