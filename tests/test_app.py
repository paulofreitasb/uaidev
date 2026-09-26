"""O Streamlit de ponta a ponta, sem navegador e com o modo demo (LLM fake)."""

from pathlib import Path

from streamlit.testing.v1 import AppTest

from agente.llm import MENSAGEM_DEMO

APP = str(Path(__file__).parents[1] / "app" / "streamlit_app.py")


def test_chat_responde_e_mostra_painel() -> None:
    app = AppTest.from_file(APP, default_timeout=30).run()
    assert not app.exception
    app.chat_input[0].set_value("Olá").run()
    textos = [m.markdown[0].value for m in app.chat_message]
    assert textos == ["Olá", MENSAGEM_DEMO]
    assert any("Intenção" in md.value for md in app.markdown)


def test_nova_conversa_troca_a_thread() -> None:
    app = AppTest.from_file(APP, default_timeout=30).run()
    thread = app.query_params["thread"]
    app.chat_input[0].set_value("Olá").run()
    app.button[0].click().run()
    assert app.query_params["thread"] != thread
    assert len(app.chat_message) == 0


def test_sem_chave_mostra_erro_amigavel(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setenv("LLM_PROVIDER", "openai")
    app = AppTest.from_file(APP, default_timeout=30).run()
    assert "LLM_API_KEY não configurada" in app.error[0].value
