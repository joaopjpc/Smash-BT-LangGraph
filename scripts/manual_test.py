from __future__ import annotations

import os
import sys

ROOT = os.path.dirname(os.path.dirname(__file__))
if ROOT not in sys.path:
    sys.path.append(ROOT)

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI

from app.agents.aula_experimental.workflow import build_trial_graph


def main() -> None:
    load_dotenv()

    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)
    graph = build_trial_graph(llm=llm)

    state = {
        "client_id": "teste_001",
        "trial": {},
    }

    messages = [
        "Oi, quero marcar uma aula experimental.",
        "Meu nome é João, tenho 27 e sou iniciante.",
        "Quero terça 2026-02-03 às 19:00.",
        "Sim, confirmo.",
    ]

    for i, msg in enumerate(messages, start=1):
        state["client_input"] = msg
        state = graph.invoke(state)
        bot_msg = state.get("specialists_outputs", {}).get("trial", "")
        stage = (state.get("trial") or {}).get("stage")

        print(f"\n# Turno {i}")
        print("USER:", msg)
        print("BOT:", bot_msg)
        print("STATE.stage:", stage)
        print("-" * 40)


if __name__ == "__main__":
    main()
