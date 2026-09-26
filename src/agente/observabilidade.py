"""Observabilidade: Langfuse (padrão, local no compose) ou LangSmith, ligados por env.

Sem nenhum dos dois configurado, nada acontece e a aplicação roda normalmente.

Cada mensagem vira um trace com a árvore de nós do grafo e as chamadas de modelo e de
ferramenta. Os metadados (intenção, versão do prompt, handoff, guardrail) viram tags,
o que permite filtrar os traces no Langfuse.
"""

from __future__ import annotations

import hashlib
import logging
import os
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Any

from langchain_core.callbacks import BaseCallbackHandler

from agente import prompts
from agente.config import obter_config

log = logging.getLogger(__name__)


@dataclass
class Rastreio:
    """O que o chamador precisa para amarrar uma execução ao trace."""

    callbacks: list[BaseCallbackHandler] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    tags: list[str] = field(default_factory=list)
    trace_id: str | None = None
    trace_url: str | None = None
    # Preenchido pelo chamador depois da execução; vira tags/metadados do trace.
    resultado: dict[str, Any] = field(default_factory=dict)


def hash_thread(thread_id: str) -> str:
    # O id da sessão vai para o trace como hash: dá para agrupar sem expor o id real.
    return hashlib.sha256(thread_id.encode()).hexdigest()[:16]


@lru_cache
def _cliente_langfuse() -> Any:
    from langfuse import Langfuse

    config = obter_config()
    assert config.langfuse_secret_key is not None
    return Langfuse(
        public_key=config.langfuse_public_key,
        secret_key=config.langfuse_secret_key.get_secret_value(),
        host=config.langfuse_host,
    )


@lru_cache
def _ligar_langsmith() -> None:
    # O LangChain lê estas variáveis do ambiente do processo (não do .env) e envia os
    # traces sozinho, sem callback explícito.
    config = obter_config()
    os.environ["LANGSMITH_TRACING"] = "true"
    os.environ["LANGSMITH_PROJECT"] = config.langsmith_project
    if config.langsmith_api_key:
        os.environ["LANGSMITH_API_KEY"] = config.langsmith_api_key.get_secret_value()


@lru_cache
def _avisar_desligada() -> None:
    log.info("observabilidade desligada")  # lru_cache = só uma vez por processo


def _tags_resultado(resultado: dict[str, Any]) -> list[str]:
    tags = [f"intencao:{resultado.get('intencao') or 'nenhuma'}"]
    if resultado.get("handoff"):
        tags.append("handoff")
    if resultado.get("guardrail_disparado"):
        tags.append(f"guardrail:{resultado['guardrail_disparado']}")
    return tags


@contextmanager
def rastrear(thread_id: str, canal: str) -> Iterator[Rastreio]:
    config = obter_config()
    versao = prompts.versao()
    base = Rastreio(
        metadata={"thread_id": hash_thread(thread_id), "canal": canal, "versao_prompt": versao},
        tags=[f"canal:{canal}", f"prompt:{versao}"],
    )

    if config.langfuse_ligado:
        with _rastrear_langfuse(base, thread_id) as rastreio:
            yield rastreio
        return

    if config.langsmith_tracing:
        _ligar_langsmith()  # metadados e tags vão pela config de execução do grafo
    else:
        _avisar_desligada()
    yield base


def _url_do_trace(cliente: Any, trace_id: str) -> str | None:
    # get_trace_url consulta a API do Langfuse (uma vez) para descobrir o projeto.
    # Langfuse fora do ar não pode derrubar a conversa: observabilidade é acessória.
    # (Os spans em si são enviados em background e simplesmente se perdem.)
    config = obter_config()
    try:
        url: str | None = cliente.get_trace_url(trace_id=trace_id)
    except Exception:
        _avisar_langfuse_indisponivel()
        return None
    if url and config.langfuse_url_publica:
        url = url.replace(config.langfuse_host, config.langfuse_url_publica)
    return url


@lru_cache
def _avisar_langfuse_indisponivel() -> None:
    log.warning("langfuse indisponível: seguindo sem link do trace (rodou `make up-obs`?)")


@contextmanager
def _rastrear_langfuse(rastreio: Rastreio, thread_id: str) -> Iterator[Rastreio]:
    from langfuse import propagate_attributes
    from langfuse.langchain import CallbackHandler

    cliente = _cliente_langfuse()
    rastreio.trace_id = cliente.create_trace_id()
    rastreio.trace_url = _url_do_trace(cliente, rastreio.trace_id)

    with (
        cliente.start_as_current_observation(
            as_type="span", name="responder", trace_context={"trace_id": rastreio.trace_id}
        ) as span,
        propagate_attributes(
            session_id=hash_thread(thread_id),
            trace_name="agente",
            version=rastreio.metadata["versao_prompt"],
            tags=rastreio.tags,
            metadata={k: str(v) for k, v in rastreio.metadata.items()},
        ),
    ):
        rastreio.callbacks = [CallbackHandler()]
        yield rastreio
        # Intenção, handoff e guardrail só são conhecidos depois da execução.
        resultado = rastreio.resultado
        with propagate_attributes(
            tags=rastreio.tags + _tags_resultado(resultado),
            metadata={k: str(v) for k, v in resultado.items() if k not in ("entrada", "texto")},
        ):
            span.update(input=resultado.get("entrada"), output=resultado.get("texto"))


def registrar_score(trace_id: str, nome: str, valor: float, comentario: str | None = None) -> None:
    """Envia uma nota (ex.: do juiz dos evals) para o trace: liga evaluation e observabilidade."""
    if not obter_config().langfuse_ligado:
        return
    _cliente_langfuse().create_score(trace_id=trace_id, name=nome, value=valor, comment=comentario)


def flush() -> None:
    if obter_config().langfuse_ligado:
        _cliente_langfuse().flush()
