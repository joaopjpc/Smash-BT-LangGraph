"""
get_llm.py — Singleton do LLM usado pelo workflow de Aula Experimental.

Instancia o ChatOpenAI uma única vez e reutiliza nas chamadas seguintes.
"""

from __future__ import annotations

import os

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI

_llm = None


def get_llm() -> ChatOpenAI:
    global _llm
    if _llm is None:
        load_dotenv()
        model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
        _llm = ChatOpenAI(model=model, temperature=0)
    return _llm
