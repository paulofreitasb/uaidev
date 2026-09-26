"""Ferramentas disponíveis para o agente.

O modelo decide qual chamar lendo o nome, a docstring e os tipos dos argumentos.
Por isso as docstrings são escritas para ele: dizem quando usar e o formato esperado.
"""

from __future__ import annotations

from langchain_core.tools import BaseTool

from agente.tools.cotacao import cotar_aluguel
from agente.tools.faq import buscar_faq
from agente.tools.handoff import transferir_para_humano
from agente.tools.reservas import consultar_reserva

TOOLS: list[BaseTool] = [buscar_faq, consultar_reserva, cotar_aluguel, transferir_para_humano]

# Padrão opcional (FILTRAR_FERRAMENTAS_POR_INTENCAO=true): menos ferramentas no prompt
# = menos tokens e menos chance de o modelo escolher a errada. O custo é depender
# do acerto do classificador.
_POR_INTENCAO: dict[str, list[BaseTool]] = {
    "faq": [buscar_faq, transferir_para_humano],
    "reserva": [consultar_reserva, transferir_para_humano],
    "cotacao": [cotar_aluguel, transferir_para_humano],
}


def ferramentas_para(intencao: str | None, filtrar: bool) -> list[BaseTool]:
    if not filtrar or intencao is None:
        return TOOLS
    return _POR_INTENCAO.get(intencao, TOOLS)
