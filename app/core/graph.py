"""
graph.py — Grafo core (principal) do sistema SMASH.

Versão mínima: input_node → trial → merge.
Futuramente será expandido com triage, faq, servicos, etc.

Fluxo atual:
  input_node → trial (subgrafo) → merge → END
"""
from __future__ import annotations

from langgraph.graph import StateGraph, END
from langchain_core.messages import HumanMessage
from langchain_core.runnables import RunnableConfig

from app.core.state import GlobalState
from app.core.merge import merge
from app.agents.aula_experimental.workflow import build_trial_graph


def input_node(state: GlobalState, config: RunnableConfig) -> dict:
    """
    Nó de entrada: extrai o texto da última mensagem do usuário
    e seta client_input para os nós especialistas consumirem.

    O Studio envia a entrada como HumanMessage em messages.
    Os nós do trial leem de client_input (string pura).
    Este nó faz a ponte entre os dois.
    """
    messages = state.get("messages", [])
    # Pega a última HumanMessage (ignora AIMessage do turno anterior)
    for msg in reversed(messages):
        if isinstance(msg, HumanMessage):
            return {"client_input": msg.content}
    return {}


def build_core_graph(config: RunnableConfig):
    """
    Factory do grafo principal.

    Aceita apenas RunnableConfig (padrão LangGraph CLI/Studio).
    """
    g = StateGraph(GlobalState)

    # --- nós ---
    g.add_node("input_node", input_node)
    g.add_node("trial", build_trial_graph(config))   # subgrafo compilado
    g.add_node("merge", merge)

    # --- fluxo ---
    g.set_entry_point("input_node")
    g.add_edge("input_node", "trial")
    g.add_edge("trial", "merge")
    g.add_edge("merge", END)

    return g.compile()
