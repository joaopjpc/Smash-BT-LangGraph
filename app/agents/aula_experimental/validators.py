"""
validators.py — Regras determinísticas de negócio e integridade do fluxo

Este módulo implementa validações 100% determinísticas para garantir que os dados extraídos
pelo LLM respeitam as regras reais do CT Smash Beach Tennis.

Importante:
- Mesmo com Structured Output, o LLM pode devolver valores inválidos, ambíguos ou fora da regra.
- Por isso, a validação do negócio deve ser feita por código (guard rails), não pelo modelo.

Exemplos de regras típicas aqui:
- desired_date deve ser uma terça-feira.
- desired_date deve estar em formato ISO (YYYY-MM-DD).
- desired_time deve estar em formato HH:MM (24h) e ser válido.
- Campos obrigatórios para avançar de etapa:
  - no stage de data/hora: desired_date/desired_time válidos

O que este módulo NÃO faz:
- Não chama LLM.
- Não interpreta texto do cliente.
- Não altera state diretamente.
Ele apenas retorna um resultado de validação (ok/erro) que os nós usam para decidir:
- perguntar novamente,
- corrigir o stage,
- ou avançar o fluxo.

Resultado:
- Fluxo mais robusto, repetível e seguro para produção.
"""


from __future__ import annotations
from datetime import date
from typing import Optional, Tuple
from pydantic import BaseModel
import datetime as dt

class ValidationResult(BaseModel):
    ok: bool
    error: Optional[str] = None

def is_iso_date(s: str) -> bool:
    try:
        dt.date.fromisoformat(s)
        return True
    except Exception:
        return False

def is_iso_time_hhmm(s: str) -> bool:
    try:
        dt.time.fromisoformat(s)
        return True
    except Exception:
        return False

def is_tuesday(iso_date: str) -> bool:
    d = dt.date.fromisoformat(iso_date)
    return d.weekday() == 1  # terça

def validate_date_time(desired_date: Optional[str], desired_time: Optional[str]) -> ValidationResult:
    if desired_date is None:
        return ValidationResult(ok=False, error="missing_date")
    if not is_iso_date(desired_date):
        return ValidationResult(ok=False, error="invalid_date_format")
    if not is_tuesday(desired_date):
        return ValidationResult(ok=False, error="not_tuesday")

    if desired_time is None:
        return ValidationResult(ok=False, error="missing_time")
    if not is_iso_time_hhmm(desired_time):
        return ValidationResult(ok=False, error="invalid_time_format")

    return ValidationResult(ok=True)
