"""
datetime_utils.py — Utilitários de data/hora compartilhados entre agentes.

Fornece contexto temporal (dia da semana, data atual, próximas terças)
para qualquer módulo que precise: extractor, NLG, validators, etc.
"""

from __future__ import annotations

from datetime import datetime, timedelta

DIAS_SEMANA = [
    "segunda-feira", "terça-feira", "quarta-feira",
    "quinta-feira", "sexta-feira", "sábado", "domingo",
]


def get_current_context() -> dict:
    """
    Retorna dict com contexto temporal completo:
    - now_iso: "2025-02-11T19:30" (referência)
    - weekday: "terça-feira"
    - today_ddmm: "11-02"
    - next_tuesdays: ["11-02", "18-02", "25-02", "04-03"]
    """
    now = datetime.now()
    return {
        "now_iso": now.isoformat(timespec="minutes"),
        "weekday": DIAS_SEMANA[now.weekday()],
        "today_ddmm": f"{now.day:02d}-{now.month:02d}",
        "next_tuesdays": _next_tuesdays(4),
    }


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
