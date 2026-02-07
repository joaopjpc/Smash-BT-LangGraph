Subgrafo e Grafo Global EXPLICAÇÃO


✅ No desenho “certo” (grafo global + subgrafo especialista)

Você não precisa ir pro merge de dentro do subgrafo.

O padrão é:

router_global → (nó especialista = subgrafo trial) → merge_global → END_global

Ou seja:

O subgrafo do trial roda, preenche specialists_outputs["trial"] e termina em END do subgrafo.

Quando o subgrafo termina, o controle volta pro grafo global, que então segue para o merge_global.

O merge_global pega specialists_outputs e monta a resposta final.

➡️ Então: sim, a resposta final deve passar pelo merge_global.
Mas isso acontece automaticamente se o subgrafo está sendo usado como um “nó” dentro do grafo global e você conectou esse nó ao merge.

✅ Quando faz sentido ir pra END (dentro do subgrafo)

Dentro do subgrafo, “ir pra END” significa apenas:

“parei de executar o workflow do trial neste turno”

Isso é exatamente o que você quer quando:

ainda falta informação (você perguntou algo pro usuário)

ou já finalizou (booked)

Porque nesse turno não tem mais nada que o trial deva fazer.

Mas isso não impede que o grafo global vá pro merge.