LangGraph — Definições do projeto

Objetivo
- Atendente do CT Smash Beach Tennis com fluxo de Aula Experimental e FAQ.
- O grafo decide a lógica; especialistas respondem com base em regras claras.

Nós (alto nível)

Assistente (nó orquestrador)
- Recebe a mensagem do cliente (WPP no futuro).
- Encerra o grafo e devolve a resposta final ao canal.
- Decide se precisa de especialistas e aciona o roteador.

FAQ (nó especialista)
- Responde dúvidas sobre o CT: localização, planos, estrutura, serviços e regras.
- Pode usar RAG se a base de conhecimento crescer.

Agendamento de Aula Experimental (WORKFLOW especialista)
- Coleta dados do aluno e agenda aula experimental.
- Regras fixas: aula apenas na terça-feira; formatos de data/hora padronizados.
- Quando confirmado, registra o agendamento (hoje sem integração WPP).

Merge (nó agregador)
- Recebe outputs de um ou mais especialistas e junta tudo em uma unica resposta final.
- Cria resposta final e marca o fluxo como finalizado.

Conceitos importantes
- Structured Output (extração estruturada).
- TypedDict para estado do grafo.
- Validação determinística (regras do CT).
- NLG opcional para redigir respostas em workflow Aula Experimental, sem decidir fluxo.

Ferramentas úteis pro futuro do projeto
- LangGraph CLI
- LangSmith/LangStudio
- Agent Chat UI


