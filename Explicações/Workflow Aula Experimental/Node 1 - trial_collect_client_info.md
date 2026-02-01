# Nó 1 — Coleta de Dados do Cliente (`trial_collect_client_info`)

Este nó é o ponto inicial do fluxo de Aula Experimental. Sua responsabilidade é coletar, validar e consolidar as informações básicas do cliente, garantindo que o estado `trial` esteja completo antes de avançar para a escolha de data e horário.

## 🎯 Objetivo do Nó
Capturar e persistir, de forma segura e incremental, os seguintes dados obrigatórios do cliente:
- Nome
- Idade
- Nível (iniciante, intermediário, avançado)

Somente após todos esses campos estarem preenchidos, o fluxo avança para o próximo estágio (`ask_date`).

## 🧠 Estratégia Geral
O nó segue um padrão consistente com o restante do subgrafo:

1. Garante a existência do estado `trial` 
2. Usa LLM com Structured Output para extração (nenhuma heurística)
3. Faz merge seguro, sem apagar dados já coletados
4. Decide o próximo `stage`
5. Define a mensagem do turno em `trial.output`
6. Exporta a saída para `specialists_outputs`

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
Sempre que o estado `trial` estiver vazio, o fluxo começa em `collect_client_info`.


### 2️⃣ Extração de dados (pro estado local Trial) via LLM (`extract_trial_fields`)

O texto do cliente (`state["client_input"]`) é enviado ao extractor:

```python
extract_trial_fields(
    llm,
    client_text=text,
    stage="collect_client_info",
    trial_snapshot=trial,
)
```

O retorno é um objeto estruturado `TrialExtraction`, por exemplo:

```python
TrialExtraction(
  nome="João",
  idade=29,
  nivel="iniciante",
  desired_date="2026-02-03",
  desired_time="19:00",
  confirmed=None
)
```
O extractor pode trazer campos extras, mas o nó só considera os campos relevantes neste estágio.


### 3️⃣ Merge Seguro no Estado (`merge_trial`)

Os dados extraídos da mensagem (nome, nivel, etc...) são mesclados ao estado Trial com regras claras:

- Apenas campos pertencentes ao TrialState
- Apenas valores não nulos
- Nunca apaga dados já coletados

Isso permite coleta progressiva ao longo da conversa. (extractor extrai e merge adiciona esses dados ao Trial)


### 4️⃣ Verificação de Campos Obrigatórios

Campos obrigatórios neste nó:

```python
("nome", "idade", "nivel")
```

O nó identifica quais ainda estão ausentes:

```python
missing = [f for f in REQUIRED_CLIENT_FIELDS if not trial.get(f)]
```

## 🧭 Caminhos de Decisão

### 🔴 Caso 4.1 — Existem dados faltantes

Quando algum campo obrigatório não foi informado:

1. Mantém o estágio como `collect_client_info`:
```python
trial["stage"] = "collect_client_info"
```

2. Cria uma mensagem fallback determinística, usada para auditoria e segurança (manda caso LLM falhe):
```
Para agendar sua aula experimental, me diga: seu nome, sua idade, seu nível.
```

3. Tenta gerar uma mensagem mais rica via NLG (ngl.py recebe contexto e gera mensagem):
```python
trial["output"] = _fallback_or_nlg(...)
```

4. Exporta a resposta final para:
```python
state["specialists_outputs"]["trial"]
```

O módulo `nlg.py` é o responsável principal por elaborar mensagens naturais, utilizando o fallback apenas como garantia em caso de falha da LLM.


### 🟢 Caso 4.2 — Todos os dados obrigatórios estão presentes

Quando `nome`, `idade` e `nível` já foram coletados:

1. Avança o estágio:
```python
trial["stage"] = "ask_date"
```

2. Define uma mensagem fixa e determinística:
```
A aula experimental é toda terça. Qual terça (dia do mês) e horário você prefere?
```

3. A LLM não é chamada neste ponto, pois a mensagem é sempre a mesma, não exige interpretação nem criatividade, e reduz custo e complexidade do fluxo.

4. A saída é exportada para o estado global.

## 📤 Saída do Nó

Ao final da execução, este nó sempre garante:

- `trial.stage` corretamente definido
- `trial.output` preenchido
- Mensagem disponível em:
```python
state["specialists_outputs"]["trial"]
```

Essa saída será utilizada pelo nó `merge` para compor a resposta final ao usuário.
