# ADR 0004 — Langfuse v3 (em vez do v2 previsto no plano)

**Status:** aceita · **Data:** 2026-09

## Contexto
O plano original previa `langfuse/langfuse:2`, um container só. Na implementação, o SDK Python do Langfuse 2.x importa `langchain.callbacks`, que **não existe mais no LangChain 1.x**. A integração falha no import.

## Decisão
Usar o **Langfuse v3 self-hosted** (`langfuse/langfuse:3` + `langfuse-worker:3` + ClickHouse + Redis + MinIO, tudo no perfil `observabilidade`) e o SDK atual (`langfuse>=3`).

## Por quê
- Mantém o repositório nas versões atuais do LangChain/LangGraph, o que importa para um material didático que vai ser clonado por meses.
- A criação automática de org, projeto, chaves e usuário (`LANGFUSE_INIT_*`) continua funcionando: ninguém precisa se cadastrar.
- Os containers extras só sobem com `make up-obs`; quem não quer observabilidade roda só `make up`.

## Alternativas consideradas
- **Fixar LangChain 0.3 + Langfuse v2:** um container a menos, mas o código ficaria preso a APIs legadas.
- **Só LangSmith:** exige conta. Continua disponível como alternativa (`LANGSMITH_TRACING=true`).

## Consequências
- `make up-obs` sobe 6 containers e usa ~2 GB de RAM; o primeiro start (com download das imagens) leva alguns minutos.
- Healthchecks e `depends_on: service_healthy` garantem a ordem de subida.
