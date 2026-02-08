"""
booking.py — Persistência de agendamento de aula experimental.

Chamado diretamente pelo nó trial_book (nodes.py).

O que faz:
- Combina desired_date (dd-mm) e desired_time (HH:MM) em um único
  datetime para gravar na coluna desired_datetime (timestamptz) do banco.
- Insere uma linha em trial_class_booking e retorna o booking_id (uuid).

O que NÃO faz:
- Não valida regras de negócio (isso é responsabilidade do validators.py).
- Não decide fluxo (isso é responsabilidade dos nós).
"""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import text

from app.tools.database import get_session


def create_trial_booking(
    *,
    customer_id: str,
    desired_date: str,
    desired_time: str,
) -> str:
    """
    Persiste agendamento de aula experimental no banco.

    Args:
        customer_id: ID do cliente (referência customer.id).
        desired_date: Data no formato dd-mm (dia-mês, ano assumido como atual).
        desired_time: Horário no formato HH:MM.

    Returns:
        booking_id: UUID (string) da reserva criada.
    """
    day, month = desired_date.split("-")
    year = datetime.now().year
    hour, minute = desired_time.split(":")
    desired_datetime = datetime(year, int(month), int(day), int(hour), int(minute))
    booking_id = str(uuid.uuid4())

    with get_session() as session:
        session.execute(
            text("""
                INSERT INTO trial_class_booking (id, customer_id, desired_datetime, status)
                VALUES (:id, :customer_id, :desired_datetime, 'pending')
            """),
            {
                "id": booking_id,
                "customer_id": customer_id,
                "desired_datetime": desired_datetime,
            },
        )

    return booking_id
