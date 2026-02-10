# Log: Problema da NLG "cega" — não vê o client_input

Conversa real no LangGraph Studio em 2026-02-10 (terça-feira).

---

## Turno 1 — "oi"

**Cliente:** `oi`

**Triage** → `intents: ["general"]`, `general_response: "Olá! Sou o assistente da CT Smash. Como posso te ajudar?"`

**Merge** → `"Olá! Sou o assistente da CT Smash Beach Tennis. Como posso te ajudar hoje?"`

Tudo OK.

---

## Turno 2 — "quero agendar uma aula experimental"

**Cliente:** `quero agendar uma aula experimental`

**Triage** → `intents: ["trial"]`

**Extractor (collect_client_info):**
```json
{"nome": null, "idade": null, "nivel": null, "desired_date": null, "desired_time": null, "confirmed": null, "wants_to_cancel": null}
```
Nenhum dado extraído — faltam nome, idade, nivel.

**NLG** → action: `ask_missing_client_fields`, missing: `["nome", "idade", "nivel"]`
> "Para agendar sua aula experimental, me diga seu nome, sua idade e seu nível (iniciante, intermediário ou avançado)."

**Merge** → repassa a mensagem.

Tudo OK.

---

## Turno 3 — "JOao 21 iniciante"

**Cliente:** `JOao 21 iniciante`

**Triage** → `intents: ["trial"]` (contexto ativo: collect_client_info)

**Extractor (collect_client_info):**
```json
{"nome": "JOao", "idade": 21, "nivel": "iniciante", "desired_date": null, "desired_time": null, "confirmed": null, "wants_to_cancel": null}
```
Todos os campos obrigatórios preenchidos → avança pra `ask_date`.

**Fallback direto** (sem NLG):
> "A aula experimental é toda terça. Qual terça (dd-mm) e horário você prefere? Ex: 10-02 às 19:00."

**Merge** → `"Olá, João! A aula experimental acontece toda terça-feira. Por favor, me informe qual terça-feira e horário você prefere..."`

Tudo OK.

---

## Turno 4 — "hoje pode?" ← PROBLEMA AQUI

**Cliente:** `hoje pode?`

Hoje é **terça-feira 2026-02-10** — é um dia válido para aula experimental.

**Triage** → `intents: ["trial"]` (contexto ativo: ask_date)

**Extractor (ask_date):**

Recebeu no prompt:
```
Data/hora atual (referência): 2026-02-10T15:38 (terça-feira)
Próximas terças-feiras disponíveis: 17-02, 24-02, 03-03, 10-03
```

Retornou:
```json
{"nome": "JOao", "idade": 21, "nivel": "iniciante", "desired_date": null, "desired_time": null, "confirmed": null, "wants_to_cancel": null}
```

**desired_date = null** — o extractor não conseguiu mapear "hoje" pra uma data.

Motivo: a lista de próximas terças começa em 17-02 (pula o dia atual). O extractor foi instruído a "SEMPRE usar as datas da lista de terças fornecida", mas "hoje" (10-02) não está na lista.

**Validator** → `error_code: "missing_date"` (desired_date é null)

**NLG** recebeu:
```
Stage: ask_date
Action: ask_date_time
Error_code: missing_date
Trial_snapshot: nome=JOao, idade=21, nivel=iniciante
```

Respondeu:
> "Perfeito, João! A aula experimental é na terça. Me diga a data (dd-mm) e o horário (HH:MM). Ex: 10-02 às 19:00."

---

## O Problema: NLG "cega"

A NLG **não recebe o `client_input`**. Ela só vê dados estruturados (stage, action, error_code, snapshot).

O cliente perguntou **"hoje pode?"** — uma pergunta direta, esperando uma resposta como:
> "Hoje é terça! Claro, me diz só o horário."
> ou: "Hoje é terça, mas já é tarde. Que tal a próxima terça?"

Em vez disso, recebeu uma resposta genérica que **ignora completamente** a pergunta:
> "Me diga a data (dd-mm) e o horário (HH:MM)."

Para o cliente, parece que o bot não entendeu nada.

### Causa raiz

São dois problemas encadeados:

1. **Extractor não mapeia "hoje"** — a lista de terças fornecida não inclui o dia atual (10-02), então "hoje" não casa com nenhuma data da lista. O extractor segue a instrução "use as datas da lista" e retorna null.

2. **NLG não vê o texto original** — como a NLG só recebe `error_code: "missing_date"`, ela não sabe que o cliente disse "hoje pode?". Não tem como contextualizar a resposta.

### Impacto

Qualquer mensagem do cliente que o extractor não consiga processar resulta numa resposta genérica da NLG. O cliente sente que o bot é surdo.

Exemplos que teriam o mesmo problema:
- "pode ser nessa semana?" (se não for terça)
- "qualquer terça serve" (sem data específica)
- "o mais rápido possível"
