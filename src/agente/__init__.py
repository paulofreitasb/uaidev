"""Agente conversacional da Locadora Exemplo.

A única função que um canal precisa conhecer é `responder()`.
"""

from agente.servico import ChamadaFerramenta, Resposta, estado_salvo, historico, responder

__all__ = ["ChamadaFerramenta", "Resposta", "estado_salvo", "historico", "responder"]
