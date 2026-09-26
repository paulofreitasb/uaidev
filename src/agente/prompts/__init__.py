"""Prompts ficam em arquivos .md, versionados junto com o código.

Assim dá para ler e revisar o prompt no GitHub, ver o diff em um PR e rastrear
qual versão respondeu cada mensagem (o hash vai para o trace como `versao_prompt`).
"""

from __future__ import annotations

import hashlib
from pathlib import Path

PASTA = Path(__file__).parent


def carregar(nome: str) -> str:
    # Lido a cada chamada, de propósito: editar o .md muda o comportamento na hora,
    # sem reiniciar o Streamlit.
    return (PASTA / f"{nome}.md").read_text(encoding="utf-8")


def versao(nome: str = "sistema") -> str:
    return hashlib.sha256(carregar(nome).encode()).hexdigest()[:8]
