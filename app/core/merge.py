"""
merge.py — Nó do grafo core que unifica as saídas dos especialistas.

Responsabilidades:
1. Lê specialists_outputs (dict com saídas de cada especialista)
2. Se nenhum especialista produziu saída, retorna mensagem fixa
3. Usa LLM + histórico da conversa (messages) para compor resposta final
4. Escreve final_answer e adiciona AIMessage em messages
"""
from __future__ import annotations

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_core.runnables import RunnableConfig

from app.core.state import GlobalState
from app.agents.aula_experimental.utils_trial.get_llm import get_llm

MERGE_SYSTEM_PROMPT = """Você é o assistente da CT Smash Beach Tennis.
Você recebe respostas de especialistas internos e deve compor uma única mensagem
natural, coerente e amigável para o cliente.

Regras:
- Use o histórico da conversa como contexto para manter continuidade
- Não invente informações além do que os especialistas forneceram
- NUNCA invente datas, horários ou disponibilidade — apenas repita os dados que os especialistas forneceram
- Se o especialista pediu uma data ao cliente, repasse o pedido sem sugerir datas específicas
- Mantenha o tom amigável e profissional
- Responda em português brasileiro
- Seja conciso — não repita o que já foi dito"""


def merge(state: GlobalState, config: RunnableConfig) -> dict:
    outputs = state.get("specialists_outputs") or {}
    parts = [v for v in outputs.values() if v]

    # Nenhum especialista produziu saída
    if not parts:
        msg = "Especialistas não produziram nada."
        return {
            "final_answer": msg,
            "messages": [AIMessage(content=msg)],
        }

    # LLM compõe resposta final com contexto do histórico
    llm = get_llm()
    history = state.get("messages", [])

    response = llm.invoke([
        SystemMessage(content=MERGE_SYSTEM_PROMPT),
        *history,
        HumanMessage(content="Respostas dos especialistas:\n" + "\n---\n".join(parts)),
    ])

    final = response.content
    return {
        "final_answer": final,
        "messages": [AIMessage(content=final)],
    }
