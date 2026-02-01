"""
schemas.py — Contratos de dados (Structured Output) do fluxo de Aula Experimental

Este módulo define os *schemas* (Pydantic) que servem como contrato formal entre:
1) a mensagem do cliente (texto livre) e
2) o estado do fluxo de agendamento (TrialState).

A ideia é que o LLM NÃO "responda texto": ele deve retornar dados estruturados, validados
por Pydantic, seguindo este schema. Isso evita heurísticas (regex/parsing manual) e dá
previsibilidade para a automação.

Princípios:
- Tudo é opcional: o LLM só preenche campos quando a informação estiver explícita.
- Não inventar: se não tiver certeza, o campo deve ser null/None.
- Normalização:
  - desired_date deve ser YYYY-MM-DD
  - desired_time deve ser HH:MM (24h)
- confirmed:
  - true para confirmação clara (sim / confirmo / pode marcar)
  - false para negação clara (não / cancela)
  - None se estiver ambíguo.

Este schema é usado pelos nós do subgrafo (collect_client_info, ask_date, confirmation)
para preencher slots progressivamente e avançar o stage com segurança.
"""

from __future__ import annotations
from pydantic import BaseModel, Field
from typing import Literal, Optional

Nivel = Literal["iniciante", "intermediario", "avancado"]

#--- Modelo de extração de campos da mensagem do cliente --- *contrato do que o LLM pode retornar
class TrialExtraction(BaseModel):
    # Dados do aluno
    nome: Optional[str] = Field(default=None, description="Nome do aluno, se mencionado.")
    idade: Optional[int] = Field(default=None, description="Idade em anos, se mencionada.")
    nivel: Optional[Nivel] = Field(default=None, description="Nível do aluno.")

    # Data/hora (normalizados)
    desired_date: Optional[str] = Field(default=None, description="Data no formato YYYY-MM-DD.")
    desired_time: Optional[str] = Field(default=None, description="Horário no formato HH:MM (24h).")

    # Confirmação (apenas quando usuário respondeu sim/não)
    confirmed: Optional[bool] = Field(default=None, description="true para sim, false para não, null se não ficou claro.")
