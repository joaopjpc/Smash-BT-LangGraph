"""
eval_trial.py — Testes de conversa do workflow de Aula Experimental via LangSmith.

Cria um dataset de cenários multi-turno, roda cada cenário contra o grafo
compilado (com chamadas reais ao GPT), e registra os resultados no LangSmith.

Uso:
    python tests/eval_trial.py

Requisitos:
    - OPENAI_API_KEY (chamadas reais ao GPT)
    - LANGSMITH_API_KEY (registrar dataset + resultados)
    - Sem DATABASE_URL → booking roda em modo dev (simulado)

Resultados em: smith.langchain.com → Datasets & Experiments
"""

from __future__ import annotations

import os
import sys

# Garante que o projeto está no path (para rodar de qualquer diretório)
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dotenv import load_dotenv
load_dotenv()

from langsmith import Client
from langsmith.evaluation import evaluate
from langchain_core.messages import HumanMessage, AIMessage

from app.agents.aula_experimental.workflow import build_trial_graph


# ═══════════════════════════════════════════════════════════════
# 1. DATASET — Cenários de conversa multi-turno
# ═══════════════════════════════════════════════════════════════

DATASET_NAME = "trial-workflow-tests"
DATASET_DESCRIPTION = "Cenários de conversa para o workflow de Aula Experimental do CT Smash"

SCENARIOS = [
    # ---- 1. Happy path completo ----
    {
        "inputs": {
            "turns": [
                "Oi, quero marcar uma aula experimental. Me chamo João, tenho 25 anos e sou iniciante",
                "Terça que vem às 9h",
                "Sim, confirmo",
            ]
        },
        "outputs": {
            "expected_final_stage": "booked",
            "expected_stages": ["ask_date", "awaiting_confirmation", "booked"],
            "expected_fields": {"nome": "João", "booking_created": True},
            "expected_fields_absent": [],
        },
        "metadata": {"scenario": "happy_path"},
    },

    # ---- 2. Coleta incremental (dados em turnos separados) ----
    {
        "inputs": {
            "turns": [
                "Oi, quero marcar uma aula",
                "Me chamo Ana, tenho 30 anos e sou intermediária",
            ]
        },
        "outputs": {
            "expected_final_stage": "ask_date",
            "expected_stages": ["collect_client_info", "ask_date"],
            "expected_fields": {"nome": "Ana", "idade": 30, "nivel": "intermediario"},
            "expected_fields_absent": [],
        },
        "metadata": {"scenario": "incremental_collect"},
    },

    # ---- 3. BUG REGRESSION: quinta às 9h (data inválida não deve persistir horário) ----
    # 3 turnos: garante que coleta termina antes de testar a data inválida
    {
        "inputs": {
            "turns": [
                "Oi, quero marcar aula experimental",
                "Me chamo Carlos, tenho 20 anos e nunca joguei",
                "Quinta que vem às 9h",
            ]
        },
        "outputs": {
            "expected_final_stage": "ask_date",
            "expected_stages": ["collect_client_info", "ask_date", "ask_date"],
            "expected_fields": {"nome": "Carlos"},
            "expected_fields_absent": ["desired_time"],
        },
        "metadata": {"scenario": "bug_regression_quinta_9h"},
    },

    # ---- 4. Horário fora do range ----
    {
        "inputs": {
            "turns": [
                "Sou Maria, 28, avançada",
                "Terça que vem às 19h",
            ]
        },
        "outputs": {
            "expected_final_stage": "ask_date",
            "expected_stages": ["ask_date", "ask_date"],
            "expected_fields": {},
            "expected_fields_absent": ["desired_time"],
        },
        "metadata": {"scenario": "time_out_of_range"},
    },

    # ---- 5. Cancelamento ----
    {
        "inputs": {
            "turns": [
                "Quero marcar uma aula experimental",
                "Sabe, deixa pra lá, não quero mais",
            ]
        },
        "outputs": {
            "expected_final_stage": "cancelled",
            "expected_stages": ["collect_client_info", "cancelled"],
            "expected_fields": {},
            "expected_fields_absent": [],
        },
        "metadata": {"scenario": "cancellation"},
    },

    # ---- 6. Rejeição de confirmação → nova data → confirma ----
    {
        "inputs": {
            "turns": [
                "Sou Pedro, 35, intermediário",
                "Terça que vem às 9h",
                "Não, quero outro horário",
                "Terça que vem às 15h",
                "Sim, confirmo",
            ]
        },
        "outputs": {
            "expected_final_stage": "booked",
            "expected_stages": [
                "ask_date",
                "awaiting_confirmation",
                "ask_date",
                "awaiting_confirmation",
                "booked",
            ],
            "expected_fields": {"nome": "Pedro", "booking_created": True},
            "expected_fields_absent": [],
        },
        "metadata": {"scenario": "rejection_then_rebook"},
    },

    # ---- 7. Tudo em uma mensagem (nome+idade+nivel) → data/horário no próximo turno ----
    # O grafo roda 1 nó por invocação: collect_client_info extrai dados pessoais e avança pra ask_date.
    # A data/horário só é processada no turno seguinte por trial_ask_date.
    {
        "inputs": {
            "turns": [
                "Sou Lucas, 22, iniciante, quero terça que vem às 14h",
                "Terça que vem às 14h",
            ]
        },
        "outputs": {
            "expected_final_stage": "awaiting_confirmation",
            "expected_stages": ["ask_date", "awaiting_confirmation"],
            "expected_fields": {"nome": "Lucas", "desired_time": "14:00"},
            "expected_fields_absent": [],
        },
        "metadata": {"scenario": "all_in_one_then_date"},
    },
]


