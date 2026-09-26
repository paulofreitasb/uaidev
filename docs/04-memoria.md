# 04 · Memória

> Slides: **Anatomia · Memória**, **Dia 1 · histórico salvo**
> Código: [`src/agente/memoria.py`](../src/agente/memoria.py), janela em [`nodes/agente.py`](../src/agente/nodes/agente.py)

## O problema

O modelo não lembra de nada entre chamadas: cada requisição é independente. "Memória" é mandar de novo, a cada mensagem, o que importa da conversa.

## Curto prazo × longo prazo

| | Curto prazo (este repositório) | Longo prazo (desafio) |
|---|---|---|
| **O que guarda** | A conversa atual: mensagens, chamadas de ferramenta, estado do grafo | Fatos sobre o cliente entre conversas ("prefere SUV", "mora em BH") |
| **Chave** | `thread_id` (uma conversa) | id do usuário |
| **Como** | Checkpointer do LangGraph | Store / banco próprio, com extração de fatos |
| **Expira** | Quando o usuário começa uma conversa nova | Nunca (ou por política de retenção) |

## Como funciona o checkpointer

A cada passo do grafo, o LangGraph salva o **estado inteiro** (`EstadoAgente`) no checkpointer, com a chave `thread_id`. Na próxima mensagem da mesma thread, ele carrega o último estado e continua de onde parou.

```python
# servico.py
config = {"configurable": {"thread_id": thread_id}}
obter_grafo().invoke({"messages": [HumanMessage(mensagem)], ...}, config)
```

O campo `messages` usa o reducer `add_messages`, que **acumula** em vez de sobrescrever. Os outros campos (`intencao`, `bloqueado`, `tentativas_ferramenta`...) são zerados a cada mensagem pelo `responder()`, porque valem só para aquele turno.

O que fica salvo (veja no Streamlit, na barra lateral → **Estado salvo**):

- todas as mensagens: do cliente, do agente, os pedidos de ferramenta e os retornos;
- os campos do estado no último passo;
- um checkpoint por passo, o que permite retomar e até "voltar no tempo" (*time travel* do LangGraph).

## Dois backends, mesmo código

```python
# memoria.py
if config.memoria_backend == "sqlite":
    return SqliteSaver(sqlite3.connect(path, check_same_thread=False))
pool = ConnectionPool(database_url, kwargs={"autocommit": True, ...})
saver = PostgresSaver(pool)
saver.setup()   # cria as tabelas na primeira vez
```

- **`postgres` (padrão):** no Postgres do compose, o mesmo banco do RAG. É o que se usa em produção. Usa um *pool* de conexões porque o Streamlit atende várias sessões ao mesmo tempo.
- **`sqlite`:** para quem não tem Docker. Um arquivo em `.data/memoria.sqlite`.

Veja as tabelas: `make db-shell` e depois `\dt` → `checkpoints`, `checkpoint_writes`, `checkpoint_blobs`, `checkpoint_migrations`.

## Janela de contexto (`trim_messages`)

Mandar o histórico **inteiro** em toda chamada fica caro e lento em conversas longas. O nó `agente` envia só as últimas `JANELA_MENSAGENS` (padrão 20):

```python
janela = trim_messages(
    estado["messages"],
    strategy="last",
    token_counter=len,
    max_tokens=config.janela_mensagens,
    start_on="human",
)
```

- `token_counter=len` conta **mensagens**, não tokens: é simples e previsível.
- `start_on="human"` garante que a janela não comece no meio de uma chamada de ferramenta, porque um retorno de ferramenta sem o pedido quebra a chamada ao modelo.
- **Trade-off:** o histórico completo continua salvo, mas o modelo "esquece" o que ficou fora da janela. Alternativas: resumir mensagens antigas com o modelo rápido, ou guardar fatos na memória de longo prazo.

## Veja funcionando

1. No Streamlit: "Meu nome é Ana" e depois "Qual meu nome?" → "Ana".
2. Clique em **Nova conversa**: novo `thread_id`, o agente não lembra mais.
3. Recarregue a página: o `thread_id` fica na URL (`?thread=...`), então a conversa volta, carregada do checkpointer.
4. Pare tudo (`make down`, `make up`) e reabra a mesma URL: o histórico continua lá, no volume `pgdata`.
5. Com `MEMORIA_BACKEND=sqlite` o comportamento é o mesmo.

Testes: `tests/test_grafo.py::TestMemoria` (SQLite) e `tests/test_integracao.py::test_memoria_no_postgres_persiste` (Postgres).
