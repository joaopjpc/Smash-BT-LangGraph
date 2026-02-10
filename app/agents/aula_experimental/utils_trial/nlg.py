"""
nlg.py — Geração de mensagens (NLG) para o fluxo de Aula Experimental.

A LLM só redige o texto. Não decide fluxo, regras ou dados.
"""
from __future__ import annotations

from typing import Optional

from app.agents.aula_experimental.utils_trial.prompts import TRIAL_NLG_SYSTEM
from app.core.prompts import SPECIALIST_BASE_PROMPT


def _format_snapshot(snapshot: dict) -> str:
    """Converte o snapshot do trial em texto legível para o prompt da NLG."""
    if not snapshot:
        return "(vazio)"
    labels = {
        "nome": "Nome", "idade": "Idade", "nivel": "Nível",
        "desired_date": "Data", "desired_time": "Horário",
        "confirmed": "Confirmado", "stage": "Etapa",
    }
    lines = []
    for key, label in labels.items():
        val = snapshot.get(key)
        if val is not None:
            lines.append(f"- {label}: {val}")
    return "\n".join(lines) if lines else "(vazio)"


# Função principal de geração de mensagens baseada em LLM e no contexto do trial recebido
def generate_trial_message(
    llm,
    *,
    stage: str,
    action: str,
    missing_fields: Optional[list[str]] = None,
    error_code: Optional[str] = None,
    trial_snapshot: Optional[dict] = None,
    client_text: Optional[str] = None,
) -> str:
    """
    Usa a LLM apenas para redigir a mensagem ao usuário.
    Retorna texto puro (string), sanitizado.
    Nunca decide fluxo ou regras.
    """
    missing_fields = missing_fields or []
    trial_snapshot = trial_snapshot or {}

    client_context = ""
    if client_text:
        client_context = f"\nMensagem original do cliente: {client_text}\n"

    user_prompt = f"""
Contexto: CT Smash Beach Tennis (aula experimental as terças feiras).
Stage: {stage}
Action: {action}
Missing_fields: {missing_fields}
Error_code: {error_code}
Trial_snapshot:
{_format_snapshot(trial_snapshot)}
{client_context}
Escreva UMA mensagem curta e direta ao usuário.
"""

    try:
        result = llm.invoke([
            {"role": "system", "content": SPECIALIST_BASE_PROMPT + "\n\n" + TRIAL_NLG_SYSTEM},
            {"role": "user", "content": user_prompt},
        ])
        content = getattr(result, "content", "")
        return content.strip()
    except Exception:
        return ""
