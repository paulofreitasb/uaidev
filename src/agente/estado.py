"""Estado do grafo: tudo o que os nós leem e escrevem ao longo de uma mensagem."""

from __future__ import annotations

from typing import Annotated, Literal, TypedDict

from langchain_core.messages import AnyMessage
from langgraph.graph.message import add_messages

Intencao = Literal["faq", "reserva", "cotacao", "humano", "outro"]
Canal = Literal["streamlit", "eval"]


class EstadoAgente(TypedDict, total=False):
    # `add_messages` acumula o histórico em vez de sobrescrever. Com o checkpointer,
    # esse histórico é a memória da conversa. Mensagem com o mesmo `id` é substituída
    # (os guardrails usam isso para mascarar PII ou trocar uma resposta).
    messages: Annotated[list[AnyMessage], add_messages]
    intencao: Intencao | None
    bloqueado: bool  # guardrail de entrada disparou
    motivo_bloqueio: str | None
    tentativas_ferramenta: int  # proteção contra loop agente ⇄ ferramentas
    canal: Canal
    handoff: bool
    guardrail_disparado: str | None  # ex.: "entrada:prompt_injection", "saida:valor_sem_ferramenta"
