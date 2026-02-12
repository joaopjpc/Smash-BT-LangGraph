# Estratégia Determinística do Workflow de Aula Experimental

## 🎯 O que significa "determinístico" neste projeto

Determinístico significa que o **código decide o fluxo, não o LLM**. O LLM é usado apenas para duas tarefas bem delimitadas:
- **Extração de dados** — transformar texto livre em dados estruturados (Structured Output)
- **Geração de mensagens** — redigir respostas naturais ao cliente (NLG)

Tudo o que envolve **decisão**, **validação** e **roteamento** é feito por código Python comum.

## 🧠 Por que essa estratégia?

### O problema com LLM decidindo fluxo

Se o LLM controlasse o fluxo (estilo agente com tools), ele precisaria:
1. Decidir **quando** pedir dados do cliente
2. Decidir **quando** validar a data
3. Decidir **quando** persistir no banco
4. Lembrar de **todas** as regras de negócio (só terça, formato ISO, etc.)

Isso traz riscos:
- O LLM pode **esquecer** de validar a data antes de confirmar
- O LLM pode **inventar** uma regra que não existe
- O LLM pode **pular** a confirmação e ir direto pro booking
- O comportamento **muda** entre execuções (não-determinístico)

### A solução: LLM faz o que é bom, código faz o resto

| Tarefa | Quem faz | Por quê |
|--------|----------|---------|
| Entender "João, 25, iniciante" | LLM (extractor) | Texto livre → precisa de interpretação |
| Verificar se nome/idade/nivel existem | Código (nó) | Checagem simples, sem ambiguidade |
| Normalizar "terça que vem" → "10-02" | LLM (extractor) | Exige compreensão de linguagem natural |
| Validar se é terça-feira | Código (validators) | Regra de negócio fixa, `weekday() == 1` |
| Validar se horário está nos slots | Código (validators) | Regra de negócio fixa, `VALID_START_TIMES` |
| Decidir próximo estágio | Código (edges do grafo) | Lógica condicional simples |
| Redigir "Confirma terça 10-02 às 09:00?" | LLM (NLG) | Texto natural, tom adequado |
| Gravar no banco | Código (booking) | Ação crítica, não pode falhar por "vontade" do LLM |

## 🔍 Exemplos concretos

### Exemplo 1: Validação de data

```
Cliente: "Quero quarta dia 12/02"
```

**Se o LLM decidisse (tool-based):**
```
LLM pensa: "O cliente quer dia 12/02... vou chamar a tool de booking"
→ ERRO: pulou a validação, não checou se é terça
```

**Como o código decide (determinístico):**
```
1. Extractor retorna: desired_date="12-02"
2. merge_trial grava no estado
3. validators.validate_date_time("12-02", ...)
   → parse_ddmm_date("12-02") → date(2026,2,12).weekday() == 2 (quarta) → FALHA
   → ValidationResult(ok=False, error="not_tuesday")
4. Nó mantém stage="ask_date"
5. Bot: "A aula experimental acontece somente na terça. Qual terça você prefere?"
```
→ **Impossível** pular essa validação. O código sempre executa.

### Exemplo 1b: Validação de horário

```
Cliente: "Terça 10-02 às 19:00"
```

**Como o código decide (determinístico):**
```
1. Extractor retorna: desired_date="10-02", desired_time="19:00"
2. merge_trial grava no estado
3. validators.validate_date_time("10-02", "19:00")
   → data é terça ✅, futura ✅, formato ok ✅
   → "19:00" in VALID_START_TIMES → FALHA (horários: 07-09, 14-17)
   → ValidationResult(ok=False, error="time_out_of_range")
4. Nó mantém stage="ask_date"
5. Bot: "Esse horário não está disponível. As aulas são das 07:00 às 10:00 e das 14:00 às 18:00."
```
→ **Impossível** agendar em horário fora do range. `VALID_START_TIMES` em `validators.py` é a fonte de verdade.

### Exemplo 2: Campos obrigatórios

```
Cliente: "Oi, quero uma aula"
```

