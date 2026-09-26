-- Roda uma vez, na criação do volume. Idempotente: pode rodar de novo sem erro.

-- pgvector: busca por similaridade para o RAG.
CREATE EXTENSION IF NOT EXISTS vector;

-- Banco separado para o Langfuse, no mesmo servidor Postgres.
SELECT 'CREATE DATABASE langfuse'
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'langfuse')\gexec
