# Changelog

## v1.0.0 — 2026-09-25

Primeira versão pública, 100% local.

### Agente
- Grafo LangGraph: `guardrail_entrada → classificador → agente ⇄ ferramentas → guardrail_saida`, com `handoff`.
- Dois modelos (rápido e forte) com provider configurável: OpenAI, Anthropic, Google, Ollama e modo `fake`.
- Ferramentas: `buscar_faq` (RAG), `consultar_reserva` (API mock), `cotar_aluguel` (regra de negócio) e `transferir_para_humano`.
- Memória por conversa com checkpointer Postgres (padrão) ou SQLite, e janela de contexto.
- RAG com pgvector (padrão) ou Chroma, com ingestão idempotente.
- Guardrails: tamanho, PII (CPF, cartão, e-mail), prompt injection (regras + LLM), promessas fora da política, valores em R$ sem ferramenta, limite de ferramentas e tamanho da resposta.

### Canal e observabilidade
- Streamlit com painel de debug: intenção, ferramentas, trechos, guardrails, latência, tokens e link do trace.
- Langfuse v3 self-hosted com org, projeto e chaves criados no primeiro start; LangSmith como alternativa.
- Logs em JSON com PII mascarada.

### Evaluation
- 28 casos, métricas determinísticas + LLM como juiz, comparação com baseline e falha em regressão.

### Infra e qualidade
- Docker Compose com perfis (`observabilidade`, `offline`, `app`), Makefile, CI (ruff, mypy --strict, pytest com cobertura ≥ 80%, integração com Postgres, gitleaks, lychee) e workflow manual de evals.
