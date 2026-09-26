"""LLM como juiz: nota de 1 a 5 por critério, com justificativa.

Por que um juiz? Métricas determinísticas (acertou a intenção? chamou a ferramenta?)
não dizem se a resposta foi boa. O juiz avalia o que só um leitor avalia: resolveu,
tom, alucinação, política. Limites: o juiz também erra e tem vieses. Por isso ele
recebe a referência e os dados das ferramentas, usa temperatura 0 quando o modelo
aceita, e suas notas são comparadas entre versões, não lidas como verdade absoluta.
"""

from __future__ import annotations

import json
from typing import Any

from langchain_core.callbacks import UsageMetadataCallbackHandler
from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field

from agente import prompts
from agente.llm import modelo_juiz

CRITERIOS = ("resolveu", "tom", "sem_alucinacao", "seguiu_politica")


class Nota(BaseModel):
    nota: int = Field(description="de 1 (péssimo) a 5 (excelente)")
    justificativa: str = Field(description="uma frase")


class Avaliacao(BaseModel):
    """Notas do juiz para uma conversa."""

    resolveu: Nota
    tom: Nota
    sem_alucinacao: Nota
    seguiu_politica: Nota


def julgar(
    caso: dict[str, Any], conversa: list[tuple[str, str]], ferramentas: list[dict[str, Any]]
) -> tuple[Avaliacao, int]:
    """Devolve a avaliação e os tokens gastos pelo juiz."""
    transcricao = "\n".join(f"Cliente: {c}\nAssistente: {a}" for c, a in conversa)
    pedido = (
        f"# Conversa\n{transcricao}\n\n"
        f"# Ferramentas chamadas no último turno (dados reais)\n"
        f"{json.dumps(ferramentas, ensure_ascii=False) if ferramentas else 'nenhuma'}\n\n"
        f"# Critérios do caso\n- " + "\n- ".join(caso["criterios"]) + "\n\n"
        f"# Referência\n{caso['referencia']}"
    )
    juiz = modelo_juiz().with_structured_output(Avaliacao)
    uso = UsageMetadataCallbackHandler()
    avaliacao = juiz.invoke(
        [SystemMessage(prompts.carregar("juiz")), HumanMessage(pedido)], {"callbacks": [uso]}
    )
    assert isinstance(avaliacao, Avaliacao)
    for criterio in CRITERIOS:  # garante a escala, caso o modelo escape dela
        nota = getattr(avaliacao, criterio)
        nota.nota = min(5, max(1, nota.nota))
    return avaliacao, sum(u["total_tokens"] for u in uso.usage_metadata.values())
