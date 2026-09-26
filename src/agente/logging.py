"""Logs estruturados em JSON, com PII mascarada.

JSON porque log é para ser consultado (filtrar por `thread`, `intencao`...), não só lido.
A máscara roda no formatter: nada que passe pelo log sai com CPF, cartão ou e-mail.
"""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from typing import Any

from agente.nodes.guardrails import mascarar_pii

_CAMPOS_PADRAO = set(vars(logging.makeLogRecord({}))) | {"message", "asctime"}


class FormatterJson(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        dados: dict[str, Any] = {
            "ts": datetime.fromtimestamp(record.created, UTC).isoformat(timespec="milliseconds"),
            "nivel": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        dados |= {k: v for k, v in vars(record).items() if k not in _CAMPOS_PADRAO}
        if record.exc_info:
            dados["erro"] = self.formatException(record.exc_info)
        return mascarar_pii(json.dumps(dados, ensure_ascii=False, default=str))


def configurar_logging(nivel: str = "INFO") -> None:
    raiz = logging.getLogger()
    if any(isinstance(h.formatter, FormatterJson) for h in raiz.handlers):
        return  # já configurado (o Streamlit reexecuta o script a cada interação)
    handler = logging.StreamHandler()
    handler.setFormatter(FormatterJson())
    raiz.addHandler(handler)
    raiz.setLevel(nivel)
    for ruidoso in ("httpx", "httpx2", "httpcore", "openai", "urllib3"):
        logging.getLogger(ruidoso).setLevel(logging.WARNING)
