"""
workflow.py — Subgrafo LangGraph do agente de Aula Experimental (Trial)

Este subgrafo opera sobre o GlobalState, mas somente lê/escreve o campo:
  - state["trial"] (TrialState)

Estratégia:
- nós por etapa
- roteamento interno baseado em trial.stage
- cada nó escreve trial.output, e exporta para specialists_outputs["trial"]
"""

from __future__ import annotations

from langgraph.graph import StateGraph, END
from langchain_core.runnables import RunnableConfig

from app.core.state import GlobalState
from app.agents.aula_experimental.nodes import (
    ensure_trial_defaults,
    trial_collect_client_info,
    trial_ask_date,
    trial_awaiting_confirmation,
    trial_book,
    trial_router,
)


def trial_route(state: GlobalState) -> str:
    """
    Decide o próximo nó do subgrafo com base no stage atual.
    Retorna o nome do nó (ou "END").
    """
    trial = ensure_trial_defaults(state)
    stage = trial.get("stage", "collect_client_info")

    stage_to_node = {
        "collect_client_info": "trial_collect_client_info",
        "ask_date": "trial_ask_date",
        "awaiting_confirmation": "trial_awaiting_confirmation",
        "book": "trial_book",
        "booked": "END",
        "cancelled": "END",
    }

    return stage_to_node.get(stage, "trial_collect_client_info")


def after_confirm_route(state: GlobalState) -> str:
    stage = (state.get("trial") or {}).get("stage")
    if stage == "book":
        return "trial_book"
    return "END"


def build_trial_graph(config: RunnableConfig):
    """
    Factory única do subgrafo de Aula Experimental.

    Aceita apenas RunnableConfig (padrão LangGraph CLI/Studio).
    Cria o LLM internamente; persistência é feita via import direto em nodes.py.
    """
    g = StateGraph(GlobalState)

    g.add_node("trial_router", trial_router)
    g.add_node("trial_collect_client_info", trial_collect_client_info)
    g.add_node("trial_ask_date", trial_ask_date)
    g.add_node("trial_awaiting_confirmation", trial_awaiting_confirmation)
    g.add_node("trial_book", trial_book)

    g.set_entry_point("trial_router")

    g.add_conditional_edges(
        "trial_router",
        trial_route,
        {
            "trial_collect_client_info": "trial_collect_client_info",
            "trial_ask_date": "trial_ask_date",
            "trial_awaiting_confirmation": "trial_awaiting_confirmation",
            "trial_book": "trial_book",
            "END": END,
        },
    )

    g.add_edge("trial_collect_client_info", END)
    g.add_edge("trial_ask_date", END)
    g.add_conditional_edges(
        "trial_awaiting_confirmation",
        after_confirm_route,
        {"trial_book": "trial_book", "END": END},
    )
    g.add_edge("trial_book", END)

    return g.compile()
