# Fluxo Completo — Workflow Aula Experimental

Simulação turno a turno com **todas** as funções, nós e mudanças no state.

---

## Estado Inicial

```python
state = {
    "client_id": "teste_001",
    "client_input": "",
    "trial": {},                    # vazio — primeira interação
    "specialists_outputs": {},
}
```

---

## TURNO 1 — Cliente diz "Oi"

**Input:** `"Oi, quero marcar uma aula experimental."`

### 1. Entrada no grafo

```python
state["client_input"] = "Oi, quero marcar uma aula experimental."
graph.invoke(state)
```

### 2. Nó: `trial_router` (workflow.py)

- Chama `ensure_trial_defaults(state)` → como `trial` está vazio, seta defaults:
  ```python
  trial = {
      "stage": "collect_client_info",   # DEFAULT_STAGE
      "booking_created": False,
      "handoff_requested": False,
      "output": None,
  }
  ```
- Retorna `state` sem alteração (nó passivo).

### 3. Roteamento: `trial_route(state)`

- Lê `trial["stage"]` → `"collect_client_info"`
- Consulta `stage_to_node` → retorna `"trial_collect_client_info"`
- **Próximo nó:** `trial_collect_client_info`

### 4. Nó: `trial_collect_client_info`

**4a. ensure_trial_defaults(state)**
- trial já existe, `.setdefault()` não muda nada.

**4b. Lê input do cliente**
```python
text = state.get("client_input", "")  # "Oi, quero marcar uma aula experimental."
```

**4c. extract_trial_fields (extractor.py)**
- Monta prompt com:
  - `stage = "collect_client_info"`
  - `trial_snapshot = {"stage": "collect_client_info", "booking_created": False, ...}`
  - `client_text = "Oi, quero marcar uma aula experimental."`
  - `now_iso = "2026-02-07T15:30"` (horário atual)
- Chama `llm.with_structured_output(TrialExtraction)` → força retorno Pydantic
- LLM analisa o texto e retorna:
  ```python
  TrialExtraction(
      nome=None,           # não mencionou nome
      idade=None,          # não mencionou idade
      nivel=None,          # não mencionou nível
      desired_date=None,
      desired_time=None,
      confirmed=None,
  )
  ```

**4d. merge_trial(trial, extraction)**
- `_to_dict_extraction(extraction)` → converte para dict via `.model_dump()`
- Itera campos: todos são `None` → **nenhum campo atualizado**
- trial continua:
  ```python
  trial = {"stage": "collect_client_info", "booking_created": False, ...}
  # nome, idade, nivel → NÃO existem ainda
  ```

**4e. Verifica campos obrigatórios faltantes**
```python
REQUIRED_CLIENT_FIELDS = ("nome", "idade", "nivel")
missing = [f for f in REQUIRED_CLIENT_FIELDS if not trial.get(f)]
# missing = ["nome", "idade", "nivel"]  → faltam TODOS
```

**4f. Como `missing` NÃO está vazio → pede os dados**
```python
trial["stage"] = "collect_client_info"  # continua no mesmo stage
```

**4g. Monta fallback**
```python
parts = ["seu nome", "sua idade", "seu nível (iniciante/intermediário/avançado)"]
fallback = "Para agendar sua aula experimental, me diga: seu nome, sua idade, seu nível (iniciante/intermediário/avançado)."
```

**4h. _fallback_or_nlg → generate_trial_message (nlg.py)**
- Chama NLG com:
  - `stage="collect_client_info"`
  - `action="ask_missing_client_fields"`
  - `missing_fields=["nome", "idade", "nivel"]`
  - `error_code=None`
- NLG usa `TRIAL_NLG_SYSTEM` (prompts.py) pra redigir mensagem amigável
- LLM retorna algo como:
  > "Oi! Para agendar sua aula experimental, preciso do seu nome, idade e nível (iniciante, intermediário ou avançado)."
- Se LLM falhar → usa o `fallback`

**4i. export_trial_output(state)**
```python
state["specialists_outputs"]["trial"] = "Oi! Para agendar sua aula experimental, preciso do seu nome, idade e nível..."
```

### Estado após Turno 1

```python
state = {
    "client_id": "teste_001",
    "client_input": "Oi, quero marcar uma aula experimental.",
    "trial": {
        "stage": "collect_client_info",   # ← continua aqui
        "booking_created": False,
        "handoff_requested": False,
        "output": "Oi! Para agendar sua aula experimental, preciso do seu nome, idade e nível...",
        # nome → NÃO EXISTE
        # idade → NÃO EXISTE
        # nivel → NÃO EXISTE
    },
    "specialists_outputs": {
        "trial": "Oi! Para agendar sua aula experimental, preciso do seu nome, idade e nível..."
    },
}
```

### Saída do grafo → `END`

---

