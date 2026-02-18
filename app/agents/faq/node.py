"""
node.py -- No de FAQ com RAG.

Recebe a pergunta do cliente, busca trechos relevantes no knowledge base
via FAISS retriever, e gera resposta via LLM (NLG).

Padrao do projeto: LLM e ferramenta (NLG), nao decisor.
Retrieval e deterministico (similarity search).
"""
from __future__ import annotations

from langchain_core.messages import HumanMessage, AIMessage
from langchain_core.runnables import RunnableConfig

from app.core.state import GlobalState
from app.core.prompts import SPECIALIST_BASE_PROMPT
from app.agents.faq.prompt import FAQ_SYSTEM_PROMPT
from app.agents.faq.retriever import retrieve_faq_context
from app.agents.aula_experimental.utils_trial.get_llm import get_llm


_FALLBACK_MESSAGE = (
    "Desculpe, nao consegui buscar essa informacao agora. "
    "Tente novamente ou entre em contato pelo nosso WhatsApp!"
)

_MAX_HISTORY_MESSAGES = 6


def _format_history(messages) -> str:
    """Formata ultimas mensagens (excluindo a atual) como contexto."""
    msgs = messages[:-1] if messages else []
    recent = msgs[-_MAX_HISTORY_MESSAGES:] if msgs else []
    if not recent:
        return ""
    lines = []
    for msg in recent:
        if isinstance(msg, HumanMessage):
            role = "Cliente"
        elif isinstance(msg, AIMessage):
            role = "Assistente"
        else:
            continue
        content = msg.content
        if isinstance(content, list):
            content = " ".join(
                b.get("text", "") for b in content
                if isinstance(b, dict) and b.get("type") == "text"
            )
        lines.append(f"{role}: {content}")
    return "\n".join(lines)


def faq_node(state: GlobalState, config: RunnableConfig) -> dict:
    query = state.get("client_input", "")
    if not query:
        return {"specialists_outputs": {"faq": _FALLBACK_MESSAGE}}

    # 1. Retrieval (similarity search deterministico — só client_input)
    context = retrieve_faq_context(query)

    # 2. Montar historico de conversa pra contexto da LLM
    history = _format_history(state.get("messages", []))

    # 3. NLG via LLM (com historico + trechos recuperados)
    try:
        llm = get_llm()
        parts = []
        if history:
            parts.append(f"Historico recente da conversa:\n{history}")
        parts.append(f"Pergunta atual do cliente: {query}")
        parts.append(f"Trechos relevantes:\n{context if context else '(nenhum trecho encontrado)'}")
        parts.append("Escreva UMA resposta curta e direta para o cliente.")

        user_prompt = "\n\n".join(parts)
        response = llm.invoke([
            {"role": "system", "content": SPECIALIST_BASE_PROMPT + "\n\n" + FAQ_SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ])
        answer = getattr(response, "content", "").strip()
    except Exception:
        answer = ""

    # 4. Fallback se LLM falhou ou retornou vazio
    if not answer:
        answer = _FALLBACK_MESSAGE

    return {"specialists_outputs": {"faq": answer}}
