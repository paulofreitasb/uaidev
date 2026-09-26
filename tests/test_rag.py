"""RAG com Chroma + embeddings fake (locais, determinísticos): roda no CI sem rede."""

import pytest

from agente.rag.ingestao import carregar_documentos, dividir, ingerir
from agente.rag.retriever import buscar, obter_vectorstore
from agente.tools.faq import SEM_RESULTADO, buscar_faq


def test_carrega_todo_o_faq() -> None:
    documentos = carregar_documentos()
    assert 8 <= len(documentos) <= 12
    assert all(d.metadata["fonte"].endswith(".md") for d in documentos)
    assert len(dividir(documentos)) >= len(documentos)


def test_ingestao_idempotente(base_faq: int) -> None:
    assert ingerir() == base_faq
    colecao = obter_vectorstore()._collection  # type: ignore[attr-defined]
    assert colecao.count() == base_faq


@pytest.mark.parametrize(
    ("pergunta", "fonte"),
    [
        ("Posso cancelar a reserva sem multa?", "cancelamento.md"),
        ("Quais documentos preciso para alugar? Preciso da CNH?", "documentos.md"),
        ("Qual a idade mínima para alugar?", "idade-minima.md"),
        ("Tem limite de quilometragem? A km é livre?", "franquia-km.md"),
        ("Como funciona a caução no cartão de crédito?", "pagamento.md"),
        ("O que o seguro cobre em caso de acidente?", "seguro.md"),
        ("Quem paga as multas de trânsito?", "multas.md"),
    ],
)
def test_pergunta_recupera_arquivo_certo_no_top3(base_faq: int, pergunta: str, fonte: str) -> None:
    fontes = [t.fonte for t in buscar(pergunta, k=3)]
    assert fonte in fontes


def test_trechos_tem_fonte_e_score(base_faq: int) -> None:
    trechos = buscar("cancelamento sem multa")
    assert trechos
    assert all(0 <= t.score <= 1 for t in trechos)
    assert trechos == sorted(trechos, key=lambda t: t.score, reverse=True)


def test_ferramenta_devolve_texto_com_fonte_e_artifact(base_faq: int) -> None:
    mensagem = buscar_faq.invoke(
        {"type": "tool_call", "id": "1", "name": "buscar_faq", "args": {"pergunta": "cancelar"}}
    )
    assert "[fonte: cancelamento.md]" in mensagem.content
    assert mensagem.artifact[0]["fonte"]


def test_sem_trecho_relevante_diz_que_nao_sabe(
    base_faq: int, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("RAG_SCORE_MINIMO", "0.99")
    buscar.__globals__["obter_config"].cache_clear()
    assert buscar_faq.invoke({"pergunta": "Qual a capital da França?"}) == SEM_RESULTADO
