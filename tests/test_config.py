import pytest
from langchain_core.messages import HumanMessage

from agente import llm, prompts
from agente.config import ErroConfiguracao, obter_config
from agente.nodes.classificador import classificar


def test_sem_chave_falha_com_mensagem_clara(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LLM_PROVIDER", "openai")
    with pytest.raises(ErroConfiguracao, match=r"Variável LLM_API_KEY não configurada\. Copie"):
        obter_config()


def test_valor_invalido_aponta_a_variavel(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MEMORIA_BACKEND", "redis")
    with pytest.raises(ErroConfiguracao, match="MEMORIA_BACKEND"):
        obter_config()


def test_variavel_vazia_vira_none(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LLM_TEMPERATURA", "")
    assert obter_config().llm_temperatura is None


def test_chave_do_provider_tambem_vale(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LLM_PROVIDER", "openai")
    monkeypatch.delenv("LLM_API_KEY")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-teste")
    assert obter_config().llm_api_key is not None


@pytest.mark.parametrize(
    ("provider", "classe"),
    [("openai", "ChatOpenAI"), ("anthropic", "ChatAnthropic"), ("ollama", "ChatOllama")],
)
def test_trocar_provider_nao_muda_codigo(
    monkeypatch: pytest.MonkeyPatch, provider: str, classe: str
) -> None:
    monkeypatch.setenv("LLM_PROVIDER", provider)
    monkeypatch.setenv("LLM_API_KEY", "chave-de-teste")
    monkeypatch.setenv("LLM_MODELO_FORTE", "modelo-x")
    monkeypatch.setenv("LLM_TEMPERATURA", "0")
    monkeypatch.setenv("LLM_REASONING_EFFORT", "low")
    modelo = llm.modelo_forte()  # só instancia, não chama a rede
    assert type(modelo).__name__ == classe


def test_openai_usa_responses_api(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LLM_PROVIDER", "openai")
    monkeypatch.setenv("LLM_API_KEY", "chave-de-teste")
    assert llm.modelo_rapido().use_responses_api is True  # type: ignore[attr-defined]


@pytest.mark.parametrize(
    ("provider", "classe"), [("openai", "OpenAIEmbeddings"), ("ollama", "OllamaEmbeddings")]
)
def test_embeddings_por_provider(
    monkeypatch: pytest.MonkeyPatch, provider: str, classe: str
) -> None:
    monkeypatch.setenv("EMBEDDINGS_PROVIDER", provider)
    monkeypatch.setenv("LLM_API_KEY", "chave-de-teste")
    assert type(llm.embeddings()).__name__ == classe


def test_provider_sem_embeddings(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("EMBEDDINGS_PROVIDER", "anthropic")
    with pytest.raises(ErroConfiguracao, match="EMBEDDINGS_PROVIDER"):
        llm.embeddings()


def test_modo_demo_responde_sem_rede() -> None:
    assert llm.modelo_forte().invoke("oi").text == llm.MENSAGEM_DEMO


def test_classificador_cai_em_outro_quando_falha() -> None:
    # No modo demo o modelo não devolve a estrutura esperada: o classificador não quebra.
    assert classificar({"messages": [HumanMessage("oi")]}) == "outro"


def test_versao_do_prompt_e_um_hash_curto() -> None:
    assert len(prompts.versao()) == 8
    assert prompts.versao() == prompts.versao()
    assert prompts.versao("sistema") != prompts.versao("juiz")
