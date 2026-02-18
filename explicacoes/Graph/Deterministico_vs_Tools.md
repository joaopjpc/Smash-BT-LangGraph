# Determinístico vs Tools (Agente): Análise Comparativa

Análise dos tradeoffs entre a abordagem determinística atual e uma possível migração para agente com tools, no contexto do workflow de Aula Experimental do CT Smash.

---

## 1. Confiabilidade das Regras de Negócio

**Determinístico (atual):** Impossível pular validação. O código *sempre* executa `validate_date_time`, *sempre* checa campos obrigatórios, *sempre* passa pelo booking antes de dizer "agendado".

**Com tools:** O LLM *decide* quando chamar `validate_date_time_tool`. Ele pode:
- Esquecer de validar antes de confirmar
- Chamar `book_tool` sem ter todos os campos
- Inventar uma resposta sem chamar nenhuma tool

Mesmo com bons prompts, a taxa de erro nunca é zero. Bugs determinísticos (fáceis de achar) viram falhas estocásticas (difíceis de reproduzir).

---

## 2. Custo e Latência

**Determinístico:** 2 chamadas LLM por turno (extractor + NLG), ambas simples e rápidas.

**Com tools:** Mínimo 1 chamada, mas tipicamente 2-4 por turno (LLM pensa → chama tool → recebe resultado → pensa de novo → responde). Com tool-calling, cada "pensamento" do LLM é um round-trip completo. O custo em tokens aumenta bastante porque o prompt inclui a descrição de todas as tools em toda chamada.

---

## 3. Complexidade do Código vs Complexidade do Prompt

**Determinístico:** Código maior (`nodes.py` ~420 linhas), mas cada linha é legível, testável e auditável.

**Com tools:** Código menor (cada tool é uma função simples), mas a complexidade migra pro prompt. É necessário um system prompt muito robusto dizendo "SEMPRE valide antes de confirmar", "NUNCA diga agendado sem chamar book_tool", etc. E mesmo assim, o LLM pode ignorar.

---

## 4. Testabilidade

**Determinístico:** Testes unitários simples — chama `trial_ask_date(state)`, verifica o output. 100% reprodutível.

**Com tools:** Testar um agente com tools exige mocks do LLM. O mesmo input pode gerar sequências de tools diferentes entre execuções. Testes se tornam mais frágeis.

---

## 5. Debugging

**Determinístico:** O `stage` no state diz exatamente onde o fluxo está. O erro tem um `error_code` determinístico.

**Com tools:** O LLM pode tomar caminhos inesperados. Debugar "por que ele não chamou validate_tool?" é muito mais difícil que debugar "por que validate_date_time retornou not_tuesday?".

---

## 6. Escalabilidade para Novos Fluxos

**Com tools ganha aqui.** Para adicionar "cancelar aula", "remarcar horário", "consultar disponibilidade", com tools basta adicionar novas funções e o LLM roteia sozinho. No modelo determinístico, cada fluxo novo é um subgrafo inteiro com nodes, edges, stages.

---

## 7. Experiência Conversacional

**Com tools ganha aqui também.** Um agente com tools lida melhor com conversas abertas, perguntas fora do script, mudanças de assunto no meio do fluxo. O modelo determinístico é mais rígido.

---

## Quando Usar Cada Abordagem

| Cenário | Determinístico | Tools |
|---------|:-:|:-:|
| Fluxo linear com etapas fixas (booking) | melhor | |
| Regras de negócio rígidas (só terça, horários fixos) | melhor | |
| Ações críticas (gravar no banco) | melhor | |
| Muitos fluxos diferentes (FAQ + booking + cancelar + remarcar) | | melhor |
| Conversa aberta e flexível | | melhor |
| Orçamento limitado de API | melhor | |

---

## Recomendação: Abordagem Híbrida

Em vez de migrar tudo, manter o **workflow determinístico para o booking** (onde regras são rígidas) e usar **tools no triage/roteador de alto nível**:

```
Cliente manda mensagem
    ↓
Agente com tools (triage) decide:
  - tool: "start_trial_booking" → entra no subgrafo determinístico atual
  - tool: "answer_faq" → responde FAQ
  - tool: "check_schedule" → consulta horários
    ↓
Subgrafo determinístico executa com garantias
```

Isso dá flexibilidade no roteamento sem perder as garantias do fluxo crítico.

---

## Resumo

Para o caso específico de aula experimental (regras rígidas), o modelo determinístico é a escolha mais segura. A migração para tools faz sentido quando houver múltiplos fluxos e necessidade de mais flexibilidade conversacional — e mesmo assim, o booking deve permanecer como subgrafo determinístico.

O LLM é **poderoso mas imprevisível**. No workflow atual:
- Ele é **ferramenta** (extrai dados e redige texto)
- Ele **não é decisor** (nunca escolhe o que fazer)
- O código garante que **todas as regras são seguidas, sempre**
- O resultado é um fluxo **previsível, auditável e seguro para produção**
