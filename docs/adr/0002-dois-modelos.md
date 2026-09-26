# ADR 0002 — Dois modelos: rápido e forte

**Status:** aceita · **Data:** 2026-09

## Contexto
Toda mensagem passa por classificação de intenção e checagem de prompt injection. Só parte delas precisa de raciocínio de verdade (decidir ferramentas, escrever a resposta).

## Decisão
Dois papéis configuráveis por env: `LLM_MODELO_RAPIDO` (classificador e guardrail) e `LLM_MODELO_FORTE` (agente). Ambos criados por `init_chat_model`, com o provider em `LLM_PROVIDER`.

## Por quê
- **Custo e latência:** tarefas de rótulo não precisam do modelo mais caro. O handoff explícito nem chama o modelo forte.
- **Lição da Liza:** separar "entender o pedido" de "resolver o pedido" deixa cada parte mais barata e mais fácil de avaliar.
- **Sem lock-in:** OpenAI, Anthropic, Google ou Ollama trocando só o `.env`.

## Alternativas consideradas
- **Um modelo só:** mais simples, e disponível com `USAR_CLASSIFICADOR=false`.
- **Classificador por regras/embeddings:** mais barato ainda, mas frágil com linguagem natural e contexto de vários turnos.

## Consequências
- Duas chamadas extras de modelo rápido por mensagem (injection + classificador). Mitigações: `GUARDRAIL_INJECAO_LLM=false`, ou juntar as duas em uma saída estruturada (desafio).
- O classificador pode errar; os evals medem a acurácia (critério ≥ 90%).
