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

from typing import Any

from langgraph.graph import StateGraph, END

from app.core.state import GlobalState
from app.agents.aula_experimental.nodes import (
    ensure_trial_defaults,
    trial_collect_client_info,
    trial_ask_date,
    trial_awaiting_confirmation,
    trial_book,
    trial_handoff,
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
        "handoff_needed": "trial_handoff",
    }

    return stage_to_node.get(stage, "trial_collect_client_info")

# Após confirmação, decide se vai para book (se confirmado) ou END (se não)
def after_confirm_route(state: GlobalState) -> str:
    stage = (state.get("trial") or {}).get("stage")
    if stage == "book":
        return "trial_book"
    return "END"


def build_trial_graph(*, llm: Any, booking_repo: Any = None):
    """
    Constrói e compila o subgrafo.

    Parâmetros:
    - llm: objeto LLM já configurado (com structured output no extractor).
    - booking_repo: repositório/serviço com create_trial_booking(...). Pode ser None em DEV.
    """
    g = StateGraph(GlobalState)

    # Para capturar dependências (llm, booking_repo), usamos lambdas/closures.
    g.add_node("trial_router", trial_router)
    g.add_node("trial_collect_client_info", lambda s: trial_collect_client_info(s, llm=llm))
    g.add_node("trial_ask_date", lambda s: trial_ask_date(s, llm=llm))
    g.add_node("trial_awaiting_confirmation", lambda s: trial_awaiting_confirmation(s, llm=llm))
    g.add_node("trial_book", lambda s: trial_book(s, booking_repo=booking_repo))
    g.add_node("trial_handoff", trial_handoff)

    # Entrada sempre cai no roteador por stage:
    g.set_entry_point("trial_router")

    # Roteamento por stage (retorna nome do nó ou "END")
    g.add_conditional_edges(
        "trial_router",
        trial_route,
        {
            "trial_collect_client_info": "trial_collect_client_info",
            "trial_ask_date": "trial_ask_date",
            "trial_awaiting_confirmation": "trial_awaiting_confirmation",
            "trial_book": "trial_book",
            "trial_handoff": "trial_handoff",
            "END": END,
        },
    )

    # Edges de captura de dados vão direto para END
    g.add_edge("trial_collect_client_info", END)
    g.add_edge("trial_ask_date", END)

    # Edge condicional pós confirmação do cliente 
    g.add_conditional_edges(                      # depois de confirmação, decide se vai para book ou END
        "trial_awaiting_confirmation",            # nó de confirmação
        after_confirm_route,                      # função de roteamento pós confirmação
        {"trial_book": "trial_book", "END": END}, # mapeamento de destinos possíveis (trial_book se confirmado, END se não)
    )
    g.add_edge("trial_book", END)
    g.add_edge("trial_handoff", END)

    return g.compile()