## TURNO 2 — Cliente dá nome e idade (falta nível)

**Input:** `"Meu nome é João, tenho 27 anos"`

### 1–3. trial_router → trial_route

- `trial["stage"]` = `"collect_client_info"` → nó: `trial_collect_client_info`

### 4. Nó: `trial_collect_client_info`

**4c. extract_trial_fields**
- LLM recebe texto `"Meu nome é João, tenho 27 anos"` + snapshot com dados anteriores
- Retorna:
  ```python
  TrialExtraction(
      nome="João",          # ✅ encontrou
      idade=27,             # ✅ encontrou
      nivel=None,           # ❌ não mencionou
      desired_date=None,
      desired_time=None,
      confirmed=None,
  )
  ```

**4d. merge_trial(trial, extraction)**
- `nome="João"` → não-nulo → `trial["nome"] = "João"` ✅
- `idade=27` → não-nulo → `trial["idade"] = 27` ✅
- `nivel=None` → **ignorado** (merge só grava não-nulos)

**4e. Verifica missing**
```python
missing = ["nivel"]  # só falta nível agora
```

**4f–4h. Pede campo faltante via NLG**
- `action="ask_missing_client_fields"`, `missing_fields=["nivel"]`
- Bot: `"Qual seu nível? Iniciante, intermediário ou avançado?"`

### Estado após Turno 2

```python
trial = {
    "stage": "collect_client_info",
    "nome": "João",          # ← ACUMULADO (merge)
    "idade": 27,             # ← ACUMULADO (merge)
    # nivel → AINDA NÃO EXISTE
    "output": "Qual seu nível? Iniciante, intermediário ou avançado?",
    ...
}
```

---

## TURNO 3 — Cliente dá o nível

**Input:** `"Sou iniciante"`

### 4. Nó: `trial_collect_client_info`

**4c. extract_trial_fields**
```python
TrialExtraction(
    nome=None,              # não mencionou (e tá ok — já temos)
    idade=None,             # não mencionou (e tá ok — já temos)
    nivel="iniciante",      # ✅ encontrou
    ...
)
```

**4d. merge_trial**
- `nome=None` → **ignorado** → `trial["nome"]` continua `"João"` ✅
- `idade=None` → **ignorado** → `trial["idade"]` continua `27` ✅
- `nivel="iniciante"` → não-nulo → `trial["nivel"] = "iniciante"` ✅

**4e. Verifica missing**
```python
missing = []  # VAZIO → todos os campos obrigatórios preenchidos!
```

**4f. Como `missing` ESTÁ vazio → avança stage**
```python
trial["stage"] = "ask_date"   # ← AVANÇA!
```

**4g. Fallback direto (sem NLG)**
```python
trial["output"] = "A aula experimental é toda terça. Qual terça (dia do mês) e horário você prefere?"
```
> Nota: aqui o código NÃO chama NLG. Usa fallback fixo porque a mensagem é sempre a mesma neste momento.

### Estado após Turno 3

```python
trial = {
    "stage": "ask_date",            # ← AVANÇOU!
    "nome": "João",
    "idade": 27,
    "nivel": "iniciante",
    "output": "A aula experimental é toda terça. Qual terça (dia do mês) e horário você prefere?",
    ...
}
```

---

## TURNO 4 — Cliente informa data e horário

**Input:** `"Quero terça 2026-02-10 às 19:00"`

### 1–3. trial_router → trial_route

- `trial["stage"]` = `"ask_date"` → nó: `trial_ask_date`

### 4. Nó: `trial_ask_date`

**4c. extract_trial_fields**
```python
TrialExtraction(
    nome=None,
    idade=None,
    nivel=None,
    desired_date="2026-02-10",    # ✅ extraído e normalizado YYYY-MM-DD
    desired_time="19:00",         # ✅ extraído e normalizado HH:MM
    confirmed=None,
)
```

**4d. merge_trial**
- `desired_date="2026-02-10"` → `trial["desired_date"] = "2026-02-10"` ✅
- `desired_time="19:00"` → `trial["desired_time"] = "19:00"` ✅
- Campos anteriores (nome, idade, nivel) → vieram None → **preservados**

**4e. Validação determinística (validators.py)**

Chama `v.validate_date_time("2026-02-10", "19:00")`:

1. `desired_date` não é None → ✅
2. `is_iso_date("2026-02-10")` → `date.fromisoformat("2026-02-10")` → ✅ formato válido
3. `is_tuesday("2026-02-10")` → `date(2026,2,10).weekday()` → `1` (terça) → ✅ é terça!
4. `desired_time` não é None → ✅
5. `is_iso_time_hhmm("19:00")` → `time.fromisoformat("19:00")` → ✅ formato válido

Resultado: `ValidationResult(ok=True)` → passa!

**4f. Como validação OK → avança stage**
```python
trial["stage"] = "awaiting_confirmation"
```

