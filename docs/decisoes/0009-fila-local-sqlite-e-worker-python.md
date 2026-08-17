# ADR-0009 — Gatilho de validação automático via fila local (`JobValidacao` em SQLite) + Worker Python

**Status:** Aceita — revisão arquitetural de 2026-08-16.

## Contexto

A primeira versão deste MVP colocava a decisão de "quando validar" no usuário: um botão **Validar** no Angular chamava `POST /validar` sob demanda. Uma revisão de objetivo identificou que isso contraria o valor central do case — o produto deveria demonstrar um fluxo **automatizado**: assim que as aprovações exigidas de uma movimentação estiverem concluídas, a validação deve acontecer sozinha, sem depender de alguém clicar em um botão.

A pergunta de design foi: como disparar automaticamente, no backend, sem introduzir infraestrutura desproporcional ao volume do MVP (~5.000 movimentações/dia, ~0,058/s em média — ver `docs/architecture.md` §1.1 e ADR relacionado sobre performance)?

## Alternativas consideradas

1. **Chamar a validação diretamente**, de forma síncrona, no mesmo caminho de código que processa a conclusão de uma aprovação. Rejeitada: acopla fortemente o fluxo de aprovação (que no MVP nem tem endpoint próprio — é simulado pelo seed) à execução da engine, e não deixa rastro de "isso foi agendado e ainda não processado", que é útil tanto para depuração quanto como building block reaproveitável se o volume crescer.
2. **Broker externo (RabbitMQ, Kafka, SQS via LocalStack)** já no MVP. Rejeitada por RC-11 e por desproporção: nenhum requisito do MVP (rodar 100% local, volume baixo) justifica operar um broker antes de precisar dele.
3. **Fila persistida no próprio SQLite (`JobValidacao`) + um processo Worker Python separado**, consumindo essa fila. **Escolhida.**

## Decisão

- `JobValidacao` é uma tabela no mesmo banco SQLite do domínio — infraestrutura, não regra de negócio (spec §4.1). Estados: `PENDENTE → PROCESSANDO → CONCLUIDO | ERRO`.
- Um **producer** local (`app/processing/producer.py`) varre movimentações `PENDENTE`, aplica o **gate de aprovação** (`app/processing/approval_gate.py` — reutiliza exclusivamente `app.validation.aprovacoes`, sem segundo mapa de exigências) e, quando todas as aprovações exigidas estão `APROVADA`, cria exatamente um `JobValidacao`. Aprovação `REPROVADA` bloqueia a movimentação diretamente (sem job, sem passar pela engine); aprovação `PENDENTE` não faz nada.
- Um **Worker Python** independente (`app/processing/worker.py`, executável via `python -m app.processing.worker`) consome o job pendente mais antigo e chama **o mesmo `ValidacaoService`** usado por `POST /validar` — nenhuma das 34 regras é reimplementada (INV-11).
- `POST /validar` é preservado como **adaptador síncrono técnico**, exigido pelo case e útil para Swagger/testes, mas o Angular nunca o chama (RC-15, CA-018).

## Trade-off explícito: fila local em SQLite agora vs. SQS na evolução

A fila local **não é a arquitetura final** — é a fronteira certa para o volume e o escopo deste MVP:

| Aspecto | Fila local (SQLite + Worker único) | SQS (evolução) |
|---|---|---|
| Operação | Zero infraestrutura extra; roda com `python -m app.processing.worker` | Requer conta AWS, IAM, monitoramento próprio |
| Concorrência | Um único consumer; SQLite tem escritor único | Múltiplos consumers, DLQ e retry gerenciados nativamente |
| Custo para o MVP | Nenhum | Desproporcional para ~0,058 mov/s |
| Gatilho de troca | Múltiplos escritores/instâncias, necessidade de DLQ/retry gerenciados, integração com sistemas externos | — |

A fronteira producer/consumer já está modelada corretamente (`app/processing/`) para que a evolução troque **a implementação da fila e do consumer**, não a lógica de gate ou o caso de uso de validação. Ver `docs/architecture.md` §2 para o diagrama completo da evolução.

## Consequências

- **Positiva:** o Angular deixou de ser o gatilho — ele é estritamente consulta/relatório (RC-10), o que corrige o desvio de objetivo identificado na revisão.
- **Positiva:** o producer é idempotente por construção (`JobValidacao.movimentacao_id` único no fluxo automático — INV-10), então reexecutar o seed ou o producer nunca duplica trabalho.
- **Positiva:** `Movimentacao.status` (estado de negócio) e `JobValidacao.status` (execução técnica) são conceitos deliberadamente separados — um job `ERRO` não é o mesmo que uma movimentação `REPROVADA`.
- **Custo aceito:** falha técnica do Worker exige uma política de retry simples (`LIMITE_TENTATIVAS`, sem backoff) — suficiente para o MVP, insuficiente para produção real, onde DLQ/retry gerenciados (SQS) resolvem isso de forma mais robusta.
- **Risco monitorado:** um único Worker é suficiente para o volume do MVP, mas não escala horizontalmente sem coordenação — documentado como o primeiro gatilho de evolução (R8, `spec.md` §14).

## Nota de atualização (2026-08-16 — ADR-0010)

O fluxo automático descrito acima continua sendo o gatilho **normal** do produto e não muda em nada aqui. A única correção é a frase "o Angular nunca o chama": um botão de validação manual condicional foi reintroduzido no detalhe (visível só em `PENDENTE`/`REPROVADA`) para dar feedback em tempo real e para cobrir o caso em que o Worker está parado ou travado. Ver ADR-0010.
