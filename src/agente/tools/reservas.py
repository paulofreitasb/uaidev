"""Ferramenta de consulta de reservas, sobre uma API mock (um JSON em data/)."""

from __future__ import annotations

import json
import re
from functools import lru_cache
from typing import Any

from langchain_core.tools import tool

from agente.config import obter_config

FORMATO_CODIGO = re.compile(r"^[A-Z]{3}\d{4}$")


@lru_cache
def _reservas() -> dict[str, dict[str, Any]]:
    caminho = obter_config().dados_dir / "reservas_mock.json"
    dados: dict[str, dict[str, Any]] = json.loads(caminho.read_text(encoding="utf-8"))["reservas"]
    return dados


@tool
def consultar_reserva(codigo: str) -> str:
    """Consulta o status e os detalhes de uma reserva da Locadora Exemplo.

    Use quando o cliente perguntar sobre uma reserva existente. O código tem
    3 letras e 4 números, por exemplo ABC1234.

    Args:
        codigo: código da reserva informado pelo cliente.
    """
    codigo = re.sub(r"[\s-]", "", codigo).upper()
    if not FORMATO_CODIGO.match(codigo):
        # Erro amigável, escrito para o modelo repassar ao cliente.
        return (
            f"Código '{codigo}' inválido. O código da reserva tem 3 letras seguidas de "
            "4 números, por exemplo ABC1234. Peça ao cliente para conferir."
        )
    reserva = _reservas().get(codigo)
    if reserva is None:
        return f"Reserva {codigo} não encontrada. Peça ao cliente para conferir o código."
    retirada, devolucao = reserva["retirada"], reserva["devolucao"]
    return (
        f"Reserva {codigo}: status {reserva['status']}. Categoria {reserva['categoria']}. "
        f"Retirada em {retirada['data']} na loja {retirada['loja']} ({retirada['cidade']}). "
        f"Devolução em {devolucao['data']} na loja {devolucao['loja']} ({devolucao['cidade']})."
    )
