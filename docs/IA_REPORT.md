# IA_REPORT.md — Uso de Inteligência Artificial

## 1. Visão geral

A Inteligência Artificial foi utilizada como **ferramenta de engenharia e aceleração**, integrada a um processo de Spec-Driven Development (SDD), revisão técnica, testes automatizados e validação manual ponta a ponta.

A responsabilidade sobre decisões de domínio, priorização, aceitação das soluções e resultado final permaneceu com o candidato. A IA não faz parte do runtime do produto: o motor de validação é determinístico e não realiza chamadas a modelos de linguagem em produção.

O uso de IA teve dois objetivos principais:

1. reduzir o tempo de execução de tarefas mecânicas/repetitivas;
2. ampliar a capacidade de revisão, comparação de alternativas e geração de testes sem transferir a decisão de negócio para a ferramenta.

---

## 2. Ferramentas utilizadas

### ChatGPT — OpenAI

Utilizado principalmente para:

- análise do enunciado e decomposição do problema;
- planejamento do SDD;
- discussão e refinamento das regras de negócio;
- análise de alternativas arquiteturais e trade-offs;
- revisão crítica de `spec.md`, `plan.md` e `tasks.md`;
- revisão de código e comportamento integrado;
- identificação de inconsistências entre regra, implementação e experiência de uso;
- apoio na consolidação da documentação e preparação para apresentação.

O ChatGPT participou da construção e revisão das regras junto com o candidato, mas decisões não explícitas de negócio eram interrompidas para validação humana antes de serem incorporadas ao SDD.

### Claude Code — Anthropic

Utilizado como agente de implementação no repositório para:

- criação e alteração de backend e frontend;
- refatorações incrementais;
- criação/ajuste de testes;
- execução das suítes;
- propagação de alterações aprovadas pelo SDD;
- atualização de documentação técnica ligada à implementação.

O agente recebia especificações e critérios de aceite previamente definidos/revisados e era orientado a não inventar regras diante de ambiguidades.

---

## 3. Atividades aceleradas pela IA

### Especificação e análise

A IA ajudou a transformar um enunciado amplo em artefatos verificáveis:

```text
spec.md
plan.md
tasks.md
ADRs
catálogo de regras
```

Isso permitiu discutir comportamento antes do código e manter rastreabilidade entre requisito, implementação e teste.

### Implementação

Foram aceleradas tarefas como:

- criação de schemas e modelos;
- repositories/services;
- componentes Angular;
- testes de unidade e integração;
- cenários de seed;
- documentação de APIs e operação.

### Revisão

A IA foi usada também como ferramenta de revisão, e não apenas geração:

- consistência entre aprovação e histórico;
- semântica dos estados;
- concorrência Worker × validação manual;
- BOLA/RBAC;
- progressão de carreira;
- snapshots de origem/destino;
- hardening de payloads;
- comportamento do fluxo em testes E2E.

---

## 4. Correções realizadas durante o processo

O desenvolvimento foi iterativo. Testes automatizados, revisão de código e smoke tests no navegador revelaram pontos que foram corrigidos antes do fechamento.

Exemplos representativos:

### Processamento automático

A primeira versão enfatizava validação manual. Ao comparar a solução com o objetivo do case, o fluxo foi reposicionado para:

```text
aprovações
→ fila
→ Worker
→ engine
→ auditoria
→ efetivação
```

O botão manual permaneceu apenas como fallback controlado pelo backend.

### Semântica dos estados

Foi separada a diferença entre:

```text
BLOQUEADA = decisão humana de aprovação encerrou o fluxo
REPROVADA = engine executou e encontrou inconsistências
```

Isso evitou misturar impedimento de workflow com resultado da validação.

### Promoção

A modelagem foi refinada para diferenciar:

```text
nivel
ordem_progressao
familia_cargo
```

e impedir saltos indevidos de carreira.

### Snapshot histórico

O detalhe de promoção passou a usar o snapshot da própria movimentação, e não o cargo atual já alterado do colaborador, preservando a leitura histórica origem → destino.

### Workflow de aprovação

A listagem de pendências passou a respeitar estritamente a ordem das etapas. A revisão E2E também corrigiu o caso em que uma movimentação já `BLOQUEADA` ainda apresentava uma etapa futura como “aguardando”.

### Verificação visual

No smoke E2E foi identificado um desalinhamento entre cabeçalhos e células na tabela de aprovações. A correção foi acompanhada de teste célula-a-célula, evitando que a mesma classe de regressão voltasse a passar apenas por comparação textual.

---

## 5. Como os resultados da IA foram controlados

O processo adotou algumas guardas explícitas.

### SDD como fonte de verdade

Alterações relevantes eram primeiro registradas em especificação/plano/tarefas. O agente implementador trabalhava a partir desses artefatos.

### Ambiguidade de negócio não era resolvida silenciosamente

Quando uma regra não estava definida, a implementação deveria parar e pedir uma decisão.

Um exemplo foi a situação em que duas etapas hierárquicas resolviam para o mesmo aprovador. A decisão final — uma única ação real podendo satisfazer dois requisitos de pessoa específica, mantendo ambos os registros para auditoria — foi tomada pelo candidato e só depois incorporada ao SDD.

### Testes e evidência real

O fechamento não dependia da afirmação do agente de que algo estava pronto.

Evidências finais:

```text
448 testes backend
92 testes frontend
Angular build verde
seed idempotente
Producer/Worker verificados
benchmark reexecutado
smoke E2E no navegador
```

### Revisão ponta a ponta

Testes unitários não foram tratados como substitutos de execução real. Algumas inconsistências só apareceram na sequência completa:

```text
criar
→ aprovar
→ processar
→ efetivar
→ reler
→ visualizar
```

---

## 6. Limitações observadas

### IA pode produzir uma solução consistente para a premissa errada

Código e testes podem estar coerentes entre si e ainda assim não representar o objetivo real do produto. A revisão do candidato contra o enunciado permaneceu obrigatória.

### Testes gerados também precisam ser revisados

Um teste pode confirmar presença de um texto sem garantir que ele aparece no lugar correto. A revisão E2E da tabela de aprovações demonstrou esse risco.

### Contexto de negócio não pode ser inferido livremente

A IA possui capacidade técnica para propor alternativas, mas políticas de RH, hierarquia e aprovação precisam ser decisões explícitas do domínio.

### IA não elimina a necessidade de debugging

Seed, concorrência, transações e comportamento de browser exigiram investigação sobre estado real da aplicação, não apenas geração de código.

---

## 7. Lições aprendidas

1. **Especificar antes de gerar código reduz retrabalho.**
2. **IA é mais eficiente quando recebe critérios de aceite verificáveis.**
3. **Decisão de negócio e accountability não devem ser delegadas ao modelo.**
4. **Testes verdes são condição necessária, não evidência suficiente de experiência correta.**
5. **Smoke E2E deve fazer parte do critério de DONE.**
6. **ADRs tornam alterações assistidas por IA auditáveis e explicáveis.**
7. **Usar uma segunda IA para revisão crítica pode revelar hipóteses que o agente implementador não questionou.**

---

## 8. Resultado

A IA permitiu acelerar análise, implementação, revisão e documentação, enquanto o processo manteve:

- regras de negócio explícitas;
- rastreabilidade;
- testes de regressão;
- decisão humana em pontos ambíguos;
- verificação técnica e funcional antes do fechamento.

O principal aprendizado não foi “gerar mais código”, mas usar IA dentro de um processo de engenharia que permita **questionar, testar, corrigir e explicar** o que foi produzido.
