# Como contribuir

Obrigado pelo interesse! Este é um repositório **didático**: toda contribuição deve deixar o código mais fácil de entender, não só mais completo.

## Antes de começar

```bash
make setup      # dependências, .env e hooks do pre-commit
make up         # Postgres + pgvector
make ingest
make check      # lint + mypy --strict + testes: é o que o CI roda
```

## Regras do jogo

1. **Simples primeiro.** Se a mudança precisa de uma abstração nova, explique no PR por que a versão simples não serve.
2. **Comente o porquê, não o quê.** Nos pontos-chave (roteamento, checkpointer, juiz, guardrails), um comentário curto explicando a decisão. Nada de narrar o óbvio.
3. **Teste sem rede.** Testes unitários usam o `ModeloFake` (veja `tests/conftest.py`). Nenhum teste de `make test` pode chamar uma API de LLM.
4. **Mexeu em comportamento? Rode os evals.** Mudanças em prompts, ferramentas ou RAG precisam de `make evals` sem regressão. Cole a tabela no PR. Se a mudança melhora o agente, promova o baseline (`make evals-baseline`) no mesmo PR.
5. **Conceito novo = doc nova.** Se o PR introduz um conceito, atualize o `docs/` correspondente e a tabela "slide → código" do README.
6. **Dados 100% fictícios.** Nada de nomes, códigos ou marcas reais, nem em testes. Nunca versione chaves: o CI e o pre-commit rodam o gitleaks.

## Fluxo

1. Abra uma issue descrevendo o problema ou a ideia.
2. Crie uma branch a partir da `main` e abra um PR usando o template.
3. O CI precisa estar verde. A `main` é protegida: só entra por PR revisado.

## Estilo

- Python ≥ 3.11, `ruff` (linha de 100) e `mypy --strict` em `src/`.
- Nomes em português, como no resto do código (`responder`, `consultar_reserva`, `guardrail_saida`).
- Commits curtos no imperativo: `adiciona ferramenta de cancelamento`.

Ao participar, você concorda com o [Código de Conduta](CODE_OF_CONDUCT.md).
