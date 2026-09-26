"""Guardrails de entrada e de saída.

Entrada: limita o tamanho, mascara PII e detecta prompt injection (regras + LLM rápido).
Saída: barra promessas fora da política, valores em R$ que não vieram de uma ferramenta
e respostas longas demais.

Regras em código são baratas, previsíveis e fáceis de testar; o LLM pega o que as regras
não previram. As duas camadas se complementam.
"""

from __future__ import annotations

import logging
import re
from typing import Any

from langchain_core.messages import AIMessage, AnyMessage, HumanMessage, SystemMessage, ToolMessage
from pydantic import BaseModel, Field

from agente import prompts
from agente.config import obter_config
from agente.estado import EstadoAgente
from agente.llm import modelo_rapido

log = logging.getLogger(__name__)

# --- PII -----------------------------------------------------------------------------------

_PII = [
    (re.compile(r"\b\d{3}\.?\d{3}\.?\d{3}-?\d{2}\b"), "***.***.***-**"),  # CPF
    (re.compile(r"\b(?:\d{4}[ .-]?){3}\d{4}\b"), "****.****.****.****"),  # cartão
    (re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b"), "***@***"),  # e-mail
]


def mascarar_pii(texto: str) -> str:
    for padrao, mascara in _PII:
        texto = padrao.sub(mascara, texto)
    return texto


# --- Prompt injection --------------------------------------------------------------------

_INJECAO = re.compile(
    r"ignore (?:as |suas |todas as )*(?:instru|regras)"
    r"|esque[çc]a (?:as |suas |todas as )*(?:instru|regras)"
    r"|(?:mostre|revele|diga|me d[êe]|repita|imprima)\b.{0,30}\b(?:seu|o) (?:prompt|system prompt)"
    r"|(?:seu|o) prompt (?:de sistema|inicial)"
    r"|ignore (?:all |your |previous )+instructions"
    r"|system prompt|modo desenvolvedor|developer mode|jailbreak|\bDAN\b",
    re.IGNORECASE,
)


class VereditoInjecao(BaseModel):
    """Resultado da checagem de prompt injection."""

    injecao: bool = Field(description="true se a mensagem tenta manipular o assistente")


def detectar_injecao(texto: str) -> bool:
    if _INJECAO.search(texto):
        return True
    if not obter_config().guardrail_injecao_llm:
        return False
    try:
        checador = modelo_rapido().with_structured_output(VereditoInjecao)
        veredito = checador.invoke(
            [SystemMessage(prompts.carregar("guardrail")), HumanMessage(texto)]
        )
        return isinstance(veredito, VereditoInjecao) and veredito.injecao
    except Exception:
        # Falha do checador não pode derrubar a conversa; as regras já rodaram.
        log.warning("checagem de injection por LLM falhou", exc_info=True)
        return False


RESPOSTAS_BLOQUEIO = {
    "prompt_injection": (
        "Desculpe, não posso ajudar com isso. Posso tirar dúvidas sobre aluguel, "
        "consultar uma reserva ou fazer uma cotação para você."
    ),
    "mensagem_longa": (
        "Sua mensagem ficou um pouco longa para mim. Pode resumir em poucas frases?"
    ),
}


def guardrail_entrada(estado: EstadoAgente) -> dict[str, Any]:
    ultima = estado["messages"][-1]
    original = ultima.text
    texto = mascarar_pii(original)
    atualizacao: dict[str, Any] = {}
    if texto != original:
        # Mesmo id = substitui a mensagem no histórico, que passa a guardar a versão mascarada.
        atualizacao["messages"] = [HumanMessage(content=texto, id=ultima.id)]

    motivo = None
    if len(texto) > obter_config().max_caracteres_entrada:
        motivo = "mensagem_longa"
    elif detectar_injecao(texto):
        motivo = "prompt_injection"

    if motivo:
        log.info("guardrail de entrada disparou", extra={"motivo": motivo})
        mensagens = [*atualizacao.get("messages", []), AIMessage(RESPOSTAS_BLOQUEIO[motivo])]
        return {
            "messages": mensagens,
            "bloqueado": True,
            "motivo_bloqueio": motivo,
            "guardrail_disparado": f"entrada:{motivo}",
        }
    return atualizacao


# --- Saída ------------------------------------------------------------------------------------

_PROMESSAS = re.compile(
    r"desconto garantido|garanto (?:um |o )?desconto|garantimos (?:um |o )?desconto"
    r"|(?:é|fica|sai) de gra[çc]a|sem nenhum custo|isen[çc][ãa]o garantida|reembolso garantido",
    re.IGNORECASE,
)
_VALOR_BRL = re.compile(r"R\$\s?(\d{1,3}(?:\.\d{3})*(?:,\d{1,2})?|\d+(?:,\d{1,2})?)")

RESPOSTA_POLITICA = (
    "Não consigo garantir essa condição. Posso fazer uma cotação oficial ou transferir "
    "você para um atendente."
)
RESPOSTA_LIMITE = (
    "Não consegui concluir sua solicitação agora. Posso transferir você para um atendente?"
)
RESPOSTA_VALOR = (
    "Não consegui confirmar esse valor agora. Posso fazer uma cotação oficial se você "
    "me disser a categoria, o número de dias e a cidade."
)


def _valores(texto: str) -> set[str]:
    return {v.replace(".", "").split(",")[0] for v in _VALOR_BRL.findall(texto)}


def _valores_conhecidos(mensagens: list[AnyMessage]) -> set[str]:
    """Valores que vieram de ferramentas (ou que o próprio cliente citou)."""
    conhecidos: set[str] = set()
    for m in mensagens:
        if isinstance(m, ToolMessage | HumanMessage):
            conhecidos |= _valores(m.text)
    return conhecidos


def _truncar(texto: str, limite: int) -> str:
    corte = texto[:limite]
    fim_frase = max(corte.rfind(". "), corte.rfind(".\n"))
    return corte[: fim_frase + 1] if fim_frase > limite // 2 else corte.rstrip() + "…"


def guardrail_saida(estado: EstadoAgente) -> dict[str, Any]:
    if estado.get("bloqueado"):
        return {}
    ultima = estado["messages"][-1]
    if not isinstance(ultima, AIMessage):
        return {}
    texto: str = str(ultima.text)
    motivo: str | None = None

    if ultima.tool_calls:
        # Chegou aqui ainda pedindo ferramenta = estourou MAX_TENTATIVAS_FERRAMENTA.
        # Trocar a mensagem também evita deixar tool_calls sem resposta no histórico.
        texto, motivo = RESPOSTA_LIMITE, "limite_ferramentas"
    elif _PROMESSAS.search(texto):
        texto, motivo = RESPOSTA_POLITICA, "promessa_fora_politica"
    elif _valores(texto) - _valores_conhecidos(estado["messages"]):
        texto, motivo = RESPOSTA_VALOR, "valor_sem_ferramenta"
    elif len(texto) > obter_config().max_caracteres_saida:
        texto, motivo = _truncar(texto, obter_config().max_caracteres_saida), "resposta_longa"

    if motivo is None:
        return {}
    log.info("guardrail de saída disparou", extra={"motivo": motivo})
    return {
        "messages": [AIMessage(content=texto, id=ultima.id)],
        "guardrail_disparado": f"saida:{motivo}",
    }
