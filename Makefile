# Atalhos do projeto. `make help` lista tudo.
COMPOSE := docker compose
UV := uv run

.DEFAULT_GOAL := help
.PHONY: help setup up up-obs up-all down logs db-reset db-shell ollama-pull ingest run \
        test test-integracao lint format typecheck check evals evals-baseline qrcode clean

help: ## Lista os comandos
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-16s\033[0m %s\n", $$1, $$2}'

# --- Ambiente ----------------------------------------------------------------------------
setup: ## Instala dependências, cria o .env e os hooks do pre-commit
	uv sync
	@test -f .env || (cp .env.example .env && echo ">> .env criado. Preencha LLM_API_KEY.")
	-$(UV) pre-commit install

# --- Infraestrutura local (Docker Compose) --------------------------------------------------
up: ## Sobe o Postgres + pgvector (memória e RAG)
	$(COMPOSE) up -d --wait postgres

up-obs: ## Sobe o Postgres + Langfuse em http://localhost:3000
	$(COMPOSE) --profile observabilidade up -d --wait

up-all: ## Sobe tudo: Postgres, Langfuse, Ollama e o app em container
	$(COMPOSE) --profile all up -d --build --wait

down: ## Para os containers (os dados ficam nos volumes)
	$(COMPOSE) --profile all down

logs: ## Acompanha os logs dos containers
	$(COMPOSE) --profile all logs -f --tail=100

db-reset: ## Apaga os volumes e recria o ambiente do zero
	$(COMPOSE) --profile all down -v
	$(MAKE) up

db-shell: ## Abre o psql no banco do agente
	$(COMPOSE) exec postgres sh -c 'psql -U "$$POSTGRES_USER" -d "$$POSTGRES_DB"'

ollama-pull: ## Baixa os modelos do modo offline (perfil offline precisa estar de pé)
	$(COMPOSE) exec ollama ollama pull $${OLLAMA_MODELO:-qwen2.5:3b}
	$(COMPOSE) exec ollama ollama pull nomic-embed-text

# --- Agente ----------------------------------------------------------------------------------
ingest: ## Ingere data/faq no vector store (idempotente)
	$(UV) python -m agente.rag.ingestao

run: ## Abre o Streamlit em http://localhost:8501
	$(UV) streamlit run app/streamlit_app.py --server.headless=true

# --- Qualidade ----------------------------------------------------------------------------
test: ## Testes unitários (sem rede, LLM fake) com cobertura
	$(UV) pytest

test-integracao: ## Testes de memória e RAG no Postgres do compose (make up antes)
	$(UV) pytest -m integracao --no-cov

lint: ## ruff check + format --check
	$(UV) ruff check .
	$(UV) ruff format --check .

format: ## Formata o código
	$(UV) ruff check --fix .
	$(UV) ruff format .

typecheck: ## mypy --strict em src/
	$(UV) mypy

check: lint typecheck test ## Tudo o que o CI roda

# --- Evaluation --------------------------------------------------------------------------
evals: ## Roda os evals e compara com o baseline (usa a API do LLM: tem custo)
	$(UV) python -m evals.rodar_evals

evals-baseline: ## Promove o último resultado a baseline
	$(UV) python -m evals.rodar_evals --promover-baseline

# --- Outros --------------------------------------------------------------------------------
qrcode: ## Gera docs/qrcode.png com o link do repositório: make qrcode URL=https://...
	uvx --from "qrcode[pil]" qr "$(URL)" > docs/qrcode.png && echo "docs/qrcode.png gerado"

clean: ## Remove caches e dados locais (SQLite/Chroma)
	rm -rf .data .pytest_cache .mypy_cache .ruff_cache .coverage htmlcov
