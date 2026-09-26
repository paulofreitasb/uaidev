# 03 · Ferramentas (tool calling)

> Slides: **Anatomia · Ferramentas**, **Por dentro do código**, **Caminho de uma mensagem (passo 04)**
> Código: [`src/agente/tools/`](../src/agente/tools/) · nó `ferramentas` em [`grafo.py`](../src/agente/grafo.py)

## O que é tool calling

O modelo não executa código. Ele **pede** para executar. O ciclo é:

1. Enviamos ao modelo a conversa **e a lista de ferramentas**: nome, descrição e parâmetros de cada uma.
2. O modelo responde com texto **ou** com um pedido: `consultar_reserva(codigo="ABC1234")`.
3. **Nós** executamos a função Python e devolvemos o resultado como uma mensagem de ferramenta.
4. O modelo lê o resultado e decide: responde ao usuário ou pede outra ferramenta.

## As ferramentas deste agente

| Ferramenta | Arquivo | O que faz |
|---|---|---|
| `buscar_faq(pergunta)` | [`tools/faq.py`](../src/agente/tools/faq.py) | Busca na base de conhecimento (RAG, veja [05](05-rag.md)) |
| `consultar_reserva(codigo)` | [`tools/reservas.py`](../src/agente/tools/reservas.py) | Status de uma reserva, sobre a API mock `data/reservas_mock.json` |
| `cotar_aluguel(categoria, dias, cidade)` | [`tools/cotacao.py`](../src/agente/tools/cotacao.py) | Regra de negócio: diária × dias, 10% de desconto a partir de 7 dias |
| `transferir_para_humano(motivo)` | [`tools/handoff.py`](../src/agente/tools/handoff.py) | O agente pede um humano quando não sabe resolver |

## Como o modelo escolhe: a docstring é o prompt da ferramenta

O decorator `@tool` transforma a função em um schema. **O nome, a docstring e os tipos são tudo o que o modelo vê.**

```python
@tool
def consultar_reserva(codigo: str) -> str:
    """Consulta o status e os detalhes de uma reserva da Locadora Exemplo.

    Use quando o cliente perguntar sobre uma reserva existente. O código tem
    3 letras e 4 números, por exemplo ABC1234.

    Args:
        codigo: código da reserva informado pelo cliente.
    """
```

Boas práticas de docstring:

- **Diga quando usar**, não só o que faz ("Use quando o cliente perguntar sobre…").
- **Dê o formato esperado com exemplo** ("3 letras e 4 números, por exemplo ABC1234").
- **Liste valores válidos** quando forem poucos (`categoria: economico, compacto, sedan, suv ou premium`).
- **Um parâmetro, uma linha em `Args`.**

## Boas práticas de implementação

- **Valide a entrada e devolva um erro amigável, escrito para o modelo repassar.** Um código inválido não levanta exceção; volta o texto *"Código 'AB12' inválido. O código tem 3 letras seguidas de 4 números, por exemplo ABC1234. Peça ao cliente para conferir."*. O modelo lê isso e pede o código certo.
- **Conta de dinheiro fica em código, não no modelo.** `cotar_aluguel` usa `Decimal` e arredondamento explícito. O LLM entende o pedido; o Python faz a conta. O guardrail de saída ainda confere se todo valor em R$ da resposta veio de uma ferramenta.
- **Normalize a entrada.** `" xyz-9876 "` vira `XYZ9876`; `"BH"` vira `Belo Horizonte`.
- **Retorno estruturado para humanos, também.** `buscar_faq` usa `response_format="content_and_artifact"`: o texto vai para o modelo, e os trechos com fonte e score ficam no `artifact`, para o painel de debug e os evals.

## Proteção contra loop

Um modelo pode ficar pedindo ferramentas sem parar. O grafo conta as rodadas (`tentativas_ferramenta`) e aplica duas travas:

1. Ao atingir `MAX_TENTATIVAS_FERRAMENTA` (padrão 3), o nó `agente` chama o modelo **sem** ferramentas, e ele é obrigado a responder em texto.
2. Se mesmo assim vier um pedido de ferramenta, a rota vai para o guardrail de saída, que troca a mensagem por "Não consegui concluir sua solicitação agora…". Isso também evita deixar `tool_calls` sem resposta no histórico, o que quebraria a próxima chamada.

Teste: `tests/test_grafo.py::test_limite_de_tentativas_de_ferramenta`.

## O mesmo loop, sem LangGraph

Para desmistificar: isto é o que o LangGraph faz por nós no ciclo agente ⇄ ferramentas.

```python
from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage
from agente.llm import modelo_forte
from agente.tools import TOOLS

ferramentas = {t.name: t for t in TOOLS}
modelo = modelo_forte().bind_tools(TOOLS)
mensagens = [SystemMessage("Você é a Duda..."), HumanMessage("Status da reserva ABC1234?")]

for _ in range(3):  # limite contra loop
    resposta = modelo.invoke(mensagens)
    mensagens.append(resposta)
    if not resposta.tool_calls:
        break  # o modelo respondeu em texto: fim
    for chamada in resposta.tool_calls:
        resultado = ferramentas[chamada["name"]].invoke(chamada["args"])
        mensagens.append(ToolMessage(resultado, tool_call_id=chamada["id"]))

print(resposta.text)
```

São cerca de 15 linhas. O que o LangGraph acrescenta: estado tipado, checkpointer (memória), roteamento explícito para outros nós (classificador, guardrails, handoff), visualização e integração com traces. Para um loop simples, o Python puro resolve. Veja o [ADR 0001](adr/0001-langgraph.md).

## Veja funcionando

- No Streamlit: "Qual o status da reserva ABC1234?" → expander **Ferramentas chamadas** mostra nome, argumentos e retorno.
- "Quanto fica um SUV por 10 dias em BH?" → `cotar_aluguel` → `R$ 2.069,10`.
- "Qual o status da reserva AB12?" → o agente pede o código no formato certo.
- No Langfuse, abra o trace: o nó `ferramentas` aparece com a chamada e o retorno.

## Exercício

Crie `cancelar_reserva(codigo)` que muda o status no mock (em memória). Escreva a docstring, adicione à lista `TOOLS`, crie os testes em `tests/test_tools.py` e um caso novo em `evals/dataset.jsonl`.
