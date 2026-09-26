# 09 · Observabilidade

> Slides: **Como observamos um agente em produção?**, **E se o agente falasse com a observabilidade?**
> Código: [`src/agente/observabilidade.py`](../src/agente/observabilidade.py), [`src/agente/logging.py`](../src/agente/logging.py)

## Por que um agente precisa de mais que logs

Num sistema tradicional, a mesma entrada dá a mesma saída. Num agente, a mesma pergunta pode seguir caminhos diferentes: chamar outra ferramenta, buscar outro trecho, gastar o dobro de tokens. Para entender o que aconteceu você precisa do **trace**: a árvore de cada passo, com entrada, saída, tempo e custo.

## Langfuse local, sem criar conta

```bash
make up-obs      # Postgres + Langfuse v3 (web, worker, ClickHouse, Redis, MinIO)
```

Abra <http://localhost:3000> e entre com `admin@exemplo.local` / `senha-local-123` (do `.env.example`). A organização, o projeto e as chaves (`pk-lf-local-dev` / `sk-lf-local-dev`) são **criados automaticamente no primeiro start** pelas variáveis `LANGFUSE_INIT_*` do compose. Ninguém precisa se cadastrar.

> Por que Langfuse v3, com 5 containers? O SDK da versão 2 não funciona com o LangChain 1.x. Veja o [ADR 0004](adr/0004-langfuse-v3.md).

## O que cada trace tem

```
agente (trace)                          tags: canal:streamlit, prompt:bf7cd5f7, intencao:cotacao
└── responder                           input: "Quanto fica um SUV..."  output: "Fica R$ 2.069,10..."
    └── agente (LangGraph)
        ├── guardrail_entrada
        │   └── ChatOpenAI              ← checagem de injection (modelo rápido)
        ├── classificador
        │   └── ChatOpenAI              ← intenção (modelo rápido)
        ├── agente
        │   └── ChatOpenAI              ← pede cotar_aluguel (modelo forte)
        ├── ferramentas
        │   └── cotar_aluguel           ← argumentos e retorno
        ├── agente
        │   └── ChatOpenAI              ← resposta final
        └── guardrail_saida
```

**Metadados e tags de cada trace:**

| Campo | Valor | Para quê |
|---|---|---|
| `session_id` | hash do `thread_id` | Agrupar a conversa inteira sem expor o id real |
| `versao_prompt` (e tag `prompt:<hash>`, e `version`) | hash do `sistema.md` | Comparar versões do prompt |
| `canal` | `streamlit` ou `eval` | Separar tráfego real de avaliação |
| tag `intencao:<x>` | intenção detectada | Filtrar por tipo de pedido |
| tag `handoff` | presente se transferiu | Taxa de handoff |
| tag `guardrail:<x>` | ex.: `guardrail:entrada:prompt_injection` | Quantos ataques, quantas respostas barradas |

No Langfuse: **Traces → Filters → Tags** → `intencao:faq`, ou `prompt:bf7cd5f7` para ver só uma versão do prompt. Os evals publicam as notas do juiz como **scores** nos traces com `canal:eval`.

## Como funciona no código

```python
# servico.py
with observabilidade.rastrear(thread_id, canal) as rastreio:
    estado = grafo.invoke(entrada, {"callbacks": [uso, *rastreio.callbacks], ...})
    ...
    rastreio.resultado = {"intencao": ..., "handoff": ..., "guardrail_disparado": ...}
```

- `rastrear()` escolhe o backend pelo `.env`:
  - `LANGFUSE_PUBLIC_KEY` + `LANGFUSE_SECRET_KEY` → Langfuse (callback do LangChain + span raiz com `propagate_attributes`);
  - `LANGSMITH_TRACING=true` → LangSmith (o LangChain envia sozinho; metadados e tags vão na config);
  - nenhum → **não faz nada** e registra `observabilidade desligada` uma única vez.
- A intenção, o handoff e o guardrail só são conhecidos **depois** da execução. Por isso as tags do resultado são aplicadas no fim, antes de fechar o span raiz.
- Tokens por modelo vêm do `UsageMetadataCallbackHandler` do LangChain, independentemente do Langfuse. Aparecem no painel do Streamlit.

## Logs estruturados

`logging.py` escreve **JSON**, uma linha por evento, com PII mascarada no formatter:

```json
{"ts": "2026-09-25T21:57:39.408+00:00", "nivel": "INFO", "logger": "agente.nodes.guardrails",
 "msg": "guardrail de entrada disparou", "motivo": "prompt_injection"}
```

JSON porque log é para ser **consultado** (filtrar por `motivo`, agrupar por `logger`), não só lido.

## O que olhar (o painel mínimo de um agente)

| Métrica | Onde | Por que importa |
|---|---|---|
| **Latência por nó** | Trace → duração de cada span | Descobrir o gargalo (quase sempre as chamadas de modelo) |
| **Taxa de handoff** | Traces com tag `handoff` / total | Alta demais = agente não resolve; zero = talvez não esteja transferindo quando devia |
| **Erros de ferramenta** | Spans com erro; retornos "não encontrada" / "inválido" | Integração quebrada ou docstring confusa |
| **Custo por conversa** | Tokens por sessão × preço | Um prompt maior ou um loop de ferramentas aparece aqui primeiro |
| **Guardrails disparados** | Tags `guardrail:*` | Ataques e alucinações barradas |
| **Distribuição de intenções** | Tags `intencao:*` | O que os clientes realmente pedem, e o que priorizar |

O paralelo com a Liza: essas são as mesmas perguntas que fazemos todo dia sobre um agente em produção. O trace responde **o que** aconteceu; as métricas agregadas respondem **com que frequência**.

## "E se o agente falasse com a observabilidade?"

Os traces também são dados. Um próximo passo natural (veja [desafios](desafios.md)) é uma ferramenta que consulta a API do Langfuse ("quantos handoffs hoje?", "qual intenção mais falhou?"), ou um job que roda o juiz sobre uma amostra diária de traces reais: a avaliação **assíncrona** do [08](08-evaluation.md).

## Alternativas

- **Langfuse Cloud:** troque `LANGFUSE_HOST` e as chaves pelas do seu projeto em cloud.langfuse.com.
- **LangSmith:** `LANGSMITH_TRACING=true`, `LANGSMITH_API_KEY=...` e as chaves do Langfuse vazias.
