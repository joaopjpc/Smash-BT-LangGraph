"""
graph.py — Grafo core (principal) do sistema SMASH.

Fluxo:
  input_node → triage → [Send] → trial / faq / merge → merge → END

- input_node: extrai client_input da ultima HumanMessage
- triage: classifica intencao (LLM), suporta multi-intent e contexto ativo
- trial: subgrafo de aula experimental (real)
- faq: stub (placeholder)
- merge: compoe resposta final a partir de specialists_outputs

Routing usa Send() pra suportar execucao paralela de especialistas
(ex: trial + faq ao mesmo tempo).
"""
from __future__ import annotations

from langgraph.graph import StateGraph, END
from langgraph.constants import Send
from langchain_core.messages import HumanMessage
from langchain_core.runnables import RunnableConfig

from app.core.state import GlobalState
from app.core.merge import merge
from app.core.triage import triage
from app.agents.aula_experimental.workflow import build_trial_graph
from app.agents.faq.node import faq_node


# Adapter só pra langraph CLI/Studio, Backend com wpp vai mudar depois
def input_node(state: GlobalState, config: RunnableConfig) -> dict:
    """
    No de entrada: extrai o texto da ultima mensagem do usuario
    e seta client_input para os nos especialistas consumirem.

    O Studio envia a entrada como HumanMessage em messages.
    Os nos do trial leem de client_input (string pura).
    Este no faz a ponte entre os dois.
    """
    messages = state.get("messages", [])
    for msg in reversed(messages):
        if isinstance(msg, HumanMessage):
            content = msg.content
            # Studio pode enviar content como lista de blocos (multimodal)
            # Ex: [{"type": "text", "text": "..."}]
            if isinstance(content, list):
                content = " ".join(
                    block.get("text", "") for block in content
                    if isinstance(block, dict) and block.get("type") == "text"
                )
            return {"client_input": content}
    return {}


def route_after_triage(state: GlobalState):
    """
    Decide quais nos rodar apos o triage.

    Usa Send() pra suportar multiplos destinos em paralelo.
    Ex: active_routes=["trial", "faq"] → Send("trial") + Send("faq")
    """
    routes = state.get("active_routes", [])
    if not routes or routes == ["general"]:
        return [Send("merge", state)]
    return [Send(route, state) for route in routes]


def build_core_graph(config: RunnableConfig):
    """
    Factory do grafo principal.

    Aceita apenas RunnableConfig (padrao LangGraph CLI/Studio).
    """
    g = StateGraph(GlobalState)

    # --- nos ---
    g.add_node("input_node", input_node)
    g.add_node("triage", triage)
    g.add_node("trial", build_trial_graph(config))   # subgrafo compilado
    g.add_node("faq", faq_node)
    g.add_node("merge", merge)

    # --- fluxo ---
    g.set_entry_point("input_node")
    g.add_edge("input_node", "triage")
    g.add_conditional_edges("triage", route_after_triage)
    g.add_edge("trial", "merge")
    g.add_edge("faq", "merge")
    g.add_edge("merge", END)

    return g.compile()
