# ADR 0003 — Canal desacoplado do agente

**Status:** aceita · **Data:** 2026-09

## Contexto
Na v1 o canal é o Streamlit. Na v2 entra o WhatsApp (Twilio). Os evals também precisam "conversar" com o agente.

## Decisão
O agente expõe **uma única função pública**: `agente.responder(thread_id, mensagem, canal) -> Resposta`. Nenhum canal importa LangGraph, prompts ou nós.

## Por quê
- **Adicionar canal não mexe no agente:** o webhook do WhatsApp será só mais um chamador de `responder()`.
- **O mesmo agente, experiências diferentes por canal:** o `canal` vai no estado e no trace, e o agente pode adaptar formato por canal sem que o canal conheça o agente.
- **Evals e testes usam a mesma porta** que o usuário.
- A `Resposta` já traz o que um canal precisa para debug (ferramentas, trechos, intenção, trace), sem vazar objetos internos.

## Consequências
- Tudo o que um canal precisar tem de passar pela `Resposta` (ou por `historico()`/`estado_salvo()`, também públicas). Isso é intencional: força a fronteira a ser pensada.
