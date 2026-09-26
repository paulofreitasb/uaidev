"""Handoff: transferência para um atendente humano.

É uma resposta fixa, sem LLM: previsível, instantânea e sem custo. O `handoff=True`
vai para o estado e para o trace, o que permite medir a taxa de transferência.
"""

from __future__ import annotations

from typing import Any

from langchain_core.messages import AIMessage

from agente.estado import EstadoAgente

MENSAGEM_HANDOFF = (
    "Certo! Vou transferir você para um dos nossos atendentes. "
    "Em instantes alguém da equipe continua a conversa por aqui."
)


def handoff(estado: EstadoAgente) -> dict[str, Any]:
    return {"messages": [AIMessage(MENSAGEM_HANDOFF)], "handoff": True}
