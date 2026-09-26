"""A fronteira pública do agente: `responder(thread_id, mensagem, canal)`.

O canal (Streamlit hoje, WhatsApp amanhã) só conhece esta função. Ele não sabe que
existe um LangGraph por trás, e por isso trocar ou adicionar canais não mexe no agente.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Any

from langchain_core.callbacks import UsageMetadataCallbackHandler
from langchain_core.messages import AIMessage, AnyMessage, HumanMessage, ToolMessage
from langchain_core.runnables import RunnableConfig
from langgraph.graph.state import CompiledStateGraph

from agente import observabilidade
from agente.estado import Canal, EstadoAgente
from agente.grafo import construir_grafo
from agente.memoria import obter_checkpointer
from agente.nodes.guardrails import mascarar_pii


@dataclass
class ChamadaFerramenta:
    nome: str
    argumentos: dict[str, Any]
    retorno: str


@dataclass
class Resposta:
    texto: str
    thread_id: str
    intencao: str | None = None
    ferramentas: list[ChamadaFerramenta] = field(default_factory=list)
    trechos: list[dict[str, Any]] = field(default_factory=list)
    bloqueado: bool = False
    motivo_bloqueio: str | None = None
    handoff: bool = False
    guardrail_disparado: str | None = None
    latencia_ms: int = 0
    tokens: int = 0
    tokens_por_modelo: dict[str, int] = field(default_factory=dict)
    trace_id: str | None = None
    trace_url: str | None = None


@lru_cache
def obter_grafo() -> CompiledStateGraph[EstadoAgente, None, EstadoAgente, EstadoAgente]:
    return construir_grafo(checkpointer=obter_checkpointer())


def _mensagens_do_turno(mensagens: list[AnyMessage]) -> list[AnyMessage]:
    """Tudo o que veio depois da última mensagem do cliente."""
    for i in range(len(mensagens) - 1, -1, -1):
        if isinstance(mensagens[i], HumanMessage):
            return mensagens[i + 1 :]
    return mensagens


def _ferramentas_chamadas(turno: list[AnyMessage]) -> tuple[list[ChamadaFerramenta], list[Any]]:
    retornos = {m.tool_call_id: m for m in turno if isinstance(m, ToolMessage)}
    chamadas, trechos = [], []
    for m in turno:
        if not isinstance(m, AIMessage):
            continue
        for call in m.tool_calls:
            retorno = retornos.get(call["id"] or "")
            chamadas.append(
                ChamadaFerramenta(call["name"], call["args"], retorno.text if retorno else "")
            )
            if retorno is not None and isinstance(retorno.artifact, list):
                trechos.extend(retorno.artifact)
    return chamadas, trechos


def responder(thread_id: str, mensagem: str, canal: Canal = "streamlit") -> Resposta:
    # PII mascarada já na fronteira: o que entra no grafo, nos logs e no trace já vem limpo.
    mensagem = mascarar_pii(mensagem)
    uso = UsageMetadataCallbackHandler()
    inicio = time.perf_counter()

    with observabilidade.rastrear(thread_id, canal) as rastreio:
        config: RunnableConfig = {
            "configurable": {"thread_id": thread_id},
            "callbacks": [uso, *rastreio.callbacks],
            "metadata": rastreio.metadata,
            "tags": rastreio.tags,
            "run_name": "agente",
        }
        # Campos "por mensagem" são zerados a cada entrada; `messages` acumula.
        entrada: EstadoAgente = {
            "messages": [HumanMessage(mensagem)],
            "canal": canal,
            "intencao": None,
            "bloqueado": False,
            "motivo_bloqueio": None,
            "tentativas_ferramenta": 0,
            "handoff": False,
            "guardrail_disparado": None,
        }
        estado = obter_grafo().invoke(entrada, config)

        turno = _mensagens_do_turno(estado["messages"])
        ferramentas, trechos = _ferramentas_chamadas(turno)
        tokens_por_modelo = {m: u["total_tokens"] for m, u in uso.usage_metadata.items()}
        resposta = Resposta(
            texto=estado["messages"][-1].text,
            thread_id=thread_id,
            intencao=estado.get("intencao"),
            ferramentas=ferramentas,
            trechos=trechos,
            bloqueado=estado.get("bloqueado", False),
            motivo_bloqueio=estado.get("motivo_bloqueio"),
            handoff=estado.get("handoff", False),
            guardrail_disparado=estado.get("guardrail_disparado"),
            latencia_ms=int((time.perf_counter() - inicio) * 1000),
            tokens=sum(tokens_por_modelo.values()),
            tokens_por_modelo=tokens_por_modelo,
            trace_id=rastreio.trace_id,
            trace_url=rastreio.trace_url,
        )
        rastreio.resultado = {
            "entrada": mensagem,
            "texto": resposta.texto,
            "intencao": resposta.intencao,
            "handoff": resposta.handoff,
            "guardrail_disparado": resposta.guardrail_disparado,
            "ferramentas": ",".join(f.nome for f in ferramentas),
        }
    return resposta


def historico(thread_id: str) -> list[AnyMessage]:
    """Mensagens salvas da conversa (para o canal reexibir depois de um reinício)."""
    estado = obter_grafo().get_state({"configurable": {"thread_id": thread_id}})
    mensagens: list[AnyMessage] = estado.values.get("messages", [])
    return mensagens


def estado_salvo(thread_id: str) -> dict[str, Any]:
    estado = obter_grafo().get_state({"configurable": {"thread_id": thread_id}})
    return dict(estado.values)