**Se o LLM decidisse:**
```
LLM pensa: "O cliente quer aula... vou perguntar a data"
→ ERRO: pulou a coleta de nome/idade/nível
```

**Como o código decide:**
```
1. Extractor retorna: nome=None, idade=None, nivel=None
2. merge_trial: nada muda
3. missing = ["nome", "idade", "nivel"] → não está vazio
4. Nó mantém stage="collect_client_info"
5. Bot: "Preciso do seu nome, idade e nível"
```
→ **Impossível** avançar sem os três campos.

### Exemplo 3: Persistência no banco

```
Cliente: "Sim, confirmo"
```

**Se o LLM decidisse:**
```
LLM pensa: "O cliente confirmou... vou dizer que está agendado"
→ ERRO: respondeu "agendado" mas não gravou no banco
```

**Como o código decide:**
```
1. trial_awaiting_confirmation detecta confirmed=True
2. Seta stage="book"
3. Edge condicional (after_confirm_route) roteia para trial_book
4. trial_book executa create_trial_booking() → INSERT no banco
5. Só DEPOIS seta stage="booked" e mensagem de sucesso
```
→ **Impossível** dizer "agendado" sem ter gravado.

## 🏗️ Onde cada tipo de lógica mora

```
┌──────────────────────────────────────────────────────────────┐
│                    LLM (não-determinístico)                    │
│                                                              │
│  extractor.py  → "João, 25 anos" → {nome:"João",idade:25}    │
│                  (recebe messages + contexto temporal)         │
│  nlg.py        → contexto temporal → "Oi João! Qual terça..." │
│                  (recebe get_current_context() de core/)       │
│                                                              │
├──────────────────────────────────────────────────────────────┤
│                    CÓDIGO (determinístico)                    │
│                                                              │
│  nodes.py         → merge, verificação de missing, stage     │
│  validators.py    → é terça? formato dd-mm? HH:MM?          │
│                     horário nos slots? (VALID_START_TIMES)   │
│  datetime_utils.py→ contexto temporal (core/, compartilhado) │
│  booking.py       → INSERT no banco                          │
│  workflow.py      → edges, roteamento entre nós              │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

## 🔄 Comparação: Agente com Tools vs Determinístico

### Abordagem com Tools (agente)
```
Cliente manda mensagem
    ↓
LLM recebe mensagem + tools disponíveis
    ↓
LLM DECIDE qual tool chamar (ou nenhuma)
    ↓
Tool executa
    ↓
LLM DECIDE se precisa chamar outra tool
    ↓
LLM gera resposta
```

### Abordagem Determinística (este projeto)
```
Cliente manda mensagem
    ↓
Router lê stage → direciona para o nó correto (código)
    ↓
Nó SEMPRE extrai dados (LLM)
    ↓
Nó SEMPRE faz merge (código)
    ↓
Nó SEMPRE valida (código, se aplicável)
    ↓
Nó SEMPRE define próximo stage (código)
    ↓
Nó SEMPRE gera mensagem (LLM)
```

A palavra-chave é **SEMPRE**. Não há "o LLM decidiu não validar hoje".

## ✅ Quando usar cada abordagem

| Cenário | Determinístico | Agente com Tools |
|---------|:-:|:-:|
| Fluxo linear com etapas fixas (booking) | ✅ | |
| Regras de negócio rígidas (só terça) | ✅ | |
| Ações críticas (gravar no banco) | ✅ | |
| Conversa aberta (FAQ, suporte geral) | | ✅ |
| Múltiplas ações possíveis (agendar OU cancelar OU consultar) | | ✅ |
| LLM precisa escolher entre ferramentas | | ✅ |

## 💡 Resumo

O LLM é **poderoso mas imprevisível**. Neste workflow:
- Ele é **ferramenta** (extrai dados e redige texto)
- Ele **não é decisor** (nunca escolhe o que fazer)
- O código garante que **todas as regras são seguidas, sempre**
- O resultado é um fluxo **previsível, auditável e seguro para produção**
