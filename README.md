# Smash-BT-LangGraph

Sistema multi-agente para atendimento da CT Smash Beach Tennis, construido com [LangGraph](https://github.com/langchain-ai/langgraph).

O projeto faz duas coisas hoje:
- **Agendar aula experimental** — fluxo completo de conversa com coleta de dados, validacao de regras de negocio e confirmacao
- **Responder perguntas sobre o CT** — FAQ com busca semantica (RAG) sobre planos, horarios, estrutura e regras

Roda no **LangGraph Studio** para teste e visualizacao do grafo.

> **Nota:** Os agendamentos ainda nao sao persistidos em banco de dados. O chat esta totalmente funcional em modo dev (sem PostgreSQL). O booking e simulado localmente.

---

## Quick Start

```bash
# 1. Instalar dependencias
pip install -r requirements.txt

# 2. Configurar variaveis de ambiente
cp .env.example .env
# Preencher OPENAI_API_KEY no .env

# 3. Gerar embeddings do FAQ (primeira vez)
python -c "from app.agents.faq.retriever import build_and_save_vectorstore; build_and_save_vectorstore()"

# 4. Abrir no LangGraph Studio
langgraph dev
```

O Studio abre no navegador com o grafo visual. Basta digitar mensagens no chat para testar.

---

## Arquitetura

### Visao geral do grafo

```
input_node → triage → [Send()] → trial / faq → merge → END
```

O cliente envia uma mensagem. O **triage** classifica a intencao (LLM) e roteia para os especialistas. Os especialistas produzem suas respostas. O **merge** unifica tudo numa resposta final natural.

O triage suporta multi-intent: uma mensagem como "quero agendar e onde fica?" roteia para `trial` e `faq` em paralelo via `Send()`.

### Modulos

O projeto esta organizado em dois niveis: **core** (orquestracao) e **agents** (especialistas).

---

## Core (`app/core/`)

Camada de orquestracao que conecta os agentes.

### Triage (`triage.py`)

Classifica a intencao do cliente em categorias:
- `trial` — quer agendar aula experimental
- `faq` — duvida sobre o CT (planos, horarios, endereco, etc.)
- `general` — saudacao, agradecimento, fora de contexto

Usa LLM com structured output (`TriageResult`) para classificar. Recebe historico recente da conversa (ultimas 6 mensagens) e o estado do agendamento ativo como contexto, o que permite desambiguar mensagens curtas como "sim" ou "e o da noite?".

### Merge (`merge.py`)

Recebe as saidas de todos os especialistas (`specialists_outputs`) e compoe uma unica resposta final para o cliente via LLM. Usa o historico da conversa para manter coerencia entre turnos.

---

## Trial — Aula Experimental (`app/agents/aula_experimental/`)

Fluxo de agendamento de aula experimental. Implementado como **workflow deterministico**, nao como agente autonomo.

### Por que workflow e nao agente?

A escolha foi deliberada. Num agente com tools, o LLM *decide* quando validar, quando persistir, quando pedir dados. Isso traz riscos em fluxos com regras de negocio rigidas:

- O LLM pode esquecer de validar se e terca-feira
- O LLM pode confirmar o agendamento sem gravar no banco
- O comportamento muda entre execucoes

No workflow deterministico, o **codigo sempre executa** a mesma sequencia: extrair → merge → validar → decidir stage → responder. Nao existe "o LLM decidiu nao validar hoje".

O LLM participa em duas tarefas onde ele agrega valor:
- **Extracao** — transformar "Joao, 25 anos, iniciante" em dados estruturados (`TrialExtraction`)
- **NLG** — redigir respostas naturais e amigaveis

Tudo mais (validacao, roteamento, regras de negocio) e codigo Python deterministico.

### Fluxo em 4 etapas

```
collect_client_info → ask_date → awaiting_confirmation → book
```

**1. Coletar dados (`collect_client_info`)** — Pede nome, idade e nivel (iniciante/intermediario/avancado). Acumula dados entre turnos via `merge_trial` (so grava campos nao-nulos, nunca apaga o que ja foi coletado).

**2. Pedir data e horario (`ask_date`)** — Pede uma terca-feira e horario. Valida com regras deterministicas: deve ser terca, data futura, formato dd-mm, horario entre 07:00-10:00 ou 14:00-18:00. Se invalido, explica o erro e pede novamente.

**3. Confirmacao (`awaiting_confirmation`)** — Apresenta o resumo e pede sim/nao. Se nao confirma, volta pra `ask_date`. Se confirma, avanca pro booking.

**4. Booking (`book`)** — Registra o agendamento. Em modo dev (sem `DATABASE_URL`), simula o booking localmente. Em producao, grava no PostgreSQL via raw SQL.

### Cancelamento

Em qualquer etapa, se o cliente disser "deixa pra la" ou similar, o extractor detecta `wants_to_cancel=True` e o fluxo vai direto para o stage `cancelled` (terminal).

---

## FAQ — RAG (`app/agents/faq/`)

Responde perguntas sobre o CT usando Retrieval-Augmented Generation.

### Pipeline

```
pergunta → FAISS similarity search → top-4 chunks → LLM gera resposta
```

### Knowledge base

A base de conhecimento e um unico arquivo markdown (`knowledge/ct_smash.md`) com informacoes do CT: estrutura, endereco, planos, horarios, aula experimental, regras de acesso e FAQ.

### Por que FAISS?

- **Persistencia em disco** — embeddings sao gerados uma unica vez e salvos localmente (`vectorstore/`). Nas proximas execucoes, carrega do disco sem chamar API de embeddings
- **Sem infraestrutura** — nao precisa de servidor de banco vetorial (Pinecone, Weaviate, etc.)
- **Suficiente pro caso** — a base tem ~16 chunks. FAISS com busca por similaridade cosine atende bem

### Splitter

Usa `MarkdownHeaderTextSplitter` do LangChain, que divide por headers (`#`, `##`, `###`). Cada chunk herda a hierarquia de headers como metadados, e com `strip_headers=False` os headers ficam no conteudo do chunk — o que melhora a qualidade dos embeddings (o embedding "sabe" que o chunk e sobre "Planos > Plano da noite").

### Embeddings

OpenAI `text-embedding-3-small` (1536 dimensoes). Modelo leve e barato, suficiente pra uma base pequena em portugues.

### Contexto de conversa

O retrieval usa apenas o `client_input` como query (sem historico, pra nao diluir a busca semantica). Mas a LLM de NLG recebe as ultimas mensagens da conversa como contexto, o que permite interpretar perguntas de follow-up como "e o da noite?" quando o cliente estava perguntando sobre planos.

---

## Estado

O estado global (`GlobalState`) e compartilhado entre todos os modulos:

```python
GlobalState:
    client_input: str                    # mensagem do turno atual
    messages: List[AnyMessage]           # historico completo
    active_routes: List[str]             # intencoes classificadas pelo triage
    specialists_outputs: Dict[str, str]  # saidas dos especialistas (merge via operator.or_)
    trial: TrialState                    # subestado do agendamento
    final_answer: str                    # resposta final pro cliente
```

Cada especialista retorna suas saidas no formato `{"specialists_outputs": {"nome": "resposta"}}`. O LangGraph faz merge automatico via `operator.or_`.

---

## Estrutura de diretorios

```
app/
  core/
    graph.py           # grafo principal
    state.py           # GlobalState
    triage.py          # classificacao de intencao
    merge.py           # composicao de resposta final
    prompts.py         # prompt base compartilhado entre especialistas
    datetime_utils.py  # utilidades de data (proxima terca, dia da semana em PT-BR)
  agents/
    aula_experimental/
      workflow.py      # subgrafo do trial
      nodes.py         # 4 nos + router
      state.py         # TrialState
      utils_trial/
        extractor.py   # LLM structured output
        schemas.py     # TrialExtraction (Pydantic)
        validators.py  # regras deterministicas
        nlg.py         # geracao de mensagens
        prompts.py     # prompts do trial
        booking.py     # persistencia (raw SQL)
        get_llm.py     # singleton ChatOpenAI
    faq/
      node.py          # no RAG
      prompt.py        # prompt do FAQ
      retriever.py     # FAISS com persistencia em disco
      knowledge/
        ct_smash.md    # base de conhecimento
tests/
  eval_trial.py        # testes de avaliacao com LangSmith
langgraph.json         # configuracao do LangGraph Studio
```

---

## Variaveis de ambiente

| Variavel | Obrigatorio | Descricao |
|---|---|---|
| `OPENAI_API_KEY` | Sim | Chave da API OpenAI |
| `OPENAI_MODEL` | Nao | Modelo (default: `gpt-4o-mini`) |
| `DATABASE_URL` | Nao | PostgreSQL. Sem ela, booking e simulado |
| `LANGSMITH_API_KEY` | Nao | Para tracing via LangSmith |

---

## Modo dev vs producao

| | Modo dev (atual) | Producao |
|---|---|---|
| `DATABASE_URL` | Nao configurada | `postgresql://...` |
| Booking | Simulado (`booking_id = "dev_booking"`) | INSERT no PostgreSQL |
| Chat | Funcional | Funcional |
| FAQ/RAG | Funcional | Funcional |
| Triage | Funcional | Funcional |

O schema do banco (`app/db/schema.sql`) e o `docker-compose.yml` ja estao preparados para quando a persistencia for conectada.

---

## Rebuildar embeddings

Se o arquivo `ct_smash.md` for alterado, os embeddings precisam ser recriados:

```bash
# Deletar vectorstore antigo e rebuildar
rmdir /s /q app\agents\faq\vectorstore
python -c "from app.agents.faq.retriever import build_and_save_vectorstore; build_and_save_vectorstore()"
```

Ou simplesmente deletar a pasta `vectorstore/` e reiniciar — o retriever rebuilda automaticamente na primeira consulta.

---

## Proximos passos

- **Testes mais robustos** — expandir a suite em `tests/` com cenarios de borda (inputs vazios, datas ambiguas, conversas longas), testes unitarios dos validators e testes end-to-end do grafo completo (triage → especialista → merge)
- **Persistencia com banco de dados** — conectar o booking ao PostgreSQL (`DATABASE_URL` no `.env`) para que os agendamentos sejam de fato gravados. O schema (`app/db/schema.sql`) e o `docker-compose.yml` ja estao prontos
