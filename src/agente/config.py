"""Configuração central, lida de variáveis de ambiente (e do arquivo .env).

Toda configuração do projeto passa por aqui. Se algo obrigatório faltar, a aplicação
falha com uma mensagem clara em vez de um stack trace no meio de uma conversa.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import AliasChoices, Field, SecretStr, ValidationError
from pydantic_settings import BaseSettings, SettingsConfigDict

RAIZ_PROJETO = Path(__file__).resolve().parents[2]

# Providers que não precisam de chave de API.
PROVIDERS_SEM_CHAVE = {"ollama", "fake"}


class ErroConfiguracao(RuntimeError):
    """Configuração inválida ou incompleta. A mensagem é pensada para o usuário final."""


class Config(BaseSettings):
    # env_parse_none_str="": uma variável vazia (ex.: LLM_TEMPERATURA=) vira None.
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore", env_parse_none_str=""
    )

    # --- Modelos -----------------------------------------------------------------------
    llm_provider: str = "openai"  # openai | anthropic | google_genai | ollama | fake
    llm_api_key: SecretStr | None = Field(
        default=None,
        validation_alias=AliasChoices(
            "LLM_API_KEY", "OPENAI_API_KEY", "ANTHROPIC_API_KEY", "GOOGLE_API_KEY"
        ),
    )
    llm_modelo_rapido: str = "gpt-5.6-luna"
    llm_modelo_forte: str = "gpt-5.6-luna"
    # Vazio = não envia (modelos de raciocínio, como a família gpt-5, só aceitam o padrão).
    llm_temperatura: float | None = None
    llm_reasoning_effort: str | None = None  # só OpenAI: none | low | medium | high
    ollama_base_url: str = "http://localhost:11434"

    embeddings_provider: str | None = None  # vazio = mesmo do LLM
    embeddings_modelo: str = "text-embedding-3-small"
    embeddings_api_key: SecretStr | None = None  # vazio = mesma do LLM

    # --- Comportamento do agente ---------------------------------------------------------
    usar_classificador: bool = True
    guardrail_injecao_llm: bool = True
    filtrar_ferramentas_por_intencao: bool = False
    max_tentativas_ferramenta: int = 3
    janela_mensagens: int = 20
    max_caracteres_entrada: int = 1000
    max_caracteres_saida: int = 900

    # --- Memória e RAG ---------------------------------------------------------------------
    memoria_backend: Literal["postgres", "sqlite"] = "postgres"
    rag_backend: Literal["pgvector", "chroma"] = "pgvector"
    database_url: str = "postgresql://agente:agente@localhost:5432/agente"
    sqlite_path: Path = RAIZ_PROJETO / ".data" / "memoria.sqlite"
    chroma_dir: Path = RAIZ_PROJETO / ".data" / "chroma"
    rag_colecao: str = "faq"
    rag_k: int = 4
    rag_score_minimo: float = 0.3
    dados_dir: Path = RAIZ_PROJETO / "data"

    # --- Observabilidade ---------------------------------------------------------------------
    langfuse_public_key: str | None = None
    langfuse_secret_key: SecretStr | None = None
    langfuse_host: str = "http://localhost:3000"
    langfuse_url_publica: str | None = None  # quando o app roda em container
    langsmith_tracing: bool = False
    langsmith_api_key: SecretStr | None = None
    langsmith_project: str = "uaidev"
    log_level: str = "INFO"

    # --- Evaluation ------------------------------------------------------------------------
    llm_modelo_juiz: str | None = None  # vazio = modelo forte
    juiz_temperatura: float | None = 0.0
    eval_tolerancia: float = 0.05
    eval_max_casos: int | None = None
    eval_preco_usd_por_milhao_tokens: float | None = None  # só para a estimativa de custo

    @property
    def langfuse_ligado(self) -> bool:
        return bool(self.langfuse_public_key and self.langfuse_secret_key)

    def validar(self) -> Config:
        if self.llm_provider not in PROVIDERS_SEM_CHAVE and self.llm_api_key is None:
            raise ErroConfiguracao(
                "Variável LLM_API_KEY não configurada. Copie .env.example para .env."
            )
        return self


@lru_cache
def obter_config() -> Config:
    try:
        return Config().validar()
    except ValidationError as erro:
        campos = ", ".join(str(e["loc"][0]).upper() for e in erro.errors())
        raise ErroConfiguracao(f"Valor inválido em: {campos}. Confira o seu .env.") from None
