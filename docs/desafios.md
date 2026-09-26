# Desafios: continue praticando

> Slide: **Continue praticando**

Cada desafio tem uma dica de onde começar e um critério objetivo de "pronto". Rode `make check` e `make evals` no fim de cada um: o desafio só está pronto se nada regredir.

## Os 3 desafios da palestra

### 1. Uma ferramenta nova: cancelar reserva
Permita que o cliente cancele uma reserva pelo chat.

- **Dica:** copie `tools/reservas.py`. Cancele só reservas `confirmada` ou `aguardando pagamento`, e **peça confirmação** antes ("Confirma o cancelamento da ABC1234?"). Leia o [03-ferramentas](03-ferramentas.md).
- **Pronto quando:** a ferramenta está em `TOOLS`, com docstring e testes de sucesso, reserva já cancelada e código inválido; há dois casos novos em `evals/dataset.jsonl` (com e sem confirmação); `make evals` passa.

### 2. Aumente a base de conhecimento
Adicione três políticas novas (ex.: pets, viagem ao exterior, carro elétrico).

- **Dica:** crie os `.md` em `data/faq/`, rode `make ingest` e confira os scores no expander "Trechos recuperados". Leia o [05-rag](05-rag.md).
- **Pronto quando:** cada arquivo novo é recuperado no top-3 por uma pergunta nova em `tests/test_rag.py`, e há um caso por arquivo no dataset com `fonte_esperada`.

### 3. Melhore uma métrica
Escolha uma métrica do `make evals` (ex.: `latencia_media_ms` ou `tokens_por_caso`) e melhore sem piorar as outras.

- **Dica:** experimente `FILTRAR_FERRAMENTAS_POR_INTENCAO=true`, `LLM_REASONING_EFFORT=none` no modelo rápido, ou um `sistema.md` mais curto.
- **Pronto quando:** o resultado novo mostra a melhora contra o baseline, sem nenhuma métrica de qualidade com ❌, e você promoveu o novo baseline com `make evals-baseline`.

## Bônus

### 4. Memória de longo prazo
Faça o agente lembrar do nome e da categoria preferida do cliente **entre conversas**.

- **Dica:** use o `store` do LangGraph (`PostgresStore`) com a chave do usuário, e um nó que extrai fatos com o modelo rápido. Leia o [04-memoria](04-memoria.md).
- **Pronto quando:** "Meu nome é Ana" numa thread e "Qual meu nome?" em **outra** thread, com o mesmo usuário, respondem "Ana"; há um teste com modelo fake cobrindo isso.

### 5. Um canal novo sem mexer no agente
Crie um CLI (`python -m agente.cli`) que conversa pelo terminal.

- **Dica:** só `responder()` pode ser importado. Leia o [ADR 0003](adr/0003-canal-desacoplado.md).
- **Pronto quando:** o CLI mantém a conversa pela `thread_id`, e o `git diff` não toca em nada dentro de `src/agente/` além do arquivo novo do canal.

### 6. O agente que fala com a observabilidade
Uma ferramenta `consultar_metricas(periodo)` que usa a API do Langfuse para responder "quantos handoffs tivemos hoje?".

- **Dica:** `Langfuse().api.trace.list(tags=["handoff"], from_timestamp=...)`. Exponha só para um canal interno (ex.: `canal="interno"`). Leia o [09-observabilidade](09-observabilidade.md).
- **Pronto quando:** a pergunta devolve o número certo (compare com o filtro da UI do Langfuse), e a ferramenta **não** está disponível no canal `streamlit`.
