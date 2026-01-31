# AGENTS.md

## Contexto do Projeto
- Repositório: Smash-BT-LangGraph
- Domínio: atendente de CT de beach tennis usando LangGraph
- Escopo atual: somente estrutura/local (sem backend ou conexão WPP/WWP)

## Objetivos
- Evoluir o agente por etapas, com tarefas pequenas
- Manter código simples e fácil de expandir
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
