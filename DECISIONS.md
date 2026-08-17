# DECISIONS.md — Índice de decisões

Este arquivo é um resumo/índice. O conteúdo integral de cada decisão está nos ADRs em [`docs/decisoes/`](docs/decisoes/). O congelamento normativo do domínio está em [`specs/001-movimentacoes/spec.md`](specs/001-movimentacoes/spec.md) §0.

## Revisão arquitetural de 2026-08-16 — gatilho automático de validação

A implementação inicial desviou do objetivo do case ao colocar um botão **Validar** no Angular como gatilho da validação. Uma revisão de objetivo corrigiu isso:

- **O frontend passou a ser estritamente consulta/relatório** (RC-10): lista, busca, filtra, ordena, detalha e exibe inconsistências — a decisão de validade é sempre do backend.
- **O gatilho normal do produto passou a ser automático**: um producer local agenda a validação (`JobValidacao`) assim que todas as aprovações exigidas de uma movimentação estão `APROVADA`; um Worker Python consome a fila e executa o mesmo caso de uso de validação usado por `POST /validar` (RC-13, RC-14). Ver [ADR-0009](docs/decisoes/0009-fila-local-sqlite-e-worker-python.md).
- **`POST /validar` foi mantido** como adaptador síncrono técnico exigido pelo case — disponível no Swagger e coberto por teste (RC-15).

Nenhuma das 34 regras de validação foi alterada por esta revisão — apenas o gatilho e a orquestração.

## Ajuste pontual de 2026-08-16 — botão de validação manual condicional

No mesmo dia, um ajuste de escopo reintroduziu, de forma **condicional**, um botão de validação manual no detalhe — sem reverter o fluxo automático acima, que continua sendo o caminho principal:

- **Botão "Validar agora"** visível só quando a solicitação está `PENDENTE` ou `REPROVADA` (não aparece em `APROVADA`); chama `POST /validar` — o mesmo caso de uso do Worker — e por isso funciona mesmo com o Worker parado/travado.
- **Histórico ilustrativo** para solicitações `APROVADA`: linha do tempo montada 100% no cliente a partir de campos já expostos por `GET /movimentacoes/{id}`, com uma última entrada fixa e claramente rotulada como cenário fictício ("efetivação nos sistemas corporativos") — não é uma feature real, não introduz endpoint nem estado novo.

Ver [ADR-0010](docs/decisoes/0010-botao-validacao-manual-condicional-e-historico-ilustrativo.md) para o detalhamento completo, incluindo as decisões interpretativas (visibilidade por `status`, não por `ultimaValidacao`).

## Decisões congeladas do domínio (`spec.md` §0)

Estas são decisões fechadas: qualquer implementação que as contrarie está incorreta, independentemente de parecer tecnicamente superior.

