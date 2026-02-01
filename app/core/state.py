"""Estado global compartilhado pelo grafo."""
from __future__ import annotations

import operator
from typing import Dict, List, TypedDict

from typing_extensions import Annotated

from langgraph.graph.message import AnyMessage, add_messages

from app.agents.aula_experimental.state import TrialState


class GlobalState(TypedDict, total=False):
    # entrada
    client_input: str
    client_id: int | str

    # (opcional) histórico do turno
    messages: Annotated[List[AnyMessage], add_messages]

    # roteamento / coordenação
    router_input: str            # entrada para o roteador
    active_routes: List[str]     # rotas ativas no momento
    specialists_outputs: Annotated[Dict[str, str], operator.or_] # saídas dos especialistas

    # sub-estados
    trial: TrialState          # estado do agente de aula experimental
    # services: ServicesState  # estado do agente de serviços (standby)

    # resposta final
    final_answer: str
    finished: bool
