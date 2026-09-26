"""Ferramenta para o próprio agente pedir um humano quando não consegue resolver.

O pedido explícito ("quero um atendente") nem chega aqui: o classificador manda direto
para o nó `handoff`. Esta ferramenta cobre o outro caso: o agente percebe que não sabe.
"""

from __future__ import annotations

from langchain_core.tools import tool


@tool
def transferir_para_humano(motivo: str) -> str:
    """Transfere a conversa para um atendente humano.

    Use quando o cliente pedir para falar com uma pessoa, estiver insatisfeito,
    ou quando você não conseguir resolver o pedido com as outras ferramentas.

    Args:
        motivo: resumo curto do motivo da transferência.
    """
    return f"Transferência para atendente registrada. Motivo: {motivo}"
