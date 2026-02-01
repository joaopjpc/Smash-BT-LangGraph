
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
from datetime import datetime
from app.agents.aula_experimental.schemas import TrialExtraction
from app.agents.aula_experimental.prompts import TRIAL_EXTRACT_SYSTEM

# Função para construir o prompt do usuário informando o contexto atual (stage atual, snapshot do trial, texto do cliente)
def build_extract_user_prompt(*, client_text: str, stage: str, trial_snapshot: dict, now_iso: str) -> str:
    return f"""
Data/hora atual (referência): {now_iso}

Etapa do fluxo (stage): {stage} 

Estado atual conhecido (trial_snapshot):
{trial_snapshot}

Mensagem do cliente:
{client_text}

Extraia somente o que estiver na mensagem do cliente.
"""

# Função principal de extração usando LLM e schema definido  
def extract_trial_fields(llm, *, client_text: str, stage: str, trial_snapshot: dict) -> TrialExtraction:
    now_iso = datetime.now().isoformat(timespec="minutes")
    user_prompt = build_extract_user_prompt(
        client_text=client_text,
        stage=stage,
        trial_snapshot=trial_snapshot,
        now_iso=now_iso,
    )

    # Padrão structured output
    extractor = llm.with_structured_output(TrialExtraction)  # se disponível no seu wrapper
    return extractor.invoke([
        {"role": "system", "content": TRIAL_EXTRACT_SYSTEM},
        {"role": "user", "content": user_prompt},
    ])
