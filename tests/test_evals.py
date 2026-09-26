"""O runner de evals também é código: testamos a comparação com o baseline sem LLM real."""

import pytest

from evals import juiz, rodar_evals
from evals.rodar_evals import agregar, avaliar_caso, carregar_casos, comparar
from tests.conftest import Modelos, chamada, intencao


def test_dataset_valido_e_sem_dados_reais() -> None:
    casos = carregar_casos(None)
    assert 20 <= len(casos) <= 30
    assert len({c["id"] for c in casos}) == len(casos)
    intencoes = {c["intencao_esperada"] for c in casos}
    assert {"faq", "reserva", "cotacao", "humano", "outro"} <= intencoes
    for caso in casos:
        assert caso["criterios"] and caso["referencia"]


def test_regressao_acima_da_tolerancia_reprova() -> None:
    _, regressoes = comparar(
        {"fonte_citada": 0.5, "tom": 0.97}, {"fonte_citada": 1.0, "tom": 1.0}, 0.05
    )
    assert regressoes == ["fonte_citada"]  # tom caiu 0.03: dentro da tolerância


def test_latencia_nao_reprova() -> None:
    _, regressoes = comparar({"latencia_media_ms": 9000}, {"latencia_media_ms": 1000}, 0.05)
    assert regressoes == []


def test_sem_baseline_nao_reprova() -> None:
    linhas, regressoes = comparar({"intencao": 0.5}, None, 0.05)
    assert regressoes == []
    assert linhas[0][2] == "—"


def test_agregar_ignora_metricas_que_nao_se_aplicam() -> None:
    casos = [
        {"metricas": {"intencao": 1.0}, "latencia_ms": 100, "tokens": 10, "tokens_juiz": 5},
        {
            "metricas": {"intencao": 0.0, "fonte_citada": 1.0},
            "latencia_ms": 300,
            "tokens": 30,
            "tokens_juiz": 5,
        },
    ]
    resumo = agregar(casos)
    assert resumo["intencao"] == 0.5
    assert resumo["fonte_citada"] == 1.0
    assert resumo["latencia_media_ms"] == 200


def test_avalia_um_caso_de_ponta_a_ponta(monkeypatch: pytest.MonkeyPatch, modelos: Modelos) -> None:
    from agente.llm import modelo_fake

    nota = {"nota": 5, "justificativa": "ok"}
    juiz_fake = modelo_fake([chamada("Avaliacao", **{c: nota for c in juiz.CRITERIOS})])
    monkeypatch.setattr(juiz, "modelo_juiz", lambda: juiz_fake)
    modelos(
        rapido=[intencao("reserva")],
        forte=[chamada("consultar_reserva", codigo="ABC1234"), "Sua reserva está confirmada."],
    )
    caso = {
        "id": "x",
        "entrada": "status ABC1234",
        "intencao_esperada": "reserva",
        "ferramenta_esperada": "consultar_reserva",
        "criterios": ["c"],
        "referencia": "r",
    }
    resultado = avaliar_caso(caso, "teste")
    assert resultado["metricas"] == {
        "intencao": 1.0,
        "ferramenta": 1.0,
        "resolveu": 1.0,
        "tom": 1.0,
        "sem_alucinacao": 1.0,
        "seguiu_politica": 1.0,
    }


def test_promover_baseline_sem_resultados(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setattr(rodar_evals, "RESULTADOS", tmp_path)
    monkeypatch.setattr(rodar_evals, "BASELINE", tmp_path / "baseline.json")
    assert rodar_evals.promover_baseline() == 1
    (tmp_path / "2026-01-01_1000.json").write_text("{}")
    assert rodar_evals.promover_baseline() == 0
    assert (tmp_path / "baseline.json").exists()
