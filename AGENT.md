# Guia rápido para agente de IA (Smash-BT-LangGraph)

## Contexto do projeto
- Repositório: Smash-BT-LangGraph
- Domínio: atendente de CT de beach tennis usando LangGraph
- Escopo atual: somente estrutura/local (sem backend ou conexão WPP/WWP)

Estamos construindo um atendente de CT de beach tennis usando LangGraph. O foco atual é o fluxo de **Aula Experimental**, com extração estruturada via LLM + regras determinísticas (terça, formatos de data/hora) e NLG apenas para redigir respostas. O projeto é local, sem backend/WhatsApp; banco está preparado mas não conectado no fluxo. 

## Onde estamos agora (detalhado)
- Estrutura base criada em `app/` com `core/`, `agents/` e `tools/`.
- Aula experimental (workflow) foi a primeira coisa implementada com:
  - `schemas.py` (TrialExtraction Pydantic)
  - `extractor.py` (LLM structured output)
  - `validators.py` (regras determinísticas)
  - `nlg.py` + `TRIAL_NLG_SYSTEM` (LLM só para redigir texto)
  - `nodes.py` (fluxo em nós: coletar dados → pedir terça/horário → confirmar → book)
  - `workflow.py` (grafo com router + edges e factory CLI)
- Teste local funcionando via `scripts/manual_test.py` (sem DB real).
- `langgraph.json` criado com `graphs`, `dependencies` e `env`.
- Banco: `docker-compose.yml` e `app/db/schema.sql` prontos.
- `GlobalState` inclui `specialists_outputs` e `messages` (opcional).

## Próximos passos
1) **Padronizar CLI**
   - Usar sempre `build_trial_graph_cli(config: RunnableConfig)` como factory para CLI/Studio.
   - Garantir que ela aceite **apenas** `RunnableConfig`. 
   FEITO!

2) **Finalizar documentação do fluxo de Aula Experimental**
   - Revisar e entender cada nó (`collect`, `ask_date`, `awaiting_confirmation`, `book`).
   - Documentar regras de negócio e possíveis error_codes.

3) **Implementar workflow global + testar no Studio**
   - Criar grafo global com router, merge e FAQ.
   - Garantir `final_answer` para UI do Studio.
   - Testar tudo junto (routing → especialistas → merge).


## Objetivos
- Evoluir o agente por etapas, com tarefas pequenas
- Manter código simples, documentado e fácil de expandir
- Priorizar clareza em prompts e estados

## Convenções
- Idioma padrão: PT-BR
- Preferir módulos pequenos e focados
- Evitar dependências pesadas no início

## Estrutura
- `app/core`: orquestração do LangGraph
- `app/agents`: agentes por domínio (FAQ, aula experimental, serviços)
- `app/tools`: ferramentas simuladas/local
- `scripts`: utilitários locais

## Notas
- Qualquer integração externa deve ficar atrás de uma interface em `app/tools`.   
