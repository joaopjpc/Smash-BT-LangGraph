
"""
extractor.py — Camada única de extração via LLM (Structured Output)

Este módulo é o "único lugar" onde o agente fala com o LLM para extrair dados do texto
do cliente e convertê-los em uma estrutura validada (TrialExtraction).

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
from datetime import datetime, timedelta
from app.agents.aula_experimental.utils_trial.schemas import TrialExtraction
from app.agents.aula_experimental.utils_trial.prompts import TRIAL_EXTRACT_SYSTEM

DIAS_SEMANA = [
    "segunda-feira", "terça-feira", "quarta-feira",
    "quinta-feira", "sexta-feira", "sábado", "domingo",
]


def _next_tuesdays(n: int = 4) -> list[str]:
    """Retorna as próximas N terças-feiras futuras em formato dd-mm."""
    today = datetime.now().date()
    days_ahead = (1 - today.weekday()) % 7  # 1 = terça
    tuesdays = []
    if days_ahead == 0:
        # hoje é terça → incluir hoje na lista
        tuesdays.append(f"{today.day:02d}-{today.month:02d}")
        days_ahead = 7  # próximas terças começam daqui a 7 dias
    d = today + timedelta(days=days_ahead)
    for _ in range(n):
        tuesdays.append(f"{d.day:02d}-{d.month:02d}")
        d += timedelta(weeks=1)
    return tuesdays


# Função para construir o prompt do usuário informando o contexto atual (stage atual, snapshot do trial, texto do cliente)
def build_extract_user_prompt(*, client_text: str, stage: str, trial_snapshot: dict,
                               now_iso: str, weekday: str, next_tuesdays: list[str]) -> str:
    return f"""
Data/hora atual (referência): {now_iso} ({weekday})
Próximas terças-feiras disponíveis: {', '.join(next_tuesdays)}

Etapa do fluxo (stage): {stage}

Estado atual conhecido (trial_snapshot):
{trial_snapshot}

Mensagem do cliente:
{client_text}

Extraia somente o que estiver na mensagem do cliente.
"""

# Função principal de extração usando LLM e schema definido
def extract_trial_fields(llm, *, client_text: str, stage: str, trial_snapshot: dict) -> TrialExtraction:
    now = datetime.now()
    now_iso = now.isoformat(timespec="minutes")
    weekday = DIAS_SEMANA[now.weekday()]
    tuesdays = _next_tuesdays(4)

    user_prompt = build_extract_user_prompt(
        client_text=client_text,
        stage=stage,
        trial_snapshot=trial_snapshot,
        now_iso=now_iso,
        weekday=weekday,
        next_tuesdays=tuesdays,
    )

    # Padrão structured output
    extractor = llm.with_structured_output(TrialExtraction)  # se disponível no seu wrapper
    return extractor.invoke([
        {"role": "system", "content": TRIAL_EXTRACT_SYSTEM},
        {"role": "user", "content": user_prompt},
    ])
