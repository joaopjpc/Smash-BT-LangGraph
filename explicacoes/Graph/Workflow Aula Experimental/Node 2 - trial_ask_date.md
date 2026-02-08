# Nó 2 — Coleta de Data e Horário (`trial_ask_date`)

Este nó é responsável por coletar e validar a data e o horário desejados para a aula experimental. Ele só é alcançado quando o Nó 1 (`trial_collect_client_info`) já confirmou que nome, idade e nível estão preenchidos.

## 🎯 Objetivo do Nó
Capturar, validar e consolidar a data e horário da aula experimental:
- Data (`desired_date`) — deve ser uma **terça-feira** em formato YYYY-MM-DD
- Horário (`desired_time`) — em formato HH:MM (24h)

Somente após ambos os campos estarem preenchidos **e validados**, o fluxo avança para o próximo estágio (`awaiting_confirmation`).

## 🧠 Estratégia Geral
O nó segue o mesmo padrão consistente do subgrafo, mas com uma etapa extra em relação ao Nó 1 — a **validação determinística** via `validators.py`:

1. Garante a existência do estado `trial`
2. Usa LLM com Structured Output para extração (nenhuma heurística)
3. Faz merge seguro, sem apagar dados já coletados
4. **Valida regras de negócio** (formato da data, é terça?, formato do horário)
5. Decide o próximo `stage`
6. Define a mensagem do turno em `trial.output`
7. Exporta a saída para `specialists_outputs`

> **Diferença do Nó 1:** O Nó 1 só verifica se os campos *existem*. Este nó verifica se os campos são *válidos* usando `validators.py`.

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

Neste ponto, o trial já contém `nome`, `idade` e `nivel` preenchidos pelo Nó 1.

### 2️⃣ Extração de dados via LLM (`extract_trial_fields`)

O texto do cliente (`state["client_input"]`) é enviado ao extractor:

```python
extract_trial_fields(
    llm,
    client_text=text,
    stage="ask_date",
    trial_snapshot=trial,
)
```

O retorno é um objeto estruturado `TrialExtraction`, por exemplo:

```python
TrialExtraction(
    nome=None,                    # não mencionou → None
    idade=None,                   # não mencionou → None
    nivel=None,                   # não mencionou → None
    desired_date="2026-02-10",    # ✅ extraído e normalizado
    desired_time="19:00",         # ✅ extraído e normalizado
    confirmed=None
)
```

O LLM é **instruído** (via prompt) a normalizar a data para YYYY-MM-DD e o horário para HH:MM, mas isso **não é garantido** — por isso existe o passo de validação.

### 3️⃣ Merge Seguro no Estado (`merge_trial`)

Os dados extraídos são mesclados ao estado Trial com as mesmas regras:

- Apenas campos pertencentes ao TrialState
- Apenas valores não nulos
- Nunca apaga dados já coletados

Depois do merge, o trial pode conter:

```python
trial = {
    "nome": "João",              # preservado do Nó 1
    "idade": 27,                 # preservado do Nó 1
    "nivel": "iniciante",        # preservado do Nó 1
    "desired_date": "2026-02-10",  # ← novo (do extractor)
    "desired_time": "19:00",       # ← novo (do extractor)
    ...
}
```

### 4️⃣ Validação Determinística (`validators.validate_date_time`)

Aqui está a **diferença principal** deste nó em relação ao Nó 1. Em vez de só verificar se os campos existem, este nó valida as **regras de negócio** usando código determinístico:

```python
v.validate_date_time(trial.get("desired_date"), trial.get("desired_time"))
```

A validação segue esta cadeia de checagens (em ordem):

| # | Checagem | Erro retornado |
|---|----------|----------------|
| 1 | `desired_date` é None? | `missing_date` |
| 2 | `desired_date` é formato ISO válido? | `invalid_date_format` |
| 3 | `desired_date` é uma terça-feira? | `not_tuesday` |
| 4 | `desired_time` é None? | `missing_time` |
| 5 | `desired_time` é formato HH:MM válido? | `invalid_time_format` |

