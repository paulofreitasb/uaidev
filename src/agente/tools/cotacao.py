"""Ferramenta de cotação: regra de negócio simples e determinística.

O cálculo fica em código, não no modelo. LLM é ótimo para entender o pedido,
mas conta de dinheiro precisa dar sempre o mesmo resultado.
"""

from __future__ import annotations

import unicodedata
from decimal import ROUND_HALF_UP, Decimal

from langchain_core.tools import tool

DIARIAS = {
    "economico": Decimal("119.90"),
    "compacto": Decimal("139.90"),
    "sedan": Decimal("179.90"),
    "suv": Decimal("229.90"),
    "premium": Decimal("349.90"),
}
DESCONTO_LONGO_PERIODO = Decimal("0.10")  # 10% a partir de 7 dias
DIAS_PARA_DESCONTO = 7
MAX_DIAS = 30

CIDADES = {
    "belo horizonte": "Belo Horizonte",
    "bh": "Belo Horizonte",
    "sao paulo": "São Paulo",
    "sp": "São Paulo",
    "rio de janeiro": "Rio de Janeiro",
    "rio": "Rio de Janeiro",
    "rj": "Rio de Janeiro",
    "curitiba": "Curitiba",
    "porto alegre": "Porto Alegre",
    "poa": "Porto Alegre",
    "salvador": "Salvador",
    "recife": "Recife",
    "brasilia": "Brasília",
}


def _normalizar(texto: str) -> str:
    sem_acento = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()
    return " ".join(sem_acento.lower().split())


def formatar_brl(valor: Decimal) -> str:
    """Decimal('1299.9') -> 'R$ 1.299,90'."""
    texto = f"{valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"R$ {texto}"


def calcular(categoria: str, dias: int) -> tuple[Decimal, Decimal, Decimal]:
    """Devolve (subtotal, desconto, total)."""
    subtotal = DIARIAS[categoria] * dias
    desconto = subtotal * DESCONTO_LONGO_PERIODO if dias >= DIAS_PARA_DESCONTO else Decimal(0)
    total = (subtotal - desconto).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return subtotal, desconto.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP), total


@tool
def cotar_aluguel(categoria: str, dias: int, cidade: str) -> str:
    """Calcula o valor de um aluguel na Locadora Exemplo.

    Use quando o cliente quiser saber quanto custa alugar um carro. Há 10% de
    desconto para aluguéis a partir de 7 dias.

    Args:
        categoria: economico, compacto, sedan, suv ou premium.
        dias: número de diárias (1 a 30).
        cidade: cidade da retirada (ex.: Belo Horizonte, BH, São Paulo, Rio de Janeiro).
    """
    chave_categoria = _normalizar(categoria)
    if chave_categoria not in DIARIAS:
        return f"Categoria '{categoria}' não existe. Opções: {', '.join(DIARIAS)}."
    if not 1 <= dias <= MAX_DIAS:
        return f"Número de dias inválido ({dias}). Cotamos de 1 a {MAX_DIAS} diárias."
    nome_cidade = CIDADES.get(_normalizar(cidade))
    if nome_cidade is None:
        atendidas = sorted(set(CIDADES.values()))
        return f"Não atendemos '{cidade}'. Cidades atendidas: {', '.join(atendidas)}."

    subtotal, desconto, total = calcular(chave_categoria, dias)
    linhas = [
        f"Cotação {chave_categoria} em {nome_cidade} por {dias} diária(s):",
        f"diária {formatar_brl(DIARIAS[chave_categoria])}, subtotal {formatar_brl(subtotal)}",
    ]
    if desconto:
        linhas.append(f"desconto de 10% (a partir de 7 dias): -{formatar_brl(desconto)}")
    linhas.append(f"total {formatar_brl(total)}.")
    return "; ".join(linhas)