# ═══════════════════════════════════════════════════════════════
# 2. TARGET — Função que roda a conversa no grafo
# ═══════════════════════════════════════════════════════════════

def run_conversation(inputs: dict) -> dict:
    """
    Recebe {"turns": ["msg1", "msg2", ...]} e roda cada turno
    sequencialmente no grafo compilado. Retorna o estado final.
    """
    graph = build_trial_graph({"configurable": {}})
    state = {"client_input": "", "messages": []}
    stages = []
    trial = {}

    for turn_text in inputs["turns"]:
        state["client_input"] = turn_text
        result = graph.invoke(state)

        trial = result.get("trial", {})
        stages.append(trial.get("stage"))
        bot_output = trial.get("output", "")

        # Reconstroi state para próximo turno, acumulando mensagens
        # (o extractor usa messages para contexto de desambiguação)
        msgs = list(result.get("messages") or [])
        msgs.append(HumanMessage(content=turn_text))
        msgs.append(AIMessage(content=bot_output))
        state = dict(result)
        state["messages"] = msgs

    return {
        "final_stage": trial.get("stage"),
        "stages": stages,
        "trial": {k: v for k, v in trial.items() if k != "output"},
        "last_output": trial.get("output", ""),
    }


# ═══════════════════════════════════════════════════════════════
# 3. EVALUATORS — Checam os resultados contra o esperado
# ═══════════════════════════════════════════════════════════════

def correct_final_stage(inputs, outputs, reference_outputs) -> dict:
    """O stage final do trial é o esperado?"""
    actual = outputs.get("final_stage")
    expected = reference_outputs.get("expected_final_stage")
    return {
        "key": "correct_final_stage",
        "score": 1.0 if actual == expected else 0.0,
        "comment": f"actual={actual}, expected={expected}",
    }


def correct_stage_sequence(inputs, outputs, reference_outputs) -> dict:
    """A sequência de stages ao longo dos turnos é a esperada?"""
    actual = outputs.get("stages", [])
    expected = reference_outputs.get("expected_stages", [])
    return {
        "key": "correct_stage_sequence",
        "score": 1.0 if actual == expected else 0.0,
        "comment": f"actual={actual}, expected={expected}",
    }


def expected_fields_match(inputs, outputs, reference_outputs) -> dict:
    """Os campos esperados existem no trial com os valores corretos?"""
    trial = outputs.get("trial", {})
    expected = reference_outputs.get("expected_fields", {})
    if not expected:
        return {"key": "expected_fields_match", "score": 1.0, "comment": "no fields to check"}

    mismatches = []
    for k, v in expected.items():
        actual_val = trial.get(k)
        if actual_val != v:
            mismatches.append(f"{k}: actual={actual_val}, expected={v}")

    return {
        "key": "expected_fields_match",
        "score": 1.0 if not mismatches else 0.0,
        "comment": "; ".join(mismatches) if mismatches else "all fields match",
    }