Se qualquer checagem falhar, retorna `ValidationResult(ok=False, error="código_do_erro")`.
Se todas passarem, retorna `ValidationResult(ok=True)`.

> **Importante:** O LLM pode normalizar "terça que vem" para "2026-02-10", mas pode errar. O validator é quem tem a **palavra final** — nunca o LLM.

## 🧭 Caminhos de Decisão do Nó

### 🔴 Caso 4.1 — Validação falhou

Quando `validate_date_time` retorna `ok=False`, o nó:

1. Mantém o estágio como `ask_date`:
```python
trial["stage"] = "ask_date"
```

2. Escolhe um fallback específico baseado no `error_code`:

| Error Code | Fallback |
|------------|----------|
| `missing_date` | "Me diga a data exata da terça (YYYY-MM-DD ou dd/mm/aaaa) e o horário." |
| `invalid_date_format` | "A data precisa estar clara. Pode me dizer a terça em formato dd/mm/aaaa e o horário?" |
| `not_tuesday` | "A aula experimental acontece somente na terça. Qual terça e horário você prefere?" |
| `missing_time` | "Fechado para {data}. Qual horário você prefere? (ex: 19:00)" |
| `invalid_time_format` | "O horário precisa estar claro (ex: 19:00). Qual horário você prefere?" |
| (outro) | "Não consegui validar a data/horário. Pode informar a terça (data) e o horário novamente?" |

3. Tenta gerar uma mensagem mais rica via NLG, passando o `error_code` para contexto:
```python
trial["output"] = _fallback_or_nlg(
    llm=llm,
    stage="ask_date",
    action="ask_date_time",
    error_code=code,        # ← NLG sabe qual erro explicar
    ...
    fallback=fallback,
)
```

4. Exporta a resposta para `state["specialists_outputs"]["trial"]`.

> **Nota:** Quando o erro é `missing_time` mas `desired_date` já foi informada, o fallback reconhece que a data está ok e pede **apenas** o horário. Isso evita pedir tudo de novo.

### 🟢 Caso 4.2 — Validação passou

Quando `validate_date_time` retorna `ok=True` (data é terça, formatos corretos):

1. Avança o estágio:
```python
trial["stage"] = "awaiting_confirmation"
```

2. Gera mensagem de confirmação via NLG:
```python
trial["output"] = _fallback_or_nlg(
    llm=llm,
    stage="awaiting_confirmation",
    action="ask_confirmation",
    ...
    fallback=f"Confirma sua aula experimental na terça {trial['desired_date']} às {trial['desired_time']}?",
)
```

A NLG recebe o snapshot do trial (com data e horário) para compor um resumo:
```
"Fechado: terça 2026-02-10 às 19:00. Confirma o agendamento? (sim/não)"
```

3. Exporta a saída para o estado global.

## 📤 Saída do Nó

Ao final da execução, este nó sempre garante:

- `trial.stage` corretamente definido (`ask_date` se falhou, `awaiting_confirmation` se passou)
- `trial.output` preenchido com a mensagem do turno
- Dados de data/horário preservados no trial (mesmo se inválidos — ficam para a próxima tentativa)
- Mensagem disponível em:
```python
state["specialists_outputs"]["trial"]
```

Essa saída será utilizada pelo nó `merge` para compor a resposta final ao usuário.

## 🔄 Cenário de Coleta Progressiva (data e horário separados)

Assim como o Nó 1, este nó suporta **coleta incremental** graças ao `merge_trial`:

```
Mensagem 1: "Quero na terça dia 10 de fevereiro"
  → extractor: desired_date="2026-02-10", desired_time=None
  → merge: trial["desired_date"] = "2026-02-10"
  → validator: ok=False, error="missing_time"
  → bot: "Fechado para 2026-02-10. Qual horário você prefere? (ex: 19:00)"

Mensagem 2: "19:00"
  → extractor: desired_date=None, desired_time="19:00"
  → merge: desired_date preservado, trial["desired_time"] = "19:00"
  → validator: ok=True ✅
  → bot: "Confirma sua aula na terça 2026-02-10 às 19:00? (sim/não)"
```
