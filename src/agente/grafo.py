"""Monta o grafo do agente.

    START → guardrail_entrada ─ bloqueado ─────────────────────────────┐
                    │ ok                                              │
              classificador ─ humano ─→ handoff ───────────────────────┤
                    │ faq/reserva/cotacao/outro                       ▼
                 agente ⇄ ferramentas (─ transferir_para_humano → handoff)
                    │ resposta                                        │
                    └───────────────→ guardrail_saida ←──────────────┘ → END

O roteamento é explícito: cada aresta condicional é uma função pequena, fácil de ler
e de testar. É o que o LangGraph dá a mais que um loop solto em Python.
"""

from __future__ import annotations

from typing import Any

from langchain_core.messages import ToolMessage
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph
from langgraph.prebuilt import ToolNode, tools_condition

from agente.config import obter_config
from agente.estado import EstadoAgente
from agente.nodes.agente import agente
from agente.nodes.classificador import classificador
from agente.nodes.guardrails import guardrail_entrada, guardrail_saida
from agente.nodes.handoff import handoff
from agente.tools import TOOLS

_tool_node = ToolNode(TOOLS)


def ferramentas(estado: EstadoAgente) -> dict[str, Any]:
    resultado: dict[str, Any] = _tool_node.invoke(estado)
    resultado["tentativas_ferramenta"] = estado.get("tentativas_ferramenta", 0) + 1
    return resultado


def rota_entrada(estado: EstadoAgente) -> str:
    if estado.get("bloqueado"):
        return "guardrail_saida"
    # USAR_CLASSIFICADOR=false: um modelo só, direto no agente.
    return "classificador" if obter_config().usar_classificador else "agente"


def rota_intencao(estado: EstadoAgente) -> str:
    # Pedido explícito de humano não passa pelo modelo forte: resposta fixa, sem custo.
    return "handoff" if estado.get("intencao") == "humano" else "agente"


def rota_agente(estado: EstadoAgente) -> str:
    quer_ferramenta = tools_condition(estado) == "tools"  # type: ignore[arg-type]
    dentro_do_limite = (
        estado.get("tentativas_ferramenta", 0) < obter_config().max_tentativas_ferramenta
    )
    # Estourou o limite e o modelo ainda pede ferramenta: o guardrail de saída encerra o turno.
    return "ferramentas" if quer_ferramenta and dentro_do_limite else "guardrail_saida"


def rota_ferramentas(estado: EstadoAgente) -> str:
    # O próprio agente pediu um humano (não sabia resolver): vai para o handoff.
    for mensagem in reversed(estado["messages"]):
        if not isinstance(mensagem, ToolMessage):
            break  # só olha os resultados desta rodada de ferramentas
        if mensagem.name == "transferir_para_humano":
            return "handoff"
    return "agente"


def construir_grafo(
    checkpointer: BaseCheckpointSaver[Any] | None = None,
) -> CompiledStateGraph[EstadoAgente, None, EstadoAgente, EstadoAgente]:
    grafo = StateGraph(EstadoAgente)
    grafo.add_node("guardrail_entrada", guardrail_entrada)
    grafo.add_node("classificador", classificador)
    grafo.add_node("agente", agente)
    grafo.add_node("ferramentas", ferramentas)
    grafo.add_node("handoff", handoff)
    grafo.add_node("guardrail_saida", guardrail_saida)

    grafo.add_edge(START, "guardrail_entrada")
    grafo.add_conditional_edges(
        "guardrail_entrada", rota_entrada, ["guardrail_saida", "classificador", "agente"]
    )
    grafo.add_conditional_edges("classificador", rota_intencao, ["handoff", "agente"])
    grafo.add_conditional_edges("agente", rota_agente, ["ferramentas", "guardrail_saida"])
    grafo.add_conditional_edges("ferramentas", rota_ferramentas, ["agente", "handoff"])
    grafo.add_edge("handoff", "guardrail_saida")
    grafo.add_edge("guardrail_saida", END)
    return grafo.compile(checkpointer=checkpointer)
