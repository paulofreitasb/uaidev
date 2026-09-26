"""Integração com a infraestrutura do compose: `make up` (e `make up-obs` para o Langfuse).

Rode com `make test-integracao`. O LLM continua fake; o que é real aqui é o banco.
"""

import os
import uuid

import psycopg
import pytest

from agente import historico, responder, servico
from agente.config import obter_config
from agente.rag.ingestao import ingerir
from agente.rag.retriever import buscar
from tests.conftest import Modelos, intencao

pytestmark = pytest.mark.integracao

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://agente:agente@localhost:5432/agente")


@pytest.fixture(autouse=True)
def postgres(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATABASE_URL", DATABASE_URL)
    monkeypatch.setenv("MEMORIA_BACKEND", "postgres")
    monkeypatch.setenv("RAG_BACKEND", "pgvector")
    monkeypatch.setenv("RAG_COLECAO", "faq_teste")  # não mexe na coleção do dev
    obter_config.cache_clear()


def test_extensao_vector_e_banco_langfuse() -> None:
    with psycopg.connect(DATABASE_URL) as conexao:
        extensoes = {r[0] for r in conexao.execute("SELECT extname FROM pg_extension")}
        bancos = {r[0] for r in conexao.execute("SELECT datname FROM pg_database")}
    assert "vector" in extensoes
    assert "langfuse" in bancos


def test_memoria_no_postgres_persiste(modelos: Modelos) -> None:
    thread = f"teste-{uuid.uuid4().hex[:8]}"
    modelos(rapido=[intencao("outro")], forte=["Prazer, Ana!"])
    responder(thread, "Meu nome é Ana")
    servico.obter_grafo.cache_clear()  # "reinicia" o app: novo pool de conexões
    assert [m.text for m in historico(thread)] == ["Meu nome é Ana", "Prazer, Ana!"]

    with psycopg.connect(DATABASE_URL) as conexao:
        tabelas = {r[0] for r in conexao.execute("SELECT tablename FROM pg_tables")}
    assert {"checkpoints", "checkpoint_writes", "checkpoint_blobs"} <= tabelas


def test_rag_no_pgvector_idempotente() -> None:
    primeira, segunda = ingerir(), ingerir()
    assert primeira == segunda
    with psycopg.connect(DATABASE_URL) as conexao:
        (total,) = conexao.execute(
            "SELECT count(*) FROM langchain_pg_embedding e JOIN langchain_pg_collection c "
            "ON e.collection_id = c.uuid WHERE c.name = 'faq_teste'"
        ).fetchone()  # type: ignore[misc]
    assert total == primeira
    assert "cancelamento.md" in [t.fonte for t in buscar("Posso cancelar sem multa?", k=3)]


@pytest.mark.skipif(not os.getenv("LANGFUSE_TESTE"), reason="defina LANGFUSE_TESTE=1 (make up-obs)")
def test_trace_no_langfuse(monkeypatch: pytest.MonkeyPatch, modelos: Modelos) -> None:
    from agente import observabilidade

    monkeypatch.setenv("LANGFUSE_PUBLIC_KEY", "pk-lf-local-dev")
    monkeypatch.setenv("LANGFUSE_SECRET_KEY", "sk-lf-local-dev")
    obter_config.cache_clear()
    observabilidade._cliente_langfuse.cache_clear()
    modelos(rapido=[intencao("outro")], forte=["Olá!"])
    resposta = responder(f"teste-{uuid.uuid4().hex[:8]}", "Olá")
    observabilidade.registrar_score(resposta.trace_id or "", "teste", 1.0)
    observabilidade.flush()
    assert resposta.trace_url and resposta.trace_url.startswith("http://localhost:3000/project/")
