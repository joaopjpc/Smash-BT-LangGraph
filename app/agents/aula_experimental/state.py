from typing import Optional, TypedDict, Literal

Nivel = Literal["iniciante", "intermediario", "avancado"]


class TrialState(TypedDict, total=False):
    # --- controle do fluxo ---
    stage: Literal[
        "collect_client_info",      # solicita infos do cliente
        "ask_tuesday",              # pergunta qual terça o aluno quer
        "awaiting_confirmation",    # recebe confirmação do cliente quando pergunta "confirma?"
        "booked",                    # marca aula experimental (feito)
        "handoff_needed"            # handoff para humano
    ]

    # --- infos do cliente ---
    nome: Optional[str]
    idade: Optional[int]
    nivel: Optional[Nivel]

    # --- escolha da terça-feira ---
    desired_date: Optional[str]              # "YYYY-MM-DD" (terça escolhida)
    desired_time: Optional[str]              # "HH:MM" (horário escolhido)

    # --- confirmação ---
    confirmed: Optional[bool]                # true/false após resposta do cliente

    # --- persistência ---
    booking_id: Optional[str]                # id da reserva no DB (uuid/int str)
    booking_created: bool                    # idempotência (não duplicar)

    # handoff (sem emergencial)
    handoff_requested: bool

    # --- saída do especialista (pra merge) ---
    output: Optional[str]                    # mensagem pronta do agente de aula experimental
