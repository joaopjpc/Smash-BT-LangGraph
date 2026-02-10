# No Triage — Classificacao de Intencao

O triage é o primeiro no do grafo core após o `input_node`. Ele recebe o texto do cliente e decide pra qual(is) especialista(s) rotear.

## Posicao no Grafo

```
input_node → triage → [route_after_triage] → trial / faq → merge → END
                                          → (general) ────→ merge → END
```

## O que o Triage faz

1. Le `client_input` do estado global
2. Verifica se ha conversa ativa com algum especialista (ex: `trial.stage`)
3. Chama LLM com structured output pra classificar a intencao
4. Escreve `active_routes` no estado — o grafo usa isso pra rotear

## Categorias de Intencao

| Categoria | Descricao | Exemplo |
|---|---|---|
| `trial` | Cliente quer agendar aula experimental | "quero marcar uma aula teste" |
| `faq` | Cliente tem duvida sobre a CT | "onde fica a CT?", "quais os horarios?" |
| `general` | Saudacoes, agradecimentos, fora de contexto | "oi", "obrigado", "tchau" |

## Multi-Intent

O triage pode classificar multiplas intencoes ao mesmo tempo:

```
"quero agendar e onde fica a CT?" → intents: ["trial", "faq"]
```

Quando isso acontece, o `route_after_triage` usa `Send()` pra executar os dois especialistas em paralelo. Ambos escrevem em `specialists_outputs` com keys diferentes (`"trial"`, `"faq"`), e o merge combina as respostas.

Regra: `"general"` sempre aparece sozinho, nunca junto com `trial` ou `faq`.

## Schema de Classificacao (TriageResult)

```python
class TriageResult(BaseModel):
    intents: List[Literal["trial", "faq", "general"]]
    general_response: Optional[str] = None
```

- `intents`: lista de categorias detectadas (pode ter mais de uma)
- `general_response`: preenchido pelo LLM somente quando `"general"` esta em intents. Contem uma resposta curta e amigavel.

## Contexto de Conversa Ativa

Problema: se o cliente esta no meio de um agendamento (trial) e manda "sim" ou "19:00", sem contexto o LLM classificaria como `"general"`. Mas na verdade e uma resposta pro trial.

Solucao: o triage verifica `trial.stage` no estado (persistido pelo checkpointer). Se ha conversa ativa, passa essa informacao no prompt:

```python
active_context = None
if stage and stage != "booked":
    active_context = f"Cliente esta no meio de um agendamento de aula experimental (etapa: {stage})"
```

O LLM recebe:

```
[CONTEXTO: Cliente esta no meio de um agendamento de aula experimental (etapa: ask_date)]

ultima mensagem do cliente: sim
```

Com isso, o LLM sabe que "sim" e continuacao do agendamento e classifica como `["trial"]`.

### Flexibilidade

O contexto NAO engessa o roteamento. Mesmo mid-trial:

| Mensagem | Classificacao | Por que |
|---|---|---|
| "sim" | `["trial"]` | Resposta ao agendamento em curso |
| "19:00" | `["trial"]` | Horario pro agendamento |
| "onde fica a CT?" | `["faq"]` | Claramente nao e sobre o agendamento |
| "sim, e onde fica?" | `["trial", "faq"]` | Confirmacao + duvida — ambos rodam |

## Fluxo de Decisao

```
triage recebe client_input
    │
    ├─ trial.stage existe e != "booked"?
    │     sim → monta active_context com a etapa atual
    │     nao → active_context = None
    │
    ├─ chama _classify_intent(text, active_context)
    │     └─ LLM retorna TriageResult(intents=[...], general_response=...)
    │
    ├─ "general" em intents?
    │     sim → escreve resposta em specialists_outputs["triage"]
    │           seta active_routes = ["general"]
    │           (merge recebe e repassa)
    │
    │     nao → seta active_routes = result.intents
    │           (route_after_triage envia pros especialistas)
```

## O que o Triage escreve no Estado

O triage retorna um dict parcial (padrao LangGraph — so retorna o que mudou, framework faz o merge):

**Caso general:**
```python
return {
    "active_routes": ["general"],
    "specialists_outputs": {"triage": response},
}
```

**Caso trial/faq:**
```python
return {"active_routes": ["trial"]}
# ou: {"active_routes": ["trial", "faq"]}
```

### active_routes

- Tipo: `List[str]` (sem reducer — sobrescreve a cada turno)
- E um sinal transiente: so importa no turno atual
- Lido por `route_after_triage` no `graph.py` pra decidir o roteamento
- Nao acumula entre turnos — cada turno o triage decide de novo

### specialists_outputs

- Tipo: `Dict[str, str]` com reducer `operator.or_` (merge de dicts)
- Triage so escreve nele no caso `"general"` (key `"triage"`)
- Nos outros casos, quem escreve sao os especialistas (key `"trial"`, `"faq"`, etc)

## Roteamento (route_after_triage)

O triage nao roteia diretamente — ele seta `active_routes` e a funcao `route_after_triage` no `graph.py` faz o roteamento:

```python
def route_after_triage(state):
    routes = state.get("active_routes", [])
    if not routes or routes == ["general"]:
        return [Send("merge", state)]       # vai direto pro merge
    return [Send(route, state) for route in routes]  # Send("trial"), Send("faq"), etc
```

`Send()` permite execucao paralela. Se `active_routes = ["trial", "faq"]`, ambos rodam ao mesmo tempo.

## Chamada LLM

Uma unica chamada por turno via `_classify_intent()`:

```python
def _classify_intent(text, active_context=None):
    llm = get_llm()
    classifier = llm.with_structured_output(TriageResult)
    # monta user_content com ou sem [CONTEXTO]
    return classifier.invoke([system_prompt, user_content])
```

- Usa structured output (Pydantic) — LLM retorna `TriageResult` validado
- No caso `"general"`, a mesma chamada ja gera a resposta (`general_response`)
- Fallback se `general_response` vier None: `"Ola! Sou o assistente da CT Smash. Como posso te ajudar?"`

## Relacao com o Checkpointer

O triage NAO persiste nada proprio — usa dados que ja estao no estado:

- `client_input`: setado pelo `input_node` no mesmo turno
- `trial.stage`: persistido pelo checkpointer entre turnos
- `active_routes`: transiente, sobrescrito a cada turno

O checkpointer garante que `trial.stage` sobrevive entre turnos. Quando `trial.stage = "booked"`, o triage para de passar contexto ativo e volta a classificar normalmente.

## Arquivo

`app/core/triage.py`
