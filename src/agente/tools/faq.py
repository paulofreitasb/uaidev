"""Ferramenta de FAQ: o agente chama o retriever como qualquer outra ferramenta."""

from __future__ import annotations

from typing import Any

from langchain_core.tools import tool

from agente.rag.retriever import buscar

SEM_RESULTADO = (
    "Nenhum trecho relevante encontrado na base de conhecimento. Diga ao cliente que "
    "não sabe responder e ofereça falar com um atendente."
)


# content_and_artifact: o texto vai para o modelo; os trechos estruturados (fonte, score)
# ficam no `artifact` da ToolMessage, para o painel de debug e os evals.
@tool(response_format="content_and_artifact")
def buscar_faq(pergunta: str) -> tuple[str, list[dict[str, Any]]]:
    """Busca na base de conhecimento da Locadora Exemplo (políticas e dúvidas frequentes).

    Use para qualquer dúvida sobre regras: documentos, cancelamento, franquia de km,
    seguro, pagamento, idade mínima, caução, multas, devolução etc.

    Args:
        pergunta: a dúvida do cliente, reescrita de forma clara e completa.
    """
    trechos = buscar(pergunta)
    if not trechos:
        return SEM_RESULTADO, []
    texto = "\n\n".join(f"[fonte: {t.fonte}]\n{t.texto}" for t in trechos)
    return texto, [t.como_dict() for t in trechos]