**4g. NLG pede confirmação**
- `action="ask_confirmation"`
- fallback: `"Confirma sua aula experimental na terça 2026-02-10 às 19:00?"`
- Bot (via NLG): `"Fechado: terça 2026-02-10 às 19:00. Confirma o agendamento? (sim/não)"`

### Estado após Turno 4

```python
trial = {
    "stage": "awaiting_confirmation",    # ← AVANÇOU!
    "nome": "João",
    "idade": 27,
    "nivel": "iniciante",
    "desired_date": "2026-02-10",        # ← NOVO
    "desired_time": "19:00",             # ← NOVO
    "output": "Fechado: terça 2026-02-10 às 19:00. Confirma o agendamento? (sim/não)",
    ...
}
```

---

## TURNO 4b (alternativo) — Data inválida (não é terça)

**Input:** `"Quero dia 2026-02-11 às 19:00"` (quarta-feira)

**Validação:**
```
is_tuesday("2026-02-11") → weekday() == 2 (quarta) → FALHA!
→ ValidationResult(ok=False, error="not_tuesday")
```

**Resultado:**
```python
trial["stage"] = "ask_date"  # continua no mesmo stage
# NLG: "A aula experimental acontece somente na terça. Qual terça e horário você prefere?"
```

> O stage NÃO avança. O cliente precisa informar uma terça válida.

---

## TURNO 5 — Cliente confirma

**Input:** `"Sim, confirmo"`

### 1–3. trial_router → trial_route

- `trial["stage"]` = `"awaiting_confirmation"` → nó: `trial_awaiting_confirmation`

### 4. Nó: `trial_awaiting_confirmation`

**4c. extract_trial_fields**
```python
TrialExtraction(
    nome=None, idade=None, nivel=None,
    desired_date=None, desired_time=None,
    confirmed=True,    # ✅ "sim, confirmo" → true
)
```

**4d. merge_trial**
- `confirmed=True` → `trial["confirmed"] = True` ✅
- Todos os outros campos → preservados

**4e. Verifica confirmed**
```python
conf = trial.get("confirmed")  # True
```

**4f. `conf is True` → avança para booking**
```python
trial["stage"] = "book"
```

**4g. NLG**
- `action="book_start"`
- Bot: `"Perfeito! Vou registrar seu agendamento agora."`

### 5. Roteamento especial: `after_confirm_route`

Diferente dos outros nós que vão direto pro END, `trial_awaiting_confirmation` tem um **conditional edge**:

```python
def after_confirm_route(state):
    stage = state["trial"]["stage"]
    if stage == "book":
        return "trial_book"   # ← vai pro booking NO MESMO turno!
    return "END"
```

Como `stage == "book"` → **encadeia direto para `trial_book`** (sem precisar de nova mensagem do cliente).

### 6. Nó: `trial_book`

**6a. ensure_trial_defaults** → trial já existe

**6b. Idempotência**
```python
trial.get("booking_created")  # False → não é duplicata
```

**6c. Verifica DATABASE_URL**
```python
os.getenv("DATABASE_URL")  # None (modo dev) ou "postgresql://..." (produção)
```

**Se modo DEV (sem DATABASE_URL):**
```python
trial["stage"] = "booked"
trial["booking_created"] = True
trial["booking_id"] = "dev_booking"
trial["output"] = "(DEV) Agendado ✅ Te espero na terça 2026-02-10 às 19:00!"
```

**Se modo PRODUÇÃO (com DATABASE_URL):**
```python
from app.agents.aula_experimental.booking import create_trial_booking

booking_id = create_trial_booking(
    customer_id="teste_001",
    desired_date="2026-02-10",
    desired_time="19:00",
)
# → Combina em datetime(2026, 2, 10, 19, 0)
# → INSERT INTO trial_class_booking (id, customer_id, desired_datetime, status='pending')
# → Retorna UUID string

trial["booking_id"] = "a1b2c3d4-..."
trial["booking_created"] = True
trial["stage"] = "booked"
trial["output"] = "Agendado ✅ Te espero na terça 2026-02-10 às 19:00!"
```

**6d. export_trial_output** → copia output para `specialists_outputs["trial"]`

### Estado Final após Turno 5

```python
state = {
    "client_id": "teste_001",
    "trial": {
        "stage": "booked",                  # ← FINAL!
        "nome": "João",
        "idade": 27,
        "nivel": "iniciante",
        "desired_date": "2026-02-10",
        "desired_time": "19:00",
        "confirmed": True,
        "booking_id": "a1b2c3d4-...",       # ← do banco (ou "dev_booking")
        "booking_created": True,             # ← idempotência
        "handoff_requested": False,
        "output": "Agendado ✅ Te espero na terça 2026-02-10 às 19:00!",
    },
    "specialists_outputs": {
        "trial": "Agendado ✅ Te espero na terça 2026-02-10 às 19:00!"
    },
}
```

