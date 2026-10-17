# Imagem LOCAL do app (perfil "app" do compose). Não é uma imagem de produção.
FROM python:3.14-slim

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy PYTHONUNBUFFERED=1

WORKDIR /app
COPY pyproject.toml uv.lock README.md ./
RUN uv sync --frozen --no-dev --no-install-project

COPY . .
RUN uv sync --frozen --no-dev

EXPOSE 8501
# A ingestão é idempotente: roda a cada start para a base estar sempre atualizada.
CMD ["sh", "-c", "uv run --no-sync python -m agente.rag.ingestao && uv run --no-sync streamlit run app/streamlit_app.py --server.address=0.0.0.0 --server.port=8501 --server.headless=true"]
