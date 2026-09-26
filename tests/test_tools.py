from decimal import Decimal

import pytest

from agente.tools import TOOLS, ferramentas_para
from agente.tools.cotacao import cotar_aluguel, formatar_brl
from agente.tools.handoff import transferir_para_humano
from agente.tools.reservas import consultar_reserva


class TestConsultarReserva:
    def test_sucesso(self) -> None:
        retorno = consultar_reserva.invoke({"codigo": "ABC1234"})
        assert "status confirmada" in retorno
        assert "Aeroporto de Confins" in retorno

    def test_normaliza_minusculas_e_espacos(self) -> None:
        assert "em andamento" in consultar_reserva.invoke({"codigo": " xyz-9876 "})

    def test_nao_encontrada(self) -> None:
        assert "não encontrada" in consultar_reserva.invoke({"codigo": "ZZZ0000"})

    @pytest.mark.parametrize("codigo", ["AB12", "1234ABC", "ABCD123", ""])
    def test_formato_invalido(self, codigo: str) -> None:
        retorno = consultar_reserva.invoke({"codigo": codigo})
        assert "inválido" in retorno
        assert "ABC1234" in retorno  # mostra o formato certo


class TestCotarAluguel:
    def test_suv_10_dias_bh_com_desconto(self) -> None:
        retorno = cotar_aluguel.invoke({"categoria": "SUV", "dias": 10, "cidade": "BH"})
        assert "Belo Horizonte" in retorno
        assert "subtotal R$ 2.299,00" in retorno
        assert "-R$ 229,90" in retorno
        assert "total R$ 2.069,10" in retorno

    def test_sem_desconto_abaixo_de_7_dias(self) -> None:
        retorno = cotar_aluguel.invoke({"categoria": "econômico", "dias": 3, "cidade": "São Paulo"})
        assert "desconto" not in retorno
        assert "total R$ 359,70" in retorno

    def test_desconto_comeca_em_7_dias(self) -> None:
        retorno = cotar_aluguel.invoke({"categoria": "compacto", "dias": 7, "cidade": "rio"})
        assert "desconto" in retorno

    def test_categoria_invalida(self) -> None:
        assert "não existe" in cotar_aluguel.invoke({"categoria": "van", "dias": 2, "cidade": "BH"})

    @pytest.mark.parametrize("dias", [0, 31, -1])
    def test_dias_invalidos(self, dias: int) -> None:
        retorno = cotar_aluguel.invoke({"categoria": "suv", "dias": dias, "cidade": "BH"})
        assert "inválido" in retorno

    def test_cidade_nao_atendida(self) -> None:
        retorno = cotar_aluguel.invoke({"categoria": "suv", "dias": 2, "cidade": "Manaus"})
        assert "Não atendemos" in retorno


@pytest.mark.parametrize(
    ("valor", "esperado"),
    [("1299.9", "R$ 1.299,90"), ("0.5", "R$ 0,50"), ("1234567.891", "R$ 1.234.567,89")],
)
def test_formatar_brl(valor: str, esperado: str) -> None:
    assert formatar_brl(Decimal(valor)) == esperado


def test_transferir_para_humano() -> None:
    assert "registrada" in transferir_para_humano.invoke({"motivo": "cliente insatisfeito"})


def test_docstrings_existem_porque_o_modelo_le() -> None:
    for ferramenta in TOOLS:
        assert len(ferramenta.description) > 40, ferramenta.name


def test_filtro_por_intencao() -> None:
    assert ferramentas_para("reserva", filtrar=False) == TOOLS
    nomes = {f.name for f in ferramentas_para("reserva", filtrar=True)}
    assert nomes == {"consultar_reserva", "transferir_para_humano"}
    assert ferramentas_para("outro", filtrar=True) == TOOLS
    assert ferramentas_para(None, filtrar=True) == TOOLS
