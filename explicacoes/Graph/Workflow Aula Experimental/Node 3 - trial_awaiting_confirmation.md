# Nó 3 — Confirmação do Agendamento (`trial_awaiting_confirmation`)

Este nó é responsável por confirmar (ou não) o agendamento da aula experimental com o cliente. Ele só é alcançado quando o Nó 2 (`trial_ask_date`) já validou que a data é uma terça-feira e o horário está em formato correto.

## 🎯 Objetivo do Nó
Capturar a resposta de confirmação do cliente:
- `confirmed = True` — cliente confirmou, avança para booking
- `confirmed = False` — cliente recusou, volta para escolher nova data/horário
- `confirmed = None` — resposta ambígua, pergunta novamente

## 🧠 Estratégia Geral
O nó segue o padrão do subgrafo, mas sem etapa de validação determinística — a decisão é baseada apenas no valor booleano extraído pelo LLM:

1. Garante a existência do estado `trial`
2. Usa LLM com Structured Output para extração (nenhuma heurística)
3. Faz merge seguro, sem apagar dados já coletados
4. Decide o próximo `stage` com base em `confirmed`
5. Define a mensagem do turno em `trial.output`
6. Exporta a saída para `specialists_outputs`

> **Diferença dos Nós 1 e 2:** Não usa `validators.py`. A decisão é um simples tristate (`True`, `False`, `None`) extraído pelo LLM via Structured Output.

## 🔁 Fluxo Detalhado

### 1️⃣ Garantia do Estado (`ensure_trial_defaults`)

Antes de qualquer lógica, o nó garante que o estado `trial` exista no `GlobalState`.

Defaults mínimos definidos:

```python
trial.setdefault("stage", "collect_client_info")
trial.setdefault("booking_created", False)
trial.setdefault("handoff_requested", False)
trial.setdefault("output", None)
```

Neste ponto, o trial já contém `nome`, `idade`, `nivel`, `desired_date` e `desired_time` preenchidos pelos Nós 1 e 2.

### 2️⃣ Extração de dados via LLM (`extract_trial_fields`)

O texto do cliente (`state["client_input"]`) é enviado ao extractor:

```python
extract_trial_fields(
    llm,
    client_text=text,
    stage="awaiting_confirmation",
    trial_snapshot=trial,
)
```

O retorno é um objeto estruturado `TrialExtraction`. Neste estágio, o campo relevante é `confirmed`:

```python
# Cliente disse "sim, pode agendar"
TrialExtraction(
    nome=None,
    idade=None,
    nivel=None,
    desired_date=None,
    desired_time=None,
    confirmed=True             # ← campo relevante neste nó
)

# Cliente disse "não, quero outra data"
TrialExtraction(
    ...
    confirmed=False
)

# Cliente disse algo ambíguo como "hmm, deixa eu pensar"
TrialExtraction(
    ...
    confirmed=None             # LLM não conseguiu determinar
)
```

### 3️⃣ Merge Seguro no Estado (`merge_trial`)

Os dados extraídos são mesclados ao estado Trial com as mesmas regras:

- Apenas campos pertencentes ao TrialState
- Apenas valores não nulos
- Nunca apaga dados já coletados

Depois do merge, o trial contém:

```python
trial = {
    "nome": "João",              # preservado do Nó 1
    "idade": 27,                 # preservado do Nó 1
    "nivel": "iniciante",        # preservado do Nó 1
    "desired_date": "2026-02-10",  # preservado do Nó 2
    "desired_time": "19:00",       # preservado do Nó 2
    "confirmed": True,             # ← novo (do extractor)
    ...
}
```

### 3b. Verificação de Cancelamento (`_check_cancellation`)

Logo após o merge, o nó verifica se o cliente quer cancelar o agendamento:

```python
cancelled = _check_cancellation(trial, state)
if cancelled:
    return cancelled
```

Se `wants_to_cancel == True`:
- Seta `trial["stage"] = "cancelled"`
- Gera mensagem de despedida via NLG (action: `cancel_confirmed`)
- Retorna imediatamente — nenhuma lógica de confirmação executa

