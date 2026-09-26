"""Nó principal: o modelo forte conversa e decide quais ferramentas chamar."""

from __future__ import annotations

from typing import Any

from langchain_core.messages import SystemMessage, trim_messages

from agente import prompts
from agente.config import obter_config
from agente.estado import EstadoAgente
from agente.llm import modelo_forte
from agente.tools import ferramentas_para


def agente(estado: EstadoAgente) -> dict[str, Any]:
    config = obter_config()
    modelo = modelo_forte()
    if estado.get("tentativas_ferramenta", 0) < config.max_tentativas_ferramenta:
        ferramentas = ferramentas_para(
            estado.get("intencao"), config.filtrar_ferramentas_por_intencao
        )
        modelo = modelo.bind_tools(ferramentas)  # type: ignore[assignment]
    # Sem bind_tools o modelo é obrigado a responder em texto: é o freio do loop.

    # Janela de contexto: só as últimas N mensagens vão para o modelo. O histórico completo
    # continua salvo no checkpointer; limitamos o que é enviado para controlar custo e
    # latência. O trade-off: fatos ditos há muito tempo são "esquecidos".
    # start_on="human" garante que a janela não comece no meio de uma chamada de ferramenta.
    janela = trim_messages(
        estado["messages"],
        strategy="last",
        token_counter=len,
        max_tokens=config.janela_mensagens,
        start_on="human",
    )
    resposta = modelo.invoke([SystemMessage(prompts.carregar("sistema")), *janela])
    return {"messages": [resposta]}
