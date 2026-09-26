"""Roda os evals: o mesmo grafo do Streamlit, com canal="eval", fora do caminho do usuário.

    make evals            # roda, grava resultados/AAAA-MM-DD_HHMM.json + .md e compara
    make evals-baseline   # promove o último resultado a baseline.json

Sai com código 1 se alguma métrica de qualidade cair mais que EVAL_TOLERANCIA em
relação ao baseline. É isso que transforma "achei que melhorou" em um teste.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from statistics import mean
from typing import Any

from agente import observabilidade, prompts, responder
from agente.config import ErroConfiguracao, obter_config
from agente.logging import configurar_logging
from evals.juiz import CRITERIOS, julgar

PASTA = Path(__file__).parent
DATASET = PASTA / "dataset.jsonl"
RESULTADOS = PASTA / "resultados"
BASELINE = RESULTADOS / "baseline.json"

# Médias medidas com gpt-5.6-luna (agente + classificador + guardrail; juiz à parte).
TOKENS_POR_TURNO = 2_000
TOKENS_POR_JULGAMENTO = 1_000
PARALELISMO = 4

# Métricas que o comando protege (maior = melhor). Latência e tokens são informativos.
METRICAS_QUALIDADE = (
    "intencao",
    "ferramenta",
    "fonte_citada",
    "guardrail",
    *CRITERIOS,
)


def carregar_casos(limite: int | None) -> list[dict[str, Any]]:
    linhas = DATASET.read_text(encoding="utf-8").splitlines()
    casos = [json.loads(linha) for linha in linhas if linha.strip()]
    return casos[:limite] if limite else casos


def turnos(caso: dict[str, Any]) -> list[str]:
    entrada = caso["entrada"]
    return entrada if isinstance(entrada, list) else [entrada]


def avaliar_caso(caso: dict[str, Any], execucao: str) -> dict[str, Any]:
    thread_id = f"eval-{execucao}-{caso['id']}"
    conversa, tokens, latencia = [], 0, 0
    for mensagem in turnos(caso):
        resposta = responder(thread_id, mensagem, canal="eval")
        conversa.append((mensagem, resposta.texto))
        tokens += resposta.tokens
        latencia += resposta.latencia_ms

    ferramentas = [asdict(f) for f in resposta.ferramentas]
    nomes = [f["nome"] for f in ferramentas]
    metricas: dict[str, float] = {}

    # --- Métricas determinísticas (sem LLM): baratas, exatas e reproduzíveis ------------
    if caso.get("intencao_esperada"):
        metricas["intencao"] = float(resposta.intencao == caso["intencao_esperada"])
    esperada = caso.get("ferramenta_esperada")
    if esperada == "nenhuma":
        metricas["ferramenta"] = float(not nomes)
    elif esperada:
        metricas["ferramenta"] = float(esperada in nomes)
    if caso.get("fonte_esperada"):
        metricas["fonte_citada"] = float(caso["fonte_esperada"] in resposta.texto)
    if caso.get("guardrail_esperado"):
        metricas["guardrail"] = float(resposta.guardrail_disparado == caso["guardrail_esperado"])

    # --- LLM como juiz -----------------------------------------------------------------
    avaliacao, tokens_juiz = julgar(caso, conversa, ferramentas)
    for criterio in CRITERIOS:
        nota = getattr(avaliacao, criterio)
        metricas[criterio] = (nota.nota - 1) / 4  # 1..5 → 0..1, na mesma escala das outras
        if resposta.trace_id:  # a nota vira score no trace: evaluation + observabilidade
            observabilidade.registrar_score(
                resposta.trace_id, criterio, nota.nota, nota.justificativa
            )

    return {
        "id": caso["id"],
        "conversa": conversa,
        "intencao": resposta.intencao,
        "ferramentas": nomes,
        "guardrail": resposta.guardrail_disparado,
        "handoff": resposta.handoff,
        "metricas": metricas,
        "juiz": avaliacao.model_dump(),
        "latencia_ms": latencia,
        "tokens": tokens,
        "tokens_juiz": tokens_juiz,
        "trace_url": resposta.trace_url,
    }


def agregar(casos: list[dict[str, Any]]) -> dict[str, float]:
    resumo: dict[str, float] = {}
    for nome in METRICAS_QUALIDADE:
        valores = [c["metricas"][nome] for c in casos if nome in c["metricas"]]
        if valores:
            resumo[nome] = round(mean(valores), 3)
    resumo["latencia_media_ms"] = round(mean(c["latencia_ms"] for c in casos))
    resumo["tokens_por_caso"] = round(mean(c["tokens"] for c in casos))
    resumo["tokens_total"] = sum(c["tokens"] for c in casos)
    resumo["tokens_juiz_total"] = sum(c["tokens_juiz"] for c in casos)
    return resumo


def comparar(
    atual: dict[str, float], baseline: dict[str, float] | None, tolerancia: float
) -> tuple[list[list[str]], list[str]]:
    linhas, regressoes = [], []
    for nome, valor in atual.items():
        anterior = baseline.get(nome) if baseline else None
        delta, status = "—", ""
        if anterior is not None:
            delta = (
                f"{valor - anterior:+.3f}" if isinstance(valor, float) else f"{valor - anterior:+}"
            )
            if nome in METRICAS_QUALIDADE:
                if valor < anterior - tolerancia:
                    status = "❌ caiu"
                    regressoes.append(nome)
                else:
                    status = "✅"
        linhas.append([nome, str(valor), "—" if anterior is None else str(anterior), delta, status])
    return linhas, regressoes


def tabela_markdown(linhas: list[list[str]]) -> str:
    cabecalho = ["métrica", "atual", "baseline", "Δ", ""]
    saida = ["| " + " | ".join(cabecalho) + " |", "|" + "---|" * len(cabecalho)]
    saida += ["| " + " | ".join(linha) + " |" for linha in linhas]
    return "\n".join(saida)


def resumo_markdown(
    resultado: dict[str, Any], linhas: list[list[str]], regressoes: list[str]
) -> str:
    falhas = [
        f"- `{c['id']}`: " + ", ".join(f"{k}={v:.2f}" for k, v in c["metricas"].items() if v < 1)
        for c in resultado["casos"]
        if any(v < 0.75 for v in c["metricas"].values())
    ]
    partes = [
        f"# Evals · {resultado['data']}",
        f"Prompt `{resultado['versao_prompt']}` · modelos `{resultado['modelos']}` · "
        f"{len(resultado['casos'])} casos",
        "",
        tabela_markdown(linhas),
        "",
        f"**Regressões:** {', '.join(regressoes)}" if regressoes else "**Sem regressões.**",
    ]
    if falhas:
        partes += ["", "## Casos com nota baixa", *falhas]
    return "\n".join(partes) + "\n"


def promover_baseline() -> int:
    candidatos = sorted(p for p in RESULTADOS.glob("*.json") if p.name != BASELINE.name)
    if not candidatos:
        print("Nenhum resultado para promover. Rode `make evals` antes.")
        return 1
    shutil.copy(candidatos[-1], BASELINE)
    print(f"{candidatos[-1].name} promovido a baseline.json")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--promover-baseline", action="store_true")
    parser.add_argument("--max-casos", type=int)
    args = parser.parse_args()
    if args.promover_baseline:
        return promover_baseline()

    try:
        config = obter_config()
    except ErroConfiguracao as erro:
        print(erro)
        return 1
    configurar_logging("WARNING")
    casos = carregar_casos(args.max_casos or config.eval_max_casos)
    total_turnos = sum(len(turnos(c)) for c in casos)
    estimativa = total_turnos * TOKENS_POR_TURNO + len(casos) * TOKENS_POR_JULGAMENTO
    aviso = f"{len(casos)} casos, {total_turnos} turnos, ~{estimativa:_} tokens estimados"
    if preco := config.eval_preco_usd_por_milhao_tokens:
        aviso += f" (≈ US$ {estimativa / 1_000_000 * preco:.2f})"
    print(aviso.replace("_", ".") + ".")

    execucao = uuid.uuid4().hex[:6]
    with ThreadPoolExecutor(max_workers=PARALELISMO) as pool:
        resultados_casos = list(pool.map(lambda c: avaliar_caso(c, execucao), casos))
    observabilidade.flush()

    agora = datetime.now()
    resultado = {
        "data": agora.isoformat(timespec="minutes"),
        "versao_prompt": prompts.versao(),
        "modelos": f"{config.llm_provider}:{config.llm_modelo_rapido}/{config.llm_modelo_forte}",
        "metricas": agregar(resultados_casos),
        "casos": resultados_casos,
    }
    baseline = (
        json.loads(BASELINE.read_text(encoding="utf-8"))["metricas"] if BASELINE.exists() else None
    )
    linhas, regressoes = comparar(resultado["metricas"], baseline, config.eval_tolerancia)
    resumo = resumo_markdown(resultado, linhas, regressoes)

    RESULTADOS.mkdir(exist_ok=True)
    arquivo = RESULTADOS / f"{agora:%Y-%m-%d_%H%M}.json"
    arquivo.write_text(json.dumps(resultado, ensure_ascii=False, indent=2), encoding="utf-8")
    arquivo.with_suffix(".md").write_text(resumo, encoding="utf-8")
    if resumo_github := os.getenv("GITHUB_STEP_SUMMARY"):
        with open(resumo_github, "a", encoding="utf-8") as saida:
            saida.write(resumo)

    print(resumo)
    print(f"Resultado salvo em {arquivo.relative_to(PASTA.parent)}")
    if baseline is None:
        print("Ainda não há baseline: rode `make evals-baseline` para promover este resultado.")
    if regressoes:
        print(f"FALHOU: {', '.join(regressoes)} caiu(ram) mais que {config.eval_tolerancia:.0%}.")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
