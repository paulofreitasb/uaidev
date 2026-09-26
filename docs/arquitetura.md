# Arquitetura

> Slide: **"Arquitetura mínima"** — Canal → Agente → Ferramentas → Dados → Observar.

Este documento explica **como as peças se encaixam** e, principalmente, **por que** elas estão separadas assim. Se você só vai ler um documento antes de abrir o código, leia este.

## Visão em camadas

```
┌──────────────────────────────────────────────────────────────┐
│  CANAL             Streamlit  ·  app/streamlit_app.py         │
│                    (WhatsApp/Twilio entra aqui na v2)         │
└───────────────────────────┬──────────────────────────────────┘
                            │  agente.responder(thread_id, msg, canal)
┌───────────────────────────▼──────────────────────────────────┐
│  AGENTE (LangGraph)          src/agente/grafo.py              │
│  guardrail_entrada → classificador → agente ⇄ ferramentas     │
│                                  ↘ handoff   → guardrail_saida│
└──────┬──────────────────┬───────────────────┬────────────────┘
       │                  │                   │
┌──────▼──────┐   ┌───────▼───────┐   ┌───────▼────────────────┐
│ FERRAMENTAS │   │  CONHECIMENTO │   │  MEMÓRIA               │
│ tools/      │   │  rag/         │   │  memoria.py            │
│ reservas    │   │  pgvector ou  │   │  checkpointer Postgres │
│ cotação     │   │  Chroma       │   │  ou SQLite             │
│ faq, handoff│   └───────────────┘   └────────────────────────┘
└─────────────┘
   ───── Observabilidade (observabilidade.py → Langfuse/LangSmith) em todas as camadas ─────
   ───── Evaluation (evals/) roda o mesmo grafo, fora do caminho do usuário ──────────────
```

## As camadas, uma a uma

| Camada | Responsabilidade | Onde está | Não deve saber de… |
|---|---|---|---|
| **Canal** | Receber a mensagem do usuário e mostrar a resposta | `app/streamlit_app.py` | LangGraph, prompts, modelos |
| **Agente** | Decidir o que fazer com a mensagem | `src/agente/grafo.py`, `nodes/` | Qual canal está falando com ele |
| **Ferramentas** | Executar ações e buscar dados | `src/agente/tools/` | Como o modelo decidiu chamá-las |
| **Conhecimento** | Encontrar trechos relevantes da base | `src/agente/rag/` | O resto do agente |
| **Memória** | Guardar o estado de cada conversa | `src/agente/memoria.py` | O conteúdo das mensagens |
| **Observabilidade** | Registrar o que aconteceu | `src/agente/observabilidade.py` | Regras de negócio |

## Princípio central: o canal não conhece o LangGraph

O Streamlit chama **uma única função**, definida em `src/agente/servico.py`:

```python
from agente import responder

resposta = responder(
    thread_id="abc123", mensagem="Qual o status da reserva ABC1234?", canal="streamlit"
)
resposta.texto  # o que mostrar ao usuário
resposta.intencao  # "reserva"
resposta.ferramentas  # [ChamadaFerramenta(nome="consultar_reserva", ...)]
resposta.trace_url  # link para o trace no Langfuse
```

Por que isso importa:

- **Trocar ou adicionar canais não mexe no agente.** Na v2, um webhook do WhatsApp chama o mesmo `responder()`. É a lição de *"o mesmo agente, experiências diferentes por canal"*.
- **Os evals usam a mesma porta de entrada** (`canal="eval"`). O que é avaliado é exatamente o que o usuário usa.
- **Testar fica fácil:** os testes de ponta a ponta (`tests/test_grafo.py`) só chamam `responder()`.

Esse padrão tem nome: é uma *fachada* (Facade). Uma interface pequena esconde um subsistema complexo.

## O que acontece dentro de `responder()`

1. **Mascara PII** (CPF, cartão, e-mail) já na fronteira. Nada com dado pessoal entra no grafo, nos logs ou no trace.
2. **Abre um trace** (se houver observabilidade configurada).
3. **Invoca o grafo** com o `thread_id`. O checkpointer carrega o histórico daquela conversa.
4. **Monta a `Resposta`**: texto final, intenção, ferramentas chamadas (com argumentos e retorno), trechos do RAG, guardrails, latência e tokens por modelo.
5. **Fecha o trace** com as tags do resultado (`intencao:faq`, `handoff`, `guardrail:...`).

O passo a passo detalhado de uma mensagem está em [07-fluxo.md](07-fluxo.md).

## Onde cada decisão foi registrada

As decisões de arquitetura estão em [`docs/adr/`](adr/):

- [0001 — LangGraph como orquestrador](adr/0001-langgraph.md)
- [0002 — Dois modelos: rápido e forte](adr/0002-dois-modelos.md)
- [0003 — Canal desacoplado do agente](adr/0003-canal-desacoplado.md)
- [0004 — Langfuse v3 em vez de v2](adr/0004-langfuse-v3.md)

## Infraestrutura local

Tudo sobe com Docker Compose (`docker-compose.yml`), com perfis para não subir o que você não vai usar:

| Serviço | Para quê | Perfil | Comando |
|---|---|---|---|
| `postgres` (pgvector) | Memória (checkpointer) + RAG, e um banco separado para o Langfuse | padrão | `make up` |
| `langfuse-web`, `langfuse-worker`, `clickhouse`, `redis`, `minio` | Langfuse v3 self-hosted (traces) | `observabilidade` | `make up-obs` |
| `ollama` | Modelos locais, sem chave de API | `offline` | `make up-all` |
| `app` | O Streamlit em container | `app` | `make up-all` |

Sem Docker? Use `MEMORIA_BACKEND=sqlite`, `RAG_BACKEND=chroma` e deixe as chaves do Langfuse vazias. O código é o mesmo, só muda o `.env`.
