LangGraph com a seguinte estratégia:



**NÓS:**



Assistente:

  Recebe mensagem do WPP e no fim envia mensagem pro WPP após grafo encerrar suas ações

  Avalia se existe necessidade de agente especialista (agendamento aula experimental/FAQ/Outros agendamentos) e caso exista, delega ao          roteador a missão de designá-los



FAQ:

  Nó especialista em dúvidas dos clientes, sabe tudo sobre o CT -> Infos de: Local, Planos, Estrutura, Serviços, Regras de negócio -> RAG vai depender do tamanho total dos arquivos de conhecimento



Agendamento Aula Experimental:

  Nó Especialista em agendamento de aula experimental. Ao confirmar o agendamento com todos os dados necessários o agente envia uma mensagem no wpp do professor principal da escolinha









coisas interessantes de se usar:

structured\_output

TypeDict



langgraph CLI 

lang studio

Agent Chat UI



