"""
nlg.py — Geração de mensagens (NLG) para o fluxo de Aula Experimental.

A LLM só redige o texto. Não decide fluxo, regras ou dados.
"""
from __future__ import annotations

from typing import Optional

from app.agents.aula_experimental.prompts import TRIAL_NLG_SYSTEM

# Função principal de geração de mensagens baseada em LLM e no contexto do trial recebido
def generate_trial_message(
    llm,
    *,
    stage: str,
    action: str,
    missing_fields: Optional[list[str]] = None,
    error_code: Optional[str] = None,
    trial_snapshot: Optional[dict] = None,
) -> str:
    """
    Usa a LLM apenas para redigir a mensagem ao usuário.
    Retorna texto puro (string), sanitizado.
    Nunca decide fluxo ou regras.
    """
    missing_fields = missing_fields or []
    trial_snapshot = trial_snapshot or {}

    user_prompt = f"""
Contexto: CT Smash Beach Tennis (aula experimental as terças feiras).
Stage: {stage}
Action: {action}
Missing_fields: {missing_fields}
Error_code: {error_code}
Trial_snapshot: {trial_snapshot}

Escreva UMA mensagem curta e direta ao usuário.
"""

    try:
        result = llm.invoke([
            {"role": "system", "content": TRIAL_NLG_SYSTEM},
            {"role": "user", "content": user_prompt},
        ])
        content = getattr(result, "content", "")
        return content.strip()
    except Exception:
        return ""
