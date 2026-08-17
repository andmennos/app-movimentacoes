# ADR-0010 — Botão de validação manual condicional e histórico ilustrativo no detalhe

**Status:** Aceita — ajuste pontual de 2026-08-16, sobre a revisão arquitetural do mesmo dia (ADR-0009).

## Contexto

A ADR-0009 removeu do Angular qualquer disparo de validação: o gatilho passou a ser 100% automático (producer + `JobValidacao` + Worker), e `POST /validar` ficou reduzido a adaptador técnico nunca chamado pelo frontend (RC-15, CA-018 na sua redação anterior).

Um ajuste de escopo pediu a reintrodução de um botão manual, mas **não** uma reversão total da ADR-0009: o fluxo automático continua sendo o caminho principal. O pedido tem quatro partes:

1. O botão só deve existir no detalhe da solicitação, e só para solicitações **pendentes, bloqueadas ou anômalas** — nunca para uma já `APROVADA`.
2. O botão deve fazer **exatamente a mesma validação** que o processamento automático — a diferença é que ele mostra, em tempo real, o resultado (quais validações falharam).
3. Casos de **timeout ou queda do Worker** não podem impedir a validação manual — ela deve funcionar normalmente mesmo assim.
4. Para solicitações **aprovadas**, deve existir um "histórico" com logs/horários dos processamentos, evidenciando que a solicitação não foi só validada, mas "realizada" — **sem** implementar o fluxo real de efetivação da transferência (isso é um cenário imaginário/ilustrativo).

## Decisão

### Botão de validação manual (itens 1–3)

- `MovimentacaoService.validar()` (`frontend/src/app/core/services/movimentacao.service.ts`) foi reintroduzido chamando `POST /validar` — o mesmo `ValidacaoService`/`ValidationEngine` que o Worker usa (INV-11 continua valendo: nenhuma regra é reimplementada). Isso resolve o item 2: "a mesma coisa que o processamento", só que síncrono e com o resultado mostrado na hora, em vez de esperar o próximo ciclo do Worker.
- `DetalheComponent.podeValidarManualmente(status)` decide a visibilidade: `true` apenas para `status === 'PENDENTE'` ou `status === 'REPROVADA'`; `false` para `APROVADA`. **Interpretação deliberada:** o sistema hoje só tem dois status distinguíveis no frontend (`PENDENTE`, `REPROVADA`/bloqueada) — "anômala" não tem campo próprio e hoje se manifesta como `PENDENTE` sem `ultimaValidacao` (aprovação íntegra pendente vs. aprovação ausente/não íntegra são indistinguíveis no status exposto). A visibilidade foi decidida por **status**, não por `ultimaValidacao === null`: usar `ultimaValidacao` esconderia o botão depois de um único clique manual mesmo que a situação de negócio não tenha mudado (ex.: validar manualmente uma pendência ainda aberta retorna `AGUARDANDO_APROVACAO`, que povoa `ultimaValidacao`, mas a solicitação continua pendente) — status-based mantém o botão disponível para nova tentativa em qualquer caso ainda não `APROVADA`.
- O item 3 (timeout/Worker caído) não exigiu código novo: `POST /validar` já era, desde a ADR-0009, completamente independente da fila `JobValidacao`/Worker — ele chama o caso de uso de validação diretamente. Documentado no docblock de `validar()` e na cópia da UI ("Roda a validação na hora, mesmo que o Worker automático esteja parado").

### Histórico ilustrativo para `APROVADA` (item 4)

- `DetalheComponent.historico()` monta uma linha do tempo **inteiramente client-side**, sem nenhum endpoint novo e sem reabrir RC-08 (só a última validação é exposta pela API): usa somente `mov.dataSolicitacao`, `mov.aprovacoes[].dataDecisao` e `mov.ultimaValidacao`, todos já retornados por `GET /movimentacoes/{id}`.
- A última entrada da linha do tempo ("Movimentação efetivada nos sistemas corporativos") é **fixa e marcada com `ilustrativo: true`**, renderizada com um selo visível "cenário ilustrativo — fora do escopo deste MVP" (`detalhe.component.html`). Ela não lê nenhum dado real de efetivação — não existe efetivação real no backend, e RC-11/spec §13 continuam proibindo esse fluxo. A entrada existe só para atender ao pedido de "evidenciar que a solicitação já foi realizada, não só validada", de forma explicitamente fictícia.
- Quando `status === 'APROVADA'`, a seção "Última validação" (com o botão) é substituída pela seção "Histórico da solicitação" — as duas nunca aparecem juntas.

## Alternativas consideradas

1. **Visibilidade do botão por `ultimaValidacao === null`** em vez de por `status`. Rejeitada pelo motivo já descrito: esconderia a opção de retry num caso ainda não resolvido.
2. **Persistir a entrada "ilustrativa" como um evento real no banco** (nova tabela ou reaproveitando `ValidacaoAuditoria`). Rejeitada: o pedido explicitamente pede um cenário imaginário, não uma feature real; persistir dado fictício como se fosse auditoria violaria a garantia de que a auditoria é uma fonte confiável (ADR-0005).
3. **Botão visível também para `APROVADA`, permitindo revalidar.** Rejeitada: contraria o pedido ("apenas em pendentes, bloqueadas e anômalas") e não faz sentido de produto — uma solicitação já aprovada não tem o que revalidar neste MVP.

## Consequências

- **Positiva:** o fluxo automático (ADR-0009) continua sendo o caminho principal e não foi alterado — o botão é um escape hatch explícito e condicional, não um retorno ao modelo anterior.
- **Positiva:** validação manual funciona mesmo com o Worker parado/travado, cobrindo um cenário operacional real (suporte/depuração) sem precisar reiniciar o Worker.
- **Positiva:** o histórico ilustrativo cumpre o pedido de "evidenciar que foi realizada" sem introduzir nenhum estado novo, endpoint novo ou violação de RC-07/RC-08/RC-11 — é 100% derivado de dados já existentes, mais uma entrada claramente rotulada como não real.
- **Custo aceito:** RC-15/RC-07/CA-018/V-06/V-15 (`spec.md`, `plan.md`, `docs/conformidade.md`) precisaram de reescrita para deixar de ser proibições absolutas e passar a descrever a exceção condicional — documentado nesses arquivos e nesta ADR.
- **Risco monitorado:** por depender de `status` (e não de um campo dedicado de "anomalia"), a visibilidade do botão pode precisar de revisão se o backend algum dia expuser um status distinto para "anômala" — nesse caso, `podeValidarManualmente` deve ser atualizado para incluir esse novo valor.
