# 08 · Evaluation

> Slides: **Avaliação assíncrona**, **Avaliando o seu agente**, **O ciclo que fecha**
> Código: [`evals/`](../evals/) · prompt do juiz em [`prompts/juiz.md`](../src/agente/prompts/juiz.md)

## Por que avaliar

Mudar um prompt, trocar de modelo ou ajustar o RAG pode melhorar um caso e piorar outros cinco, sem ninguém perceber. Teste unitário não pega isso, porque o LLM é fake nos testes. Evaluation é o **teste de regressão do comportamento**: roda o agente de verdade sobre um conjunto fixo de casos e compara com a versão anterior.

## As peças

### 1. Dataset: [`evals/dataset.jsonl`](../evals/dataset.jsonl)

28 casos, um por linha, cobrindo todas as intenções, guardrails, perguntas fora da base e conversas de mais de um turno:

```json
{"id": "cotacao-suv-bh",
 "entrada": "Quanto fica um SUV por 10 dias em BH?",          // ou uma lista de turnos
 "intencao_esperada": "cotacao",
 "ferramenta_esperada": "cotar_aluguel",                      // "nenhuma" = não pode chamar; null = tanto faz
 "fonte_esperada": null,                                      // arquivo que deve ser citado
 "criterios": ["informa o total de R$ 2.069,10", "menciona o desconto de 10%"],
 "referencia": "SUV em BH por 10 dias: ... total R$ 2.069,10."}
```

Casos de guardrail têm também `"guardrail_esperado": "entrada:prompt_injection"`. **Todos os dados são fictícios.**

### 2. Métricas determinísticas (sem LLM)

Baratas, exatas e 100% reproduzíveis:

| Métrica | Pergunta |
|---|---|
| `intencao` | O classificador acertou? |
| `ferramenta` | Chamou a ferramenta esperada (ou nenhuma, quando era para não chamar)? |
| `fonte_citada` | O nome do arquivo esperado aparece na resposta? |
| `guardrail` | O guardrail esperado disparou? |
| `latencia_media_ms`, `tokens_por_caso` | Informativas: não reprovam o comando |

### 3. LLM como juiz: [`evals/juiz.py`](../evals/juiz.py)

Métrica determinística não diz se a resposta foi **boa**. O juiz recebe a conversa, os dados reais das ferramentas, os critérios e a referência, e devolve, com saída estruturada, **nota de 1 a 5 e justificativa** para:

- `resolveu` · `tom` · `sem_alucinacao` · `seguiu_politica`

As notas são normalizadas para 0 a 1 (`(nota - 1) / 4`), na mesma escala das outras métricas.

### 4. Runner: [`evals/rodar_evals.py`](../evals/rodar_evals.py)

```bash
make evals            # roda tudo e compara com o baseline
make evals-baseline   # promove o último resultado a baseline
```

- Roda o **mesmo grafo** do Streamlit, com `canal="eval"`, uma thread nova por caso e 4 casos em paralelo.
- Imprime a estimativa de tokens (e de custo, se `EVAL_PRECO_USD_POR_MILHAO_TOKENS` estiver definido) **antes** de começar.
- Grava `evals/resultados/AAAA-MM-DD_HHMM.json` (tudo, caso a caso, com as justificativas do juiz) e um `.md` com o resumo.
- Compara com [`baseline.json`](../evals/resultados/baseline.json) e **sai com código 1** se alguma métrica de qualidade cair mais que `EVAL_TOLERANCIA` (padrão 0,05).
- Com Langfuse ligado, as notas do juiz viram **scores no trace** de cada caso: evaluation e observabilidade no mesmo lugar.
- `EVAL_MAX_CASOS=5` (ou `--max-casos 5`) para testar barato.

Saída real (gpt-5.6-luna):

```
| métrica         | atual | baseline | Δ      |    |
|-----------------|-------|----------|--------|----|
| intencao        | 1.0   | 1.0      | +0.000 | ✅ |
| ferramenta      | 1.0   | 1.0      | +0.000 | ✅ |
| fonte_citada    | 1.0   | 1.0      | +0.000 | ✅ |
| guardrail       | 1.0   | 1.0      | +0.000 | ✅ |
| resolveu        | 1.0   | 1.0      | +0.000 | ✅ |
| sem_alucinacao  | 0.991 | 0.991    | +0.000 | ✅ |
...
```

## O ciclo que fecha: exemplo real

Apagamos de propósito "cite a fonte" do `sistema.md` e rodamos `make evals`:

```
| fonte_citada    | 0.0   | 1.0 | -1.000 | ❌ caiu |
| seguiu_politica | 0.902 | 1.0 | -0.098 | ❌ caiu |
FALHOU: fonte_citada, seguiu_politica caiu(ram) mais que 5%.
```

A métrica determinística (`fonte_citada`) e o juiz (`seguiu_politica`) pegaram a regressão, e o comando falhou. É isso que permite mudar prompt com confiança.

## Offline × online

| | Offline (este repositório) | Online / assíncrona (produção) |
|---|---|---|
| **Sobre o quê** | Dataset fixo e curado | Conversas reais, depois que aconteceram |
| **Quando** | Antes de publicar uma mudança | Continuamente, fora do caminho do usuário |
| **Para quê** | Não regredir | Descobrir problemas que o dataset não previa |
| **Como** | `make evals`, workflow manual no GitHub | Amostra de traces do Langfuse + juiz, alertas |

O ciclo: conversas reais revelam falhas → viram casos novos no dataset (anonimizados) → o offline impede que voltem.

## Reprodutibilidade

- **Temperatura 0 no juiz** quando o modelo aceita (`JUIZ_TEMPERATURA=0`). A família gpt-5 só aceita o padrão; nesse caso deixe vazio e aceite alguma variação, que a tolerância de 5% absorve.
- **Seed:** a Responses API da OpenAI não expõe seed. Providers que aceitam podem receber via kwargs em `llm.py`.
- Métricas determinísticas não variam.
- Mesmo prompt (o hash vai em `versao_prompt`) e mesmo dataset.

## Limites do LLM como juiz

- **Ele também erra**, e tende a ser generoso com respostas bem escritas. Por isso recebe a **referência** e os **dados das ferramentas**, em vez de julgar "de cabeça".
- **Viés de modelo:** um juiz da mesma família do agente pode favorecê-lo. Considere `LLM_MODELO_JUIZ` diferente.
- **Use para comparar versões, não como verdade absoluta.** Leia as justificativas dos casos com nota baixa (estão no `.json` do resultado).
- Calibre de vez em quando: pegue 10 casos, dê a sua nota e compare com a do juiz.

## Como aumentar o dataset com conversas reais

1. No Langfuse, filtre traces com `handoff`, `guardrail:*` ou score baixo.
2. **Anonimize**: troque nomes, códigos e valores reais por fictícios. A máscara de PII ajuda, mas revise à mão.
3. Escreva `criterios` e `referencia` e adicione ao `dataset.jsonl`.
4. `make evals` e, se estiver tudo certo, `make evals-baseline`.

## Custo

Uma execução completa (28 casos, 30 turnos) com gpt-5.6-luna usou **~62 mil tokens do agente** e **~27 mil do juiz**, em cerca de 1 minuto (4 casos em paralelo). Veja [Custos no README](../README.md#custos).
