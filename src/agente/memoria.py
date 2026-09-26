"""Memória de curto prazo: o checkpointer salva o estado do grafo a cada passo.

Cada conversa tem um `thread_id`. Na mensagem seguinte da mesma thread, o LangGraph
carrega o estado salvo (incluindo o histórico) e continua de onde parou. Trocar o
`thread_id` é começar uma conversa nova.
"""

from __future__ import annotations

import sqlite3

from langgraph.checkpoint.base import BaseCheckpointSaver

from agente.config import obter_config


def obter_checkpointer() -> BaseCheckpointSaver[str]:
    config = obter_config()
    if config.memoria_backend == "sqlite":
        from langgraph.checkpoint.sqlite import SqliteSaver

        config.sqlite_path.parent.mkdir(parents=True, exist_ok=True)
        # check_same_thread=False: o Streamlit atende cada sessão em uma thread diferente.
        conexao = sqlite3.connect(config.sqlite_path, check_same_thread=False)
        return SqliteSaver(conexao)

    from langgraph.checkpoint.postgres import PostgresSaver
    from psycopg.rows import dict_row
    from psycopg_pool import ConnectionPool

    # Pool: o Streamlit pode atender várias sessões ao mesmo tempo.
    pool = ConnectionPool(
        config.database_url,
        max_size=5,
        kwargs={"autocommit": True, "prepare_threshold": 0, "row_factory": dict_row},
        open=True,
    )
    saver = PostgresSaver(pool)  # type: ignore[arg-type]
    saver.setup()  # cria as tabelas na primeira vez; nas próximas não faz nada
    return saver
