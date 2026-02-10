"""
triage.py — No de triagem do grafo core.

Responsabilidades:
1. Classifica a intencao do usuario via LLM (structured output) — sempre
2. Passa contexto de conversa ativa pro LLM (se houver) pra desambiguar
3. Suporta multi-intent: pode rotear pra trial + faq em paralelo
4. Para inputs genericos (saudacoes, etc), responde direto sem chamar especialista

Categorias:
- trial: aula experimental / agendamento de aula
- faq: duvidas sobre a CT (localizacao, planos, horarios, regras)
- general: saudacoes, agradecimentos, mensagens fora de contexto
"""
from __future__ import annotations

from typing import Optional, Literal, List

from pydantic import BaseModel, Field
from langchain_core.runnables import RunnableConfig

from app.core.state import GlobalState
from app.agents.aula_experimental.utils_trial.get_llm import get_llm


# ---------------------------------------------------------------------------
# Schema de classificacao
# ---------------------------------------------------------------------------

class TriageResult(BaseModel):
    intents: List[Literal["trial", "faq", "general"]] = Field(
        description="Lista de intencoes detectadas. Pode conter mais de uma (ex: ['trial', 'faq']). 'general' deve aparecer sozinho."
    )
    general_response: Optional[str] = Field(
        default=None,
        description="Resposta amigavel para o cliente. Preenchido SOMENTE quando 'general' esta em intents.",
    )


# ---------------------------------------------------------------------------
# Prompt
# ---------------------------------------------------------------------------

TRIAGE_SYSTEM_PROMPT = """Voce e o classificador de intencoes da CT Smash Beach Tennis.

Analise a mensagem atual do cliente e o contexto da conversa e classifique nas categorias aplicaveis:

- "trial": o cliente quer AGENDAR AULA EXPERIMENTAL (agendar primeira aula, marcar aula teste, experimentar).
- "faq": o cliente tem duvidas sobre o CT (localizacao, planos, precos, horarios, estrutura, regras, funcionamento, horarios/infos de aula experimental).
- "general": saudacoes (oi, ola, bom dia), agradecimentos, mensagens fora de contexto de FAQ/Aula Experimental, ou qualquer coisa que nao se encaixe nas outras.

Regras de classificacao:
- Voce pode retornar MULTIPLAS intencoes. Ex: "quero agendar e onde fica?" -> ["trial", "faq"]
- "general" deve aparecer SOZINHO, nunca junto com trial/faq.
- Caso o cliente cite "Aula Experimental":
  - "trial": interesse real em COMECAR UM AGENDAMENTO
  - "faq": interesse em INFORMACOES sobre aula experimental (se e possivel, quais horarios, local da aula experimental)
  - Ambos se o cliente quer agendar E pergunta info ao mesmo tempo

Se houver um [CONTEXTO] informando que o cliente esta no meio de um agendamento:
- Mensagens ambiguas ("sim", "nao", datas, horarios, nomes) devem incluir "trial"
- Perguntas claras sobre outros assuntos podem incluir "faq" JUNTO com "trial"
- Se a mensagem claramente NAO e sobre o agendamento em curso (ex: so uma duvida), pode ser so ["faq"]

Se "general" estiver nas intencoes, escreva uma resposta curta e amigavel em portugues brasileiro no campo general_response.
Exemplos:
- "oi" -> "Ola! Sou o assistente da CT Smash. Como posso te ajudar?"
- "obrigado" -> "Por nada! Se precisar de algo mais, e so chamar."
- "tchau" -> "Ate mais! Bom treino!"

Se "general" NAO estiver nas intencoes, deixe general_response como null."""


# ---------------------------------------------------------------------------
# Classificacao
# ---------------------------------------------------------------------------

def _classify_intent(text: str, active_context: str | None = None) -> TriageResult: 
    """Classifica a intencao do cliente usando LLM com structured output."""
    llm = get_llm()
    classifier = llm.with_structured_output(TriageResult)

    user_content = text
    if active_context:
        user_content = f"[CONTEXTO: {active_context}]\n\nùltima mensagem do cliente: {text}"

    return classifier.invoke([
        {"role": "system", "content": TRIAGE_SYSTEM_PROMPT},
        {"role": "user", "content": user_content},
    ])


# ---------------------------------------------------------------------------
# No do grafo
# ---------------------------------------------------------------------------

def triage(state: GlobalState, config: RunnableConfig) -> dict:
    """
    Nó de triagem: classifica intencao e decide roteamento.

    Sempre chama o LLM — mesmo com conversa ativa.
    O contexto da conversa ativa e passado no prompt pra
    desambiguar mensagens como "sim" ou "19:00".
    """
    text = state.get("client_input", "")
    trial = state.get("trial", {})
    stage = trial.get("stage")

    # Montar contexto de conversa ativa (se houver)
    active_context = None
    if stage and stage not in ("booked", "cancelled"): # se tiver stage e nao for etapa final (booked/cancelled), considera que cliente esta no meio do agendamento
        active_context = f"Cliente esta no meio de um agendamento de aula experimental (etapa: {stage})"

    result = _classify_intent(text, active_context)

    if "general" in result.intents:
        response = result.general_response or "Ola! Sou o assistente da CT Smash. Como posso te ajudar?"
        return {
            "active_routes": ["general"],
            "specialists_outputs": {"triage": response},
        }

    return {"active_routes": result.intents}