### Saída do grafo → `END`

Se o grafo for invocado novamente com `stage == "booked"`, o `trial_route` retorna `"END"` direto.

---

## TURNO 5b (alternativo) — Cliente nega confirmação

**Input:** `"Não, quero outro horário"`

```python
TrialExtraction(confirmed=False)
```

**Resultado:**
```python
trial["confirmed"] = False     # merge
trial["stage"] = "ask_date"    # VOLTA pro stage de data!
# Bot: "Sem problemas. Qual terça e horário você prefere então?"
```

> O fluxo volta para `ask_date`. Na próxima mensagem, o cliente informa nova data/hora.

---

## TURNO alternativo — Cancelamento (qualquer estágio)

**Input:** `"Esse mês não vou conseguir, deixa pra lá"`

Pode acontecer em qualquer nó que chama o extractor (Nó 1, 2 ou 3).

### Extração

```python
TrialExtraction(
    nome=None, idade=None, nivel=None,
    desired_date=None, desired_time=None,
    confirmed=None,
    wants_to_cancel=True,    # ← NOVO campo
)
```

### merge_trial + _check_cancellation

```python
merge_trial(trial, extraction)        # wants_to_cancel=True → trial["wants_to_cancel"] = True

cancelled = _check_cancellation(trial, state)  # detecta wants_to_cancel == True
# → trial["stage"] = "cancelled"
# → trial["output"] = NLG com action="cancel_confirmed"
# → retorna imediatamente (nenhuma lógica posterior executa)
```

### Estado após cancelamento

```python
trial = {
    "stage": "cancelled",          # ← TERMINAL
    "nome": "João",                # preservado
    "idade": 27,                   # preservado
    "wants_to_cancel": True,
    "output": "Sem problemas! Quando quiser agendar, é só me chamar. Até mais!",
}
```

### Próxima mensagem no mesmo thread

Se o cliente mandar "quero agendar" no mesmo thread:
- Triage vê `stage == "cancelled"` → sem contexto ativo
- Classifica como `["trial"]` → roteia pro trial
- `trial_route` vê `stage == "cancelled"` → retorna `END`
- **Não faz nada** — "cancelled" é terminal, precisa de novo thread

### Diferença: wants_to_cancel vs confirmed=false

| Campo | Significado | Exemplo | Resultado |
|---|---|---|---|
| `confirmed: false` | "Não quero essa data" | "Não, muda pra 19h" | Volta pra ask_date |
| `wants_to_cancel: true` | "Desisto do agendamento" | "Deixa pra lá" | Stage → cancelled (terminal) |

---

## Resumo Visual: Arquivos envolvidos por turno

```
Mensagem do cliente
    │
    ▼
┌─────────────────────┐
│    trial_router      │  → workflow.py (trial_route)
│    (lê stage)        │  → nodes.py (ensure_trial_defaults)
└─────────┬───────────┘
          ▼
┌─────────────────────────────────┐
│  Nó do stage atual              │  → nodes.py
│                                 │
│  1. ensure_trial_defaults()     │  → nodes.py (helper)
│  2. extract_trial_fields()      │  → extractor.py → schemas.py → prompts.py (TRIAL_EXTRACT_SYSTEM)
│  3. merge_trial()               │  → nodes.py (helper) — acumula dados sem apagar
│  3b. _check_cancellation()      │  → nodes.py (helper) — se wants_to_cancel, seta cancelled e retorna
│  4. validators (se ask_date)    │  → validators.py (validate_date_time)
│  5. Decide: avança ou repete?   │  → nodes.py (lógica determinística)
│  6. _fallback_or_nlg()          │  → nlg.py (recebe client_text) → prompts.py (TRIAL_NLG_SYSTEM)
│  7. export_trial_output()       │  → nodes.py (helper)
└─────────┬───────────────────────┘
          ▼
        END (ou trial_book via after_confirm_route)
```

---

## Quem muda o quê

| Função | Muda stage? | Muda dados do trial? | Chama LLM? |
|--------|:-----------:|:--------------------:|:----------:|
| trial_router | Não | Não | Não |
| ensure_trial_defaults | Não (seta default) | Seta defaults se vazio | Não |
| extract_trial_fields | Não | Não (retorna TrialExtraction) | SIM (structured output) |
| merge_trial | Não | SIM (campos não-nulos) | Não |
| _check_cancellation | SIM (→ cancelled) | Não | SIM (NLG) |
| validate_date_time | Não | Não | Não |
| _fallback_or_nlg | Não | Não | SIM (texto livre) |
| export_trial_output | Não | Não | Não |
| **O nó** (ex: trial_collect_client_info) | **SIM** | Via merge_trial | Via extractor + NLG |
