# 02 · Modelos: rápido × forte

> Slide: **Anatomia · Modelo**
> Código: [`src/agente/llm.py`](../src/agente/llm.py), [`nodes/classificador.py`](../src/agente/nodes/classificador.py), [`nodes/agente.py`](../src/agente/nodes/agente.py)
> Decisão: [ADR 0002](adr/0002-dois-modelos.md)

## A ideia

Nem toda tarefa precisa do melhor modelo. Este agente usa dois:

| Papel | Função em `llm.py` | Faz o quê | Por que esse modelo |
|---|---|---|---|
| **Rápido** | `modelo_rapido()` | Classifica a intenção e checa prompt injection | Roda em **toda** mensagem e só escolhe um rótulo: precisa ser barato e rápido |
| **Forte** | `modelo_forte()` | Conversa, decide ferramentas, escreve a resposta | Onde a qualidade aparece para o usuário |
| **Juiz** | `modelo_juiz()` | Dá nota às respostas nos evals | Só roda fora do caminho do usuário |

A economia aparece no handoff: "Quero falar com um atendente" é resolvido só pelo modelo rápido (classificador → `handoff`). O modelo forte **nem é chamado**. Isso aparece no painel "Tokens por modelo" do Streamlit e no trace.

> Nos testes deste repositório os dois papéis usam o mesmo modelo (`gpt-5.6-luna`), porque ele já é rápido e barato. A separação continua valendo: é só trocar `LLM_MODELO_FORTE` no `.env`.

## Provider configurável com `init_chat_model`

```python
# src/agente/llm.py (simplificado)
def _criar_modelo(nome, temperatura):
    kwargs = {"api_key": ..., "temperature": temperatura}
    if provider == "openai":
        kwargs["use_responses_api"] = True  # necessária para tools com modelos de raciocínio
    return init_chat_model(nome, model_provider=provider, **kwargs)
```

Trocar de fornecedor é só mudar o `.env`:

```bash
# OpenAI (padrão)
LLM_PROVIDER=openai
LLM_MODELO_RAPIDO=gpt-5.6-luna
LLM_MODELO_FORTE=gpt-5.6-luna

# Anthropic
LLM_PROVIDER=anthropic
LLM_API_KEY=sk-ant-...
LLM_MODELO_RAPIDO=claude-haiku-4-5-20251001
LLM_MODELO_FORTE=claude-sonnet-5
EMBEDDINGS_PROVIDER=openai          # a Anthropic não tem embeddings
EMBEDDINGS_API_KEY=sk-...

# Ollama (100% local, sem chave) — veja "Modo offline" no README
LLM_PROVIDER=ollama
LLM_MODELO_RAPIDO=qwen2.5:3b
LLM_MODELO_FORTE=qwen2.5:3b
EMBEDDINGS_MODELO=nomic-embed-text
```

O teste `tests/test_config.py::test_trocar_provider_nao_muda_codigo` garante que OpenAI, Anthropic e Ollama são instanciados sem mudar uma linha de código.

## Detalhes que pegam as pessoas

- **Modelos de raciocínio não aceitam `temperature`.** A família gpt-5 só aceita o valor padrão. Por isso `LLM_TEMPERATURA` fica vazio por padrão (vazio = não envia).
- **Esforço de raciocínio.** `LLM_REASONING_EFFORT=low` deixa o gpt-5.6-luna mais rápido e barato. Ele aceita `none | low | medium | high`.
- **Responses API.** Nesses modelos, ferramentas + raciocínio só funcionam na Responses API da OpenAI. O `llm.py` já liga `use_responses_api=True`.
- **Modo demo (`LLM_PROVIDER=fake`).** Não chama rede nenhuma e responde uma mensagem fixa. Serve para ver a interface funcionando sem chave.

## Modelos fake nos testes

`ModeloFake` (em `llm.py`) devolve respostas roteirizadas, em ordem, incluindo `tool_calls`. Assim os testes exercitam o grafo inteiro sem rede e sem custo:

```python
modelos(
    rapido=[intencao("reserva")],
    forte=[chamada("consultar_reserva", codigo="ABC1234"), "Sua reserva está confirmada."],
)
```

Uma lista vazia faz o modelo falhar se for chamado. É assim que `test_handoff_nao_chama_modelo_forte` prova que o modelo forte não foi usado.

## Veja funcionando

- No Streamlit, mande "Quero falar com um atendente" e depois "Posso cancelar sem multa?". Compare os "Tokens por modelo" no painel de debug.
- Com `USAR_CLASSIFICADOR=false` o grafo pula o classificador: um modelo só faz tudo. Compare latência e tokens.