**Importante:** `wants_to_cancel` tem prioridade sobre `confirmed`. Se o cliente disser "desisto de tudo", não importa se `confirmed` é True/False/None — o cancelamento prevalece porque é checado primeiro.

Se `wants_to_cancel` é None/False, o fluxo continua normalmente.

### 4️⃣ Decisão com base em `confirmed`

O nó lê o valor de `confirmed` do trial e segue um dos três caminhos:

```python
conf = trial.get("confirmed")
```

## 🧭 Caminhos de Decisão do Nó

### 🟡 Caso 4.1 — Resposta ambígua (`confirmed is None`)

Quando o LLM não conseguiu determinar se o cliente confirmou ou não:

1. Mantém o estágio como `awaiting_confirmation`:
```python
trial["stage"] = "awaiting_confirmation"
```

2. Tenta gerar uma mensagem via NLG com fallback:
```python
trial["output"] = _fallback_or_nlg(
    stage="awaiting_confirmation",
    action="ask_confirmation",
    ...
    fallback="Só pra confirmar: sim ou não?",
)
```

3. Exporta a resposta para `state["specialists_outputs"]["trial"]`.

> **Exemplo:** Cliente disse "hmm, acho que sim" — o LLM pode não ter certeza e retornar `None`. O bot pede uma confirmação direta.

### 🔴 Caso 4.2 — Cliente recusou (`confirmed is False`)

Quando o cliente disse algo como "não", "quero outra data", "mudei de ideia":

1. **Volta** o estágio para `ask_date`:
```python
trial["stage"] = "ask_date"
```

2. Gera mensagem convidando a escolher nova data/horário:
```python
trial["output"] = _fallback_or_nlg(
    stage="ask_date",
    action="ask_date_time",
    ...
    fallback="Sem problemas. Qual terça e horário você prefere então?",
)
```

3. Exporta a resposta para o estado global.

> **Nota:** Ao voltar para `ask_date`, os dados de `desired_date` e `desired_time` ainda estão no trial. Na próxima interação, o Nó 2 vai extrair os novos valores e o `merge_trial` vai sobrescrevê-los (porque virão não-nulos do extractor).

### 🟢 Caso 4.3 — Cliente confirmou (`confirmed is True`)

Quando o cliente confirmou o agendamento:

1. Avança o estágio para `book`:
```python
trial["stage"] = "book"
```

2. Gera mensagem informando que vai registrar:
```python
trial["output"] = _fallback_or_nlg(
    stage="book",
    action="book_start",
    ...
    fallback="Perfeito! Vou registrar seu agendamento agora.",
)
```

3. Exporta a saída para o estado global.

> **Importante:** Este nó não faz o booking — ele apenas seta `stage = "book"`. O booking real acontece no Nó 4 (`trial_book`), que é acionado na próxima execução do grafo via `after_confirm_route`.

## 📤 Saída do Nó

Ao final da execução, este nó sempre garante:

- `trial.stage` corretamente definido (`awaiting_confirmation`, `ask_date` ou `book`)
- `trial.output` preenchido com a mensagem do turno
- Dados do cliente e data/horário preservados no trial
- Mensagem disponível em:
```python
state["specialists_outputs"]["trial"]
```

Essa saída será utilizada pelo nó `merge` para compor a resposta final ao usuário.

## 🔄 Cenário: Confirmação após recusa

O fluxo suporta o cliente mudar de ideia e voltar:

```
Bot: "Confirma sua aula na terça 2026-02-10 às 19:00? (sim/não)"

Mensagem 1: "não, quero outro horário"
  → extractor: confirmed=False
  → stage volta para "ask_date"
  → bot: "Sem problemas. Qual terça e horário você prefere então?"

Mensagem 2: "pode ser às 18:00 mesmo dia"
  → Nó 2 (ask_date): desired_time="18:00", desired_date preservado
  → validator: ok=True ✅
  → stage avança para "awaiting_confirmation"
  → bot: "Confirma na terça 2026-02-10 às 18:00? (sim/não)"

Mensagem 3: "sim!"
  → Nó 3 (awaiting_confirmation): confirmed=True
  → stage avança para "book"
  → bot: "Perfeito! Vou registrar seu agendamento agora."
```
