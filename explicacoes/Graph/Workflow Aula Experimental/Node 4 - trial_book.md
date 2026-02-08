# Nó 4 — Registro do Agendamento (`trial_book`)

Este nó é responsável por persistir o agendamento da aula experimental no banco de dados. Ele só é alcançado quando o Nó 3 (`trial_awaiting_confirmation`) recebeu `confirmed=True` do cliente.

## 🎯 Objetivo do Nó
Registrar o agendamento no banco de dados (ou simular em modo dev):
- Chamar `create_trial_booking()` para inserir no PostgreSQL
- Marcar `booking_created = True` no trial
- Armazenar o `booking_id` gerado

## 🧠 Estratégia Geral
Este nó é **100% determinístico** — não usa LLM em nenhum momento. Sem extração, sem NLG, sem merge. Apenas lógica de persistência:

1. Garante a existência do estado `trial`
2. Verifica se o booking já foi feito (idempotência)
3. Detecta modo dev ou produção
4. Persiste ou simula o agendamento
5. Define a mensagem do turno em `trial.output`
6. Exporta a saída para `specialists_outputs`

> **Diferença dos Nós 1, 2 e 3:** Não chama `extract_trial_fields`, `merge_trial` nem `_fallback_or_nlg`. Todas as mensagens são strings fixas. É o único nó que faz operação de I/O (banco de dados).

## 🔁 Fluxo Detalhado

### 1️⃣ Garantia do Estado (`ensure_trial_defaults`)

Antes de qualquer lógica, o nó garante que o estado `trial` exista no `GlobalState`.

Neste ponto, o trial já contém todos os dados coletados e validados pelos nós anteriores:

```python
trial = {
    "nome": "João",
    "idade": 27,
    "nivel": "iniciante",
    "desired_date": "2026-02-10",
    "desired_time": "19:00",
    "confirmed": True,
    "booking_created": False,    # ← ainda não registrado
    ...
}
```

### 2️⃣ Verificação de Idempotência

Antes de tentar registrar, o nó verifica se o booking **já foi feito**:

```python
if trial.get("booking_created"):
    # já registrado, não faz nada de novo
```

Isso previne duplicidade caso o nó seja executado mais de uma vez (ex: retry, re-execução do grafo).

### 3️⃣ Detecção de Modo (dev vs produção)

O nó verifica a variável de ambiente `DATABASE_URL`:

```python
if not os.getenv("DATABASE_URL"):
    # modo dev: simula sem banco
else:
    # produção: persiste no PostgreSQL
```

## 🧭 Caminhos de Decisão do Nó

### 🟡 Caso 1 — Booking já existe (`booking_created = True`)

Quando o nó é chamado mas o booking já foi registrado:

1. Seta o estágio como `booked`:
```python
trial["stage"] = "booked"
```

2. Retorna mensagem informativa:
```
Seu agendamento já está registrado ✅ Terça 2026-02-10 às 19:00.
```

3. Exporta para `state["specialists_outputs"]["trial"]`.

> **Quando acontece:** Re-execução do grafo, retry após timeout, ou cliente mandando mensagem após booking.

### 🔵 Caso 2 — Modo dev (sem `DATABASE_URL`)

Quando `DATABASE_URL` não está definida (desenvolvimento local, testes):

1. Simula o booking sem banco:
```python
trial["booking_created"] = True
trial["booking_id"] = "dev_booking"
trial["stage"] = "booked"
```

2. Retorna mensagem com prefixo `(DEV)`:
```
(DEV) Agendado ✅ Te espero na terça 2026-02-10 às 19:00!
```

3. Exporta para o estado global.

> **Por que existe:** Permite rodar `manual_test.py` e LangGraph Studio sem precisar de PostgreSQL rodando.

### 🟢 Caso 3 — Produção (com `DATABASE_URL`)

Quando `DATABASE_URL` está definida:

1. Importa `create_trial_booking` sob demanda (lazy import):
```python
from app.agents.aula_experimental.utils_trial.booking import create_trial_booking
```

2. Chama a função de persistência:
```python
booking_id = create_trial_booking(
    customer_id=state.get("client_id"),
    desired_date=trial.get("desired_date"),
    desired_time=trial.get("desired_time"),
)
```

3. Registra o resultado no trial:
```python
trial["booking_id"] = booking_id      # UUID gerado
trial["booking_created"] = True        # marca como feito
trial["stage"] = "booked"              # estágio final
```

4. Retorna mensagem de confirmação:
```
Agendado ✅ Te espero na terça 2026-02-10 às 19:00!
```

5. Exporta para o estado global.

## 🗄️ O que acontece no banco (`create_trial_booking`)

A função `create_trial_booking` em `utils_trial/booking.py`:

1. Combina `desired_date` + `desired_time` em um único `datetime`:
```python
desired_datetime = datetime.fromisoformat("2026-02-10T19:00:00")
```

2. Gera um UUID para o booking:
```python
booking_id = str(uuid.uuid4())
```

3. Insere na tabela `trial_class_booking` via SQL direto (sem ORM):
```sql
INSERT INTO trial_class_booking (id, customer_id, desired_datetime, status)
VALUES (:id, :customer_id, :desired_datetime, 'pending')
```

4. Retorna o `booking_id` gerado.

> **Nota:** O status inicial é sempre `'pending'`. A confirmação administrativa é um processo separado, fora do escopo deste workflow.

## 📤 Saída do Nó

Ao final da execução, este nó sempre garante:

- `trial.stage` = `"booked"` (estágio final do workflow)
- `trial.booking_created` = `True`
- `trial.booking_id` preenchido (UUID real ou `"dev_booking"`)
- `trial.output` preenchido com mensagem de confirmação
- Mensagem disponível em:
```python
state["specialists_outputs"]["trial"]
```

Essa saída será utilizada pelo nó `merge` para compor a resposta final ao usuário.

## 🔒 Garantias de Segurança

| Garantia | Como |
|----------|------|
| Sem duplicidade | Checa `booking_created` antes de inserir |
| Sem crash em dev | Fallback `dev_booking` quando `DATABASE_URL` ausente |
| Lazy import | `booking.py` só é importado em produção, evitando erro de conexão em dev |
| Dados validados | Data e horário já passaram por `validators.py` no Nó 2 |
| Sem LLM | Nenhuma chamada de LLM — mensagens são strings fixas |
