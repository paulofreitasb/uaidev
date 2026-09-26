# ADR 0001 — LangGraph como orquestrador

**Status:** aceita · **Data:** 2026-09

## Contexto
Um agente conversacional precisa de um loop (modelo → ferramenta → modelo), de estado por conversa e de desvios (guardrails, classificador, handoff). Dá para escrever isso em Python puro, com um framework de "agente pronto" ou com um orquestrador de grafo.

## Decisão
Usar **LangGraph**: um `StateGraph` com estado tipado (`EstadoAgente`), nós como funções puras e arestas condicionais explícitas.

## Por quê
- **Fluxo explícito e legível:** o grafo inteiro cabe em `grafo.py`, e cada decisão de rota é uma função de 3 linhas, fácil de testar.
- **Estado tipado** em vez de variáveis soltas.
- **Checkpointer nativo:** memória por `thread_id` em Postgres ou SQLite, sem código próprio.
- **Visualizável** (`get_graph().draw_mermaid()`) e integrado aos traces: cada nó vira um span.
- É o que usamos na Liza, então a experiência da palestra se aplica.

## Alternativas consideradas
- **Loop puro em Python:** ótimo para entender (mostrado em [03-ferramentas](../03-ferramentas.md)), mas memória, roteamento e observabilidade teriam de ser escritos à mão.
- **Agente pronto (`create_agent`):** menos código, mas esconde o fluxo, o que é ruim para um repositório didático.

## Consequências
- Dependência de uma biblioteca que evolui rápido: versões fixadas no `uv.lock`, Dependabot e CI.
- Quem nunca viu grafos tem uma curva inicial pequena; o [07-fluxo](../07-fluxo.md) existe para isso.
