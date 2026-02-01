"""
nodes.py — Nós do subgrafo de Aula Experimental (Trial)

Estratégia:
- Cada nó controla uma etapa do fluxo (stage) e é responsável por:
  1) chamar o extractor (LLM -> TrialExtraction estruturado)
  2) fazer merge no TrialState sem apagar dados já coletados
  3) validar regras determinísticas (validators.py)
  4) definir trial.stage e trial.output (a mensagem do turno)

Observação:
- Este arquivo NÃO faz parsing heurístico de texto.
- Extração sempre vem do LLM via extractor.py (Structured Output).
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from app.core.state import GlobalState

# Seu extractor/schema/validator (você já criou esses módulos)
from app.agents.aula_experimental.extractor import extract_trial_fields
from app.agents.aula_experimental.schemas import TrialExtraction
from app.agents.aula_experimental.nlg import generate_trial_message
import app.agents.aula_experimental.validators as v


# -------------------------
# Helpers (state + merge)
# -------------------------

DEFAULT_STAGE = "collect_client_info"

# Campos que pertencem ao TrialState e podem ser preenchidos pelo LLM
TRIAL_FIELDS = {
    "nome",
    "idade",
    "nivel",
    "desired_date",
    "desired_time",
    "confirmed",
}

REQUIRED_CLIENT_FIELDS = ("nome", "idade", "nivel")

# Roteador simples: não altera estado (usado em workflow.py)
def trial_router(state: GlobalState) -> GlobalState:
    """Nó roteador: não altera o estado, só redireciona pelo stage."""
    return state


# Garante que estado trial existe e seta defaults mínimos (só quando é deafult!)
def ensure_trial_defaults(state: GlobalState) -> Dict[str, Any]:
    """Garante que state['trial'] existe e possui defaults mínimos."""
    trial = state.get("trial") or {}         # pega estado existente ou cria dict vazio

    # função seta default somente se não existir nada no campo.
    trial.setdefault("stage", DEFAULT_STAGE) # Trial só é vazio na primeira vez entao seta collect_client_info pra começo do fluxo 
    trial.setdefault("booking_created", False)
    trial.setdefault("handoff_requested", False)
    trial.setdefault("output", None)

    state["trial"] = trial                   # atualiza estado global com trial atualizado
    return trial


# Função auxiliar para converter TrialExtraction em dict (usado no merge)
def _to_dict_extraction(extraction: Any) -> Dict[str, Any]:
    """Aceita TrialExtraction, dict, ou qualquer obj com model_dump()."""
    if extraction is None:
        return {}
    if isinstance(extraction, dict):
        return extraction
    if hasattr(extraction, "model_dump"):
        return extraction.model_dump()
    # último fallback: tenta __dict__
    return getattr(extraction, "__dict__", {})


# Função que recebe o trial atual e faz merge seguro com dados extraídos pelo extractor (atualiza no trial, somente campos não-nulos contidos no extractor)
def merge_trial(trial: Dict[str, Any], extraction: Any) -> Dict[str, Any]:
    """
    Merge “seguro”: só sobrescreve campos quando vierem não-nulos do extractor.
    Não apaga valores já coletados.
    """
    data = _to_dict_extraction(extraction)
    for k, val in data.items():
        if k in TRIAL_FIELDS and val is not None:
            trial[k] = val
    return trial


def _validation_result_to_code(res: Any) -> tuple[bool, Optional[str]]:
    """
    Normaliza retorno de validação:
    - pode ser (ok, error_code)
    - pode ser obj com .ok e .error
    - pode ser dict {"ok": ..., "error": ...}
    """
    if res is None:
        return False, "validation_error"

    if isinstance(res, tuple) and len(res) >= 1:
        ok = bool(res[0])
        code = res[1] if len(res) > 1 else None
        return ok, code

    if isinstance(res, dict):
        return bool(res.get("ok")), res.get("error")

    if hasattr(res, "ok"):
        return bool(getattr(res, "ok")), getattr(res, "error", None)

    return False, "validation_error"

# Função para exportar saída do trial pro estado global "specialists_outputs"
def export_trial_output(state: GlobalState) -> GlobalState:
    """
    Padroniza a saída do especialista:
    - copia trial.output para specialists_outputs['trial']
    Isso ajuda o merge global a compor final_answer.
    """
    trial = ensure_trial_defaults(state)      # Garante trial no estado global
    out = (trial.get("output") or "").strip() # Pega output do trial 

    if out:
        state.setdefault("specialists_outputs", {}) # Garante specialists_outputs existe
        state["specialists_outputs"]["trial"] = out # Seta saída do trial no specialists_outputs

    return state

# Função auxiliar para chamar NLG (com fallback caso LLM falhe)
def _fallback_or_nlg(*, llm: Any, stage: str, action: str, missing_fields: Optional[list[str]], error_code: Optional[str], trial: Dict[str, Any], fallback: str) -> str:
    msg = generate_trial_message(
        llm,
        stage=stage,
        action=action,
        missing_fields=missing_fields,
        error_code=error_code,
        trial_snapshot=trial,
    )
    return msg or fallback


# -------------------------
# Nó 1: Coletar dados
# -------------------------

def trial_collect_client_info(state: GlobalState, *, llm: Any) -> GlobalState:  # Recebe: estado global + LLM
    trial = ensure_trial_defaults(state)            # Garante trial no estado global
    text = state.get("client_input", "") or ""      # Pega input do cliente (texto)

    extraction: TrialExtraction = extract_trial_fields( # Chama extractor LLM -> TrialExtraction para extrair dados do texto
        llm,
        client_text=text,
        stage="collect_client_info",
        trial_snapshot=trial,
    )
    merge_trial(trial, extraction)                      # Faz merge seguro dos dados extraídos pro trial atual

    missing = [f for f in REQUIRED_CLIENT_FIELDS if not trial.get(f)] # Verifica campos obrigatórios faltantes
    if missing:                                                       # Se tiver campos faltando...
        parts = []                                                    # Constrói lista de campos faltantes para mensagem
        for m in missing:                                             # Itera sobre campos faltantes
            if m == "nome":                   
                parts.append("seu nome")                              # Adiciona descrição amigável do campo pra fallback depois
            elif m == "idade":
                parts.append("sua idade")
            elif m == "nivel":
                parts.append("seu nível (iniciante/intermediário/avançado)")
        trial["stage"] = "collect_client_info"
        fallback = "Para agendar sua aula experimental, me diga: " + ", ".join(parts) + "." # Mensagem fallback pra auditoria ou falha da LLM
        trial["output"] = _fallback_or_nlg(       # Chama NLG ou usa fallback 
            llm=llm,
            stage="collect_client_info",          # Passa stage 
            action="ask_missing_client_fields",   # Passa action
            missing_fields=missing,               # Passa campos faltantes 
            error_code=None,
            trial=trial,                          # Passa trial snapshot pro NLG
            fallback=fallback,
        )
        return export_trial_output(state)  # Exporta saída pro estado global "specialists_outputs" e retorna estado atualizado

    trial["stage"] = "ask_date"   # Caso não tenha campos faltando, avança para próxima etapa: pedir data/horário
    fallback = "A aula experimental é toda terça. Qual terça (dia do mês) e horário você prefere?"

    # trial["output"] = _fallback_or_nlg(  # Chama NLG ou usa fallback pra pedir data/horário
    #     llm=llm,
    #     stage="ask_date",
    #     action="ask_date_time",
    #     missing_fields=None, 
    #     error_code=None,
    #     trial=trial,
    #     fallback=fallback,
    # )
    # return export_trial_output(state)
    """""
    Aqui optei por não chamar o NLG (LLM) na primeira vez que pede data/horário,
    porque o caso é: acabei de perceber que tenho todos os dados do cliente,
    então já vou direto pedir data/horário. Nesse caso, a mensagem é sempre
    a mesma (pede data/horário), então não se faz necessário LLM (não precisa de interpretação nem criatividade).
    então uso um fallback simples:
    """""
    trial["output"] = fallback       # Usa fallback simples pra pedir data/horário pela primeira vez (aqui é ok não chamar LLM)
    return export_trial_output(state) # sempre que eu uso export_trial_output(state), tenho que garantir que o trial.output está setado corretamente antes


# -------------------------
# Nó 2: Pedir data/horário (terça)
# -------------------------

def trial_ask_date(state: GlobalState, *, llm: Any) -> GlobalState:
    trial = ensure_trial_defaults(state)
    text = state.get("client_input", "") or ""

    extraction: TrialExtraction = extract_trial_fields(
        llm,
        client_text=text,
        stage="ask_date",
        trial_snapshot=trial,
    )
    merge_trial(trial, extraction)

    # Usa validator do seu módulo (com fallback defensivo de API)
    if hasattr(v, "validate_date_time"):
        ok, code = _validation_result_to_code(
            v.validate_date_time(trial.get("desired_date"), trial.get("desired_time"))
        )
    else:
        ok, code = False, "missing_validator"

    if not ok:
        trial["stage"] = "ask_date"

        # Mensagens por erro (você pode ajustar à vontade)
        if code == "missing_date":
            fallback = "Me diga a data exata da terça (YYYY-MM-DD ou dd/mm/aaaa) e o horário."
        elif code == "invalid_date_format":
            fallback = "A data precisa estar clara. Pode me dizer a terça em formato dd/mm/aaaa e o horário?"
        elif code == "not_tuesday":
            fallback = "A aula experimental acontece somente na terça. Qual terça e horário você prefere?"
        elif code == "missing_time":
            dd = trial.get("desired_date") or "essa terça"
            fallback = f"Fechado para {dd}. Qual horário você prefere? (ex: 19:00)"
        elif code == "invalid_time_format":
            fallback = "O horário precisa estar claro (ex: 19:00). Qual horário você prefere?"
        else:
            fallback = "Não consegui validar a data/horário. Pode informar a terça (data) e o horário novamente?"

        trial["output"] = _fallback_or_nlg(
            llm=llm,
            stage="ask_date",
            action="ask_date_time",
            missing_fields=None,
            error_code=code,
            trial=trial,
            fallback=fallback,
        )
        return export_trial_output(state)

    trial["stage"] = "awaiting_confirmation"
    fallback = f"Confirma sua aula experimental na terça {trial['desired_date']} às {trial['desired_time']}?"
    trial["output"] = _fallback_or_nlg(
        llm=llm,
        stage="awaiting_confirmation",
        action="ask_confirmation",
        missing_fields=None,
        error_code=None,
        trial=trial,
        fallback=fallback,
    )
    return export_trial_output(state)


# -------------------------
# Nó 3: Confirmação
# -------------------------

def trial_awaiting_confirmation(state: GlobalState, *, llm: Any) -> GlobalState:
    trial = ensure_trial_defaults(state)
    text = state.get("client_input", "") or ""

    extraction: TrialExtraction = extract_trial_fields(
        llm,
        client_text=text,
        stage="awaiting_confirmation",
        trial_snapshot=trial,
    )
    merge_trial(trial, extraction)

    conf = trial.get("confirmed")

    if conf is None:
        trial["stage"] = "awaiting_confirmation"
        fallback = "Só pra confirmar: sim ou não?"
        trial["output"] = _fallback_or_nlg(
            llm=llm,
            stage="awaiting_confirmation",
            action="ask_confirmation",
            missing_fields=None,
            error_code=None,
            trial=trial,
            fallback=fallback,
        )
        return export_trial_output(state)

    if conf is False:
        trial["stage"] = "ask_date"
        fallback = "Sem problemas. Qual terça e horário você prefere então?"
        trial["output"] = _fallback_or_nlg(
            llm=llm,
            stage="ask_date",
            action="ask_date_time",
            missing_fields=None,
            error_code=None,
            trial=trial,
            fallback=fallback,
        )
        return export_trial_output(state)

    # conf True
    trial["stage"] = "book"
    fallback = "Perfeito! Vou registrar seu agendamento agora."
    trial["output"] = _fallback_or_nlg(
        llm=llm,
        stage="book",
        action="book_start",
        missing_fields=None,
        error_code=None,
        trial=trial,
        fallback=fallback,
    )
    return export_trial_output(state)


# -------------------------
# Nó 4: Booking (persistência)
# -------------------------

def trial_book(state: GlobalState, *, booking_repo: Any) -> GlobalState:
    """
    booking_repo esperado:
      - create_trial_booking(client_id, nome, idade, nivel, desired_date, desired_time) -> booking_id
    """
    trial = ensure_trial_defaults(state)

    if trial.get("booking_created"):
        trial["stage"] = "booked"
        fallback = (
            f"Seu agendamento já está registrado ✅ Terça {trial.get('desired_date')} às {trial.get('desired_time')}."
        )
        trial["output"] = fallback
        return export_trial_output(state)

    if booking_repo is None:
        # Modo dev: não quebra o fluxo se ainda não plugou DB
        trial["stage"] = "booked"
        trial["booking_created"] = True
        trial["booking_id"] = "dev_booking"
        fallback = (
            f"(DEV) Agendado ✅ Te espero na terça {trial.get('desired_date')} às {trial.get('desired_time')}!"
        )
        trial["output"] = fallback
        return export_trial_output(state)

    booking_id = booking_repo.create_trial_booking(
        client_id=state.get("client_id"),
        nome=trial.get("nome"),
        idade=trial.get("idade"),
        nivel=trial.get("nivel"),
        desired_date=trial.get("desired_date"),
        desired_time=trial.get("desired_time"),
    )

    trial["booking_id"] = booking_id
    trial["booking_created"] = True
    trial["stage"] = "booked"
    trial["output"] = f"Agendado ✅ Te espero na terça {trial['desired_date']} às {trial['desired_time']}!"
    return export_trial_output(state)


# -------------------------
# Nó 5: Handoff
# -------------------------

def trial_handoff(state: GlobalState) -> GlobalState:
    trial = ensure_trial_defaults(state)
    trial["stage"] = "handoff_needed"
    fallback = "Vou chamar um atendente humano para te ajudar melhor."
    trial["output"] = fallback
    return export_trial_output(state)
