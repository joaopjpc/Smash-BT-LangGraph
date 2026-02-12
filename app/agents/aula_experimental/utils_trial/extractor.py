
"""
extractor.py — Camada única de extração via LLM (Structured Output)

Este módulo é o "único lugar" onde o agente fala com o LLM para extrair dados do texto
do cliente e convertê-los em uma estrutura validada (TrialExtraction)(usa as descriptions do pydantic).

Objetivo:
- Transformar texto livre -> dados confiáveis (Pydantic) sem heurística manual.
- Centralizar prompt, chamada do modelo e parsing/validação do structured output.
- Manter os nós (nodes.py) limpos: nós não montam prompt nem lidam com parsing, apenas
  chamam `extract_trial_fields(...)` e decidem o fluxo.

O que este módulo faz:
- Monta mensagens (system/user) com contexto mínimo necessário:
  - stage atual (ex: collect_client_info / ask_date / awaiting_confirmation)
  - snapshot do trial (o que já sabemos)
  - texto do cliente
  - referência temporal (opcional, se você permitir normalizar "terça que vem")
- Chama o LLM em modo Structured Output (Pydantic) e retorna TrialExtraction.

O que este módulo NÃO faz:
- Não valida regra do negócio (ex: "é terça?") -> isso é responsabilidade do validators.py.
- Não decide transições de stage -> isso é responsabilidade dos nós.
- Não persiste no banco -> isso é responsabilidade da camada de serviço/repositório.

Benefícios:
- Trocar de modelo/provider fica fácil (muda aqui).
- Debug fica centralizado (logging de input/output).
- Reduz risco de alucinação, porque o modelo é forçado a obedecer o schema.
"""

from __future__ import annotations
from typing import Optional, List

from langchain_core.messages import HumanMessage, AIMessage

from app.agents.aula_experimental.utils_trial.schemas import TrialExtraction
from app.agents.aula_experimental.utils_trial.prompts import TRIAL_EXTRACT_SYSTEM
from app.core.datetime_utils import get_current_context


def _format_recent_messages(messages: list, n: int = 4) -> str:
    """Formata as últimas n mensagens (Human/AI) como texto para o prompt."""
    if not messages:
        return ""
    recent = messages[-n:]
    lines = []
    for msg in recent:
        if isinstance(msg, HumanMessage):
            lines.append(f'Cliente: "{msg.content}"')
        elif isinstance(msg, AIMessage):
            lines.append(f'Bot: "{msg.content}"')
    if not lines:
        return ""
    return "Histórico recente da conversa:\n" + "\n".join(lines)


# Função para construir o prompt do usuário informando o contexto atual (stage atual, snapshot do trial, texto do cliente)
def build_extract_user_prompt(*, client_text: str, stage: str, trial_snapshot: dict,
                               now_iso: str, weekday: str, next_tuesdays: list[str],
                               recent_history: str = "") -> str:
    history_block = f"\n{recent_history}\n" if recent_history else ""
    return f"""
Data/hora atual (referência): {now_iso} ({weekday})
Próximas terças-feiras disponíveis: {', '.join(next_tuesdays)}

Etapa do fluxo (stage): {stage}

Estado atual conhecido (trial_snapshot):
{trial_snapshot}
{history_block}
Mensagem do cliente:
{client_text}

Extraia somente o que estiver na mensagem do cliente.
"""

# Função principal de extração usando LLM e schema definido
def extract_trial_fields(llm, *, client_text: str, stage: str, trial_snapshot: dict,
                         messages: Optional[List] = None) -> TrialExtraction:
    ctx = get_current_context()
    recent_history = _format_recent_messages(messages or [], n=4)

    user_prompt = build_extract_user_prompt(
        client_text=client_text,
        stage=stage,
        trial_snapshot=trial_snapshot,
        now_iso=ctx["now_iso"],
        weekday=ctx["weekday"],
        next_tuesdays=ctx["next_tuesdays"],
        recent_history=recent_history,
    )

    # Padrão structured output
    extractor = llm.with_structured_output(TrialExtraction)
    return extractor.invoke([
        {"role": "system", "content": TRIAL_EXTRACT_SYSTEM},
        {"role": "user", "content": user_prompt},
    ])
