"""
node.py — No stub do FAQ.

Placeholder ate a implementacao real (RAG ou knowledge base).
Retorna mensagem fixa informando que o FAQ esta em construcao.
"""
from __future__ import annotations

from langchain_core.runnables import RunnableConfig

from app.core.state import GlobalState


def faq_node(state: GlobalState, config: RunnableConfig) -> dict:
    return {
        "specialists_outputs": {
            "faq": "Nosso FAQ ainda esta em construcao. Em breve poderemos responder suas duvidas sobre a CT Smash!"
        }
    }
