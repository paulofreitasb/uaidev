"""Ingestão da base de conhecimento: data/faq/*.md → trechos → embeddings → vector store.

Rode com `make ingest`. É idempotente: a coleção é recriada a cada execução, então
rodar duas vezes não duplica trechos e arquivos apagados somem da base.
"""

from __future__ import annotations

import logging
from typing import Any

from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

from agente.config import obter_config
from agente.rag.retriever import obter_vectorstore

log = logging.getLogger(__name__)

# ~1500 caracteres ≈ 400-500 tokens em português. Trechos menores deixam a busca mais
# precisa; o overlap evita cortar uma regra no meio.
TAMANHO_TRECHO = 1500
OVERLAP = 150


def carregar_documentos() -> list[Document]:
    pasta = obter_config().dados_dir / "faq"
    return [
        Document(page_content=arquivo.read_text(encoding="utf-8"), metadata={"fonte": arquivo.name})
        for arquivo in sorted(pasta.glob("*.md"))
    ]


def dividir(documentos: list[Document]) -> list[Document]:
    splitter = RecursiveCharacterTextSplitter(chunk_size=TAMANHO_TRECHO, chunk_overlap=OVERLAP)
    return splitter.split_documents(documentos)


def ingerir() -> int:
    trechos = dividir(carregar_documentos())
    store: Any = obter_vectorstore()  # Chroma ou PGVector: APIs de coleção diferentes
    # Recria a coleção: é o jeito mais simples de ser idempotente.
    if hasattr(store, "reset_collection"):  # Chroma
        store.reset_collection()
    else:  # PGVector
        store.delete_collection()
        store.create_collection()
    # Ids determinísticos e com o nome da coleção: no pgvector o id é único na tabela toda.
    colecao = obter_config().rag_colecao
    ids = [f"{colecao}:{t.metadata['fonte']}#{i}" for i, t in enumerate(trechos)]
    store.add_documents(trechos, ids=ids)
    return len(trechos)


def main() -> None:
    from agente.logging import configurar_logging

    configurar_logging()
    config = obter_config()
    total = ingerir()
    log.info("ingestão concluída", extra={"trechos": total, "backend": config.rag_backend})
    print(f"{total} trechos gravados em '{config.rag_backend}' (coleção {config.rag_colecao}).")


if __name__ == "__main__":
    main()