| # | Restrição | Racional resumido |
|---|---|---|
| RC-01 | Catálogo com exatamente 34 regras executáveis | Contrato fechado — nenhuma regra adicionada/removida sem nova decisão registrada |
| RC-02 / RC-03 | `ALTERACAO_ESTRUTURA` move um colaborador; `AE05` é só `origem ≠ destino` | Ver [ADR-0001](docs/decisoes/0001-significado-alteracao-estrutura.md) |
| RC-04 | Ciclo hierárquico é regra real exclusivamente em `TG05` | Consequência de RC-02/RC-03 |
| RC-05 | Aprovação superior baseada em cargo aplica-se exclusivamente a `PROMOCAO` (`P06`) | Ver [ADR-0003](docs/decisoes/0003-politica-aprovacao-promocao-cargo-destino.md) |
| RC-06 | `PX01–PX05` são políticas fictícias e configuráveis; não implementar | Demonstram extensibilidade sem inventar política real de RH |
| RC-07 / RC-08 | Auditoria persistida e append-only; só a última validação é exposta pela API (exceção pontual: linha do tempo client-side em `APROVADA`, sem consultar auditoria histórica — ADR-0010) | Ver [ADR-0005](docs/decisoes/0005-auditoria-sem-endpoint-proprio.md) |
| RC-09 | `Movimentacao.status = PENDENTE` significa "não concluída", não "nunca validada" | Ver [ADR-0004](docs/decisoes/0004-status-vs-resultado-validacao.md) |
| RC-10 | Nenhuma regra de negócio no Angular | O frontend apresenta; a decisão de validade é sempre do backend (CA-039) |
| RC-11 | Fora do MVP: AWS em runtime, Docker obrigatório, Redis, Celery, RabbitMQ, Kafka, autenticação, microsserviços, workflow engine, regras em banco, event sourcing, CQRS, Kubernetes, IA no produto. A fila local `JobValidacao` + Worker Python **fazem parte** do MVP | Ver [`docs/architecture.md`](docs/architecture.md) para a evolução proposta |
| RC-12 | Nenhuma meta numérica de testes ou de cobertura é objetivo do projeto | Qualidade avaliada por comportamento coberto, não por percentual |
| RC-13 | O fluxo normal do produto é automático: só é agendada para validação a movimentação com todas as aprovações exigidas concluídas e aprovadas | Ver [ADR-0009](docs/decisoes/0009-fila-local-sqlite-e-worker-python.md) |
| RC-14 | O disparo local usa producer + `JobValidacao` (SQLite) + Worker Python, fronteira substituível por mensageria gerenciada na evolução | Ver [ADR-0009](docs/decisoes/0009-fila-local-sqlite-e-worker-python.md) |
| RC-15 | `POST /validar` permanece disponível (Swagger, testes, contrato técnico do case) e não é o gatilho normal; o Angular só o chama pelo botão manual condicional do detalhe (`PENDENTE`/`REPROVADA`) | Ver [ADR-0009](docs/decisoes/0009-fila-local-sqlite-e-worker-python.md) e [ADR-0010](docs/decisoes/0010-botao-validacao-manual-condicional-e-historico-ilustrativo.md) |

## ADRs

| ADR | Decisão |
|---|---|
| [0001](docs/decisoes/0001-significado-alteracao-estrutura.md) | `ALTERACAO_ESTRUTURA` move um colaborador, não reparenta a árvore; `AE05` é só `origem ≠ destino` |
| [0002](docs/decisoes/0002-fks-explicitas-nullable.md) | `Movimentacao` usa 10 FKs explícitas nullable, uma por par origem/destino |
| [0003](docs/decisoes/0003-politica-aprovacao-promocao-cargo-destino.md) | Política de aprovação de promoção baseada no cargo de destino (`P06`, `Cargo.aprovacao_adicional`) |
| [0004](docs/decisoes/0004-status-vs-resultado-validacao.md) | `Movimentacao.status` e `resultado_ultima_validacao` são campos distintos |
| [0005](docs/decisoes/0005-auditoria-sem-endpoint-proprio.md) | Auditoria é persistida e append-only, mas sem endpoint nem tela próprios |
| [0006](docs/decisoes/0006-remocao-p01-duplicado.md) | Remoção de "P01 — colaborador ativo" por duplicar `G02` |
| [0007](docs/decisoes/0007-excecao-nao-tratada-nao-e-sys01.md) | Exceção não tratada não vira inconsistência de negócio; propaga como HTTP 500 |
| [0008](docs/decisoes/0008-aprovador-esperado-formalizado-por-tipo.md) | Origem do aprovador esperado formalizada por tipo; `TROCA_GESTOR` exige `gestor_origem_id` |
| [0009](docs/decisoes/0009-fila-local-sqlite-e-worker-python.md) | Gatilho de validação automático via fila local (`JobValidacao` em SQLite) + Worker Python; trade-off explícito vs. SQS na evolução |
| [0010](docs/decisoes/0010-botao-validacao-manual-condicional-e-historico-ilustrativo.md) | Botão de validação manual reintroduzido de forma condicional (só `PENDENTE`/`REPROVADA`) + histórico ilustrativo client-side para `APROVADA` |

## Outros documentos de referência

- [`docs/regras/catalogo-regras.md`](docs/regras/catalogo-regras.md) — as 34 regras, com código, pré-condição, mensagem e severidade.
- [`docs/architecture.md`](docs/architecture.md) — arquitetura do MVP e proposta de evolução (AWS, escalabilidade, observabilidade).
- [`docs/operations.md`](docs/operations.md) — métricas, logs, alertas, troubleshooting e investigação de incidentes.
- [`docs/IA_REPORT.md`](docs/IA_REPORT.md) — uso de IA no desenvolvimento deste projeto.
- [`docs/conformidade.md`](docs/conformidade.md) — checklist de conformidade V-01 a V-14 verificado ao final da implementação.
