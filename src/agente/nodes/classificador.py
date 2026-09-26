"""Classificador de intenção, com o modelo rápido.

Classificar antes de responder permite rotear barato: um pedido de atendente vai
direto para o handoff, sem gastar uma chamada do modelo forte.
"""

from __future__ import annotations

import logging
from typing import Any, get_args

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from pydantic import BaseModel

from agente import prompts
from agente.estado import EstadoAgente, Intencao
from agente.llm import modelo_rapido

log = logging.getLogger(__name__)
INTENCOES: tuple[str, ...] = get_args(Intencao)
CONTEXTO_MENSAGENS = 6


class Classificacao(BaseModel):
    """Intenção da última mensagem do cliente."""

    intencao: Intencao


def _transcricao(estado: EstadoAgente) -> str:
    """Histórico recente como texto puro.

    Só o texto de cliente e agente: mensagens de ferramenta não ajudam a classificar
    e alguns providers recusam `tool_calls` sem as ferramentas declaradas.
    """
    linhas = []
    for m in estado["messages"][-CONTEXTO_MENSAGENS:]:
        if isinstance(m, HumanMessage):
            linhas.append(f"Cliente: {m.text}")
        elif isinstance(m, AIMessage) and m.text:
            linhas.append(f"Agente: {m.text}")
    historico, atual = linhas[:-1], linhas[-1] if linhas else ""
    return "Histórico:\n" + ("\n".join(historico) or "(vazio)") + f"\n\nÚltima mensagem:\n{atual}"


def classificar(estado: EstadoAgente) -> Intencao:
    try:
        classificador = modelo_rapido().with_structured_output(Classificacao)
        resultado = classificador.invoke(
            [SystemMessage(prompts.carregar("classificador")), HumanMessage(_transcricao(estado))]
        )
        if isinstance(resultado, Classificacao):
            return resultado.intencao
    except Exception:
        log.warning("classificador falhou; seguindo como 'outro'", exc_info=True)
    return "outro"


def classificador(estado: EstadoAgente) -> dict[str, Any]:
    return {"intencao": classificar(estado)}
