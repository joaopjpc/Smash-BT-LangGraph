TrialState Esxplicação:

Estado local de Aulas Experimentais. Contém variáveis necessárias no processo de registrar uma aula experimental


1. Ele tem Estágios possíveis(stage):
 - collect_client_info: solicitando infos necessárias do cliente (nível, nome etc...)
 - ask_date: oferecendo possibilidades de horários
 - awaiting_confirmation: esperando confirmação efetiva final do cliente (confirma? -> sim!)
 - book: registrando agendamento no banco
 - booked: aula experimental marcada (terminal)
 - cancelled: cliente desistiu do agendamento (terminal)

2. Infos necessárias pra agendar:
 - nome
 - idade
 - nivel
 - horário desejado

3. Campos de controle:
 - confirmed: se o cliente confirmou sim/não a data/horário
 - wants_to_cancel: se o cliente quer desistir do agendamento inteiro (diferente de confirmed=false, que é só trocar data/horário)

4. Terei aulas experimentais somente as terças (prototipo)
   E devo pegar qual terça o cliente consegue e qual horário nessa terça

5. Cancelamento:
   - Em qualquer estágio (collect_client_info, ask_date, awaiting_confirmation), se o cliente disser algo como "desisto", "esse mês não dá", "deixa pra lá", o extractor retorna wants_to_cancel=True
   - O nó seta stage="cancelled" e gera uma despedida
   - "cancelled" é terminal (como "booked") — no mesmo thread, o fluxo não reinicia