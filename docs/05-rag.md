# 05 · Conhecimento com RAG

> Slides: **Anatomia · Conhecimento**, **Arquitetura (Ferramentas/RAG)**
> Código: [`src/agente/rag/ingestao.py`](../src/agente/rag/ingestao.py), [`rag/retriever.py`](../src/agente/rag/retriever.py), [`tools/faq.py`](../src/agente/tools/faq.py) · base em [`data/faq/`](../data/faq/)

## Por que RAG, e não colocar tudo no prompt?

Com 10 arquivos, até caberia tudo no prompt. Mas:

- **Custo e latência:** o prompt vai em toda chamada. Mandar a base inteira para responder "oi" é desperdício.
- **Escala:** bases reais têm centenas ou milhares de documentos, e não cabem.
- **Qualidade:** com muito texto irrelevante, o modelo se confunde mais. Poucos trechos certos funcionam melhor que muitos trechos quaisquer.
- **Atualização:** mudou uma política? Edite o `.md` e rode `make ingest`. O prompt não muda.

RAG (*Retrieval-Augmented Generation*) = **buscar** os trechos relevantes e **só eles** vão para o modelo.

## As duas metades

### 1. Ingestão (offline): `make ingest`

```
data/faq/*.md → carregar → dividir em trechos → gerar embeddings → gravar no vector store
```

- **Chunking:** `RecursiveCharacterTextSplitter` com `chunk_size=1500` caracteres (≈ 400 a 500 tokens em português) e `overlap=150`. Ele tenta quebrar em parágrafos antes de quebrar em frases. O overlap evita cortar uma regra no meio.
- **Embeddings:** cada trecho vira um vetor (`text-embedding-3-small` = 1536 números) que representa o seu significado. Textos parecidos viram vetores próximos.
- **Metadado `fonte`:** cada trecho guarda o nome do arquivo de origem. É isso que permite citar a fonte.
- **Idempotência:** a coleção é recriada a cada ingestão, com ids determinísticos (`faq:cancelamento.md#0`). Rodar duas vezes não duplica nada, e arquivos apagados somem da base.

### 2. Busca (a cada pergunta)

```python
buscar("Posso cancelar sem multa?", k=4)
# [Trecho(fonte="cancelamento.md", score=0.71, texto="..."), ...]
```

- A pergunta vira um embedding e o banco devolve os `k` vetores mais próximos (similaridade de cosseno).
- **`RAG_K` (top-k, padrão 4):** k pequeno perde contexto, k grande traz ruído e custa mais tokens.
- **`RAG_SCORE_MINIMO` (padrão 0,3):** trechos abaixo disso são descartados. Se nada sobra, a ferramenta devolve "Nenhum trecho relevante encontrado…", e o prompt manda o agente dizer que não sabe. **É melhor dizer "não sei" do que responder com um trecho que não tem a ver.**

### 3. A ferramenta `buscar_faq`

O agente chama o RAG como qualquer outra ferramenta. Assim ele decide **quando** buscar (em "oi" não busca), e **reescreve a pergunta** de forma clara antes de buscar. O retorno traz a fonte de cada trecho, e o prompt exige terminar a resposta com `(Fonte: arquivo.md)`.

## Backends

| `RAG_BACKEND` | Onde | Quando usar |
|---|---|---|
| `pgvector` (padrão) | Postgres do compose, tabela `langchain_pg_embedding` | Um banco só para memória e vetores, igual à produção |
| `chroma` | `.data/chroma` | Sem Docker |

> Trocou de modelo de embeddings? Rode `make ingest` de novo: vetores de modelos diferentes têm dimensões diferentes e não se misturam.

## Como avaliar a recuperação

Avalie a busca **separada** da resposta. Se a busca traz o trecho errado, nenhum prompt salva a resposta.

- **Teste de recuperação** (`tests/test_rag.py`): "a pergunta X traz o arquivo Y no top-3". No CI roda com embeddings fake (saco de palavras, sem rede), o que prova o encanamento. Com embeddings reais, o mesmo teste mede a qualidade.
- **Métrica `fonte_citada` nos evals:** a resposta citou o arquivo esperado?
- **Critério `sem_alucinacao` do juiz:** a resposta afirmou algo que não estava na base?
- **Painel "Trechos recuperados" no Streamlit:** mostra fonte e score. Score baixo em pergunta respondível indica problema de chunking ou de conteúdo.

## Veja funcionando

- "Posso cancelar sem multa?" → cita `cancelamento.md`, e o expander **Trechos recuperados** mostra os scores.
- "Vocês alugam motos?" → a base não fala disso, e o agente não inventa.
- `make ingest` duas vezes, e depois `make db-shell`: `select count(*) from langchain_pg_embedding;` → continua 10.

## Exercício

Adicione `data/faq/pets.md` ("Aceitamos animais em caixa de transporte, com taxa de limpeza se houver pelos…"), rode `make ingest` e pergunte "Posso levar meu cachorro?". Depois adicione o caso em `evals/dataset.jsonl`.