def fields_absent(inputs, outputs, reference_outputs) -> dict:
    """Campos que NÃO devem existir estão de fato ausentes?"""
    trial = outputs.get("trial", {})
    absent_fields = reference_outputs.get("expected_fields_absent", [])
    if not absent_fields:
        return {"key": "fields_absent", "score": 1.0, "comment": "no absence check needed"}

    present = [f for f in absent_fields if trial.get(f) is not None]
    return {
        "key": "fields_absent",
        "score": 1.0 if not present else 0.0,
        "comment": f"should be absent but found: {present}" if present else "all absent as expected",
    }


# ═══════════════════════════════════════════════════════════════
# 4. MAIN — Cria dataset (se não existir) e roda evaluate()
# ═══════════════════════════════════════════════════════════════

def create_or_get_dataset(client: Client) -> str:
    """Cria o dataset no LangSmith ou retorna o existente."""
    # Verifica se já existe
    for ds in client.list_datasets():
        if ds.name == DATASET_NAME:
            print(f"Dataset '{DATASET_NAME}' já existe (id={ds.id}). Recriando exemplos...")
            # Deleta exemplos antigos para recriar com cenários atualizados
            for example in client.list_examples(dataset_id=ds.id):
                client.delete_example(example.id)
            dataset_id = ds.id
            break
    else:
        dataset = client.create_dataset(
            dataset_name=DATASET_NAME,
            description=DATASET_DESCRIPTION,
        )
        dataset_id = dataset.id
        print(f"Dataset '{DATASET_NAME}' criado (id={dataset_id})")

    # Cria exemplos
    client.create_examples(
        dataset_id=dataset_id,
        inputs=[s["inputs"] for s in SCENARIOS],
        outputs=[s["outputs"] for s in SCENARIOS],
        metadata=[s.get("metadata", {}) for s in SCENARIOS],
    )
    print(f"{len(SCENARIOS)} cenários adicionados ao dataset")
    return DATASET_NAME


def main():
    # Validações de ambiente
    if not os.getenv("OPENAI_API_KEY"):
        print("ERRO: OPENAI_API_KEY não definida")
        sys.exit(1)
    if not os.getenv("LANGSMITH_API_KEY"):
        print("ERRO: LANGSMITH_API_KEY não definida")
        sys.exit(1)

    # Garante tracing ativo
    os.environ.setdefault("LANGCHAIN_TRACING_V2", "true")
    os.environ.setdefault("LANGCHAIN_PROJECT", "trial-workflow-eval")

    client = Client()
    dataset_name = create_or_get_dataset(client)

    print(f"\nRodando evaluate() contra '{dataset_name}'...")
    print("(cada cenário faz chamadas reais ao GPT — pode demorar)\n")

    results = evaluate(
        run_conversation,
        data=dataset_name,
        evaluators=[
            correct_final_stage,
            correct_stage_sequence,
            expected_fields_match,
            fields_absent,
        ],
        experiment_prefix="trial-eval",
        description="Avaliação do workflow de Aula Experimental",
        max_concurrency=1,  # sequencial para evitar rate limits
    )

    # Resumo no terminal
    print("\n" + "=" * 60)
    print("RESULTADOS")
    print("=" * 60)

    for result in results:
        try:
            # result é TypedDict com keys: run, example, evaluation_results
            example = result["example"]              # langsmith.schemas.Example (Pydantic)
            scenario = (example.metadata or {}).get("scenario", "?")

            eval_results = result["evaluation_results"]  # TypedDict com key "results"
            raw_results = eval_results["results"]        # list[EvaluationResult]
            scores = {e.key: e.score for e in raw_results}
            all_pass = all(s == 1.0 for s in scores.values() if s is not None)
            status = "PASS" if all_pass else "FAIL"
            print(f"  [{status}] {scenario}: {scores}")
        except Exception as e:
            print(f"  [?] erro ao ler resultado: {e}")

    print(f"\nDetalhes completos em: https://smith.langchain.com")
    print(f"Projeto: trial-workflow-eval")


if __name__ == "__main__":
    main()
