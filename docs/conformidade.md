# Checklist de conformidade (T-40, `plan.md` §13)

Verificação V-01 a V-20, uma a uma, ao final da implementação — incluindo a revisão arquitetural de 2026-08-16 (processamento automático) e o ajuste pontual do mesmo dia que reintroduziu, de forma condicional, o botão de validação manual (ADR-0010; ver reabertura de V-06 e V-15 abaixo). Nenhuma outra divergência encontrada.

| # | Verificação | Resultado | Evidência |
|---|---|---|---|
| V-01 | O catálogo implementado tem exatamente 34 códigos | ✅ | `tests/engine/test_engine.py::test_v01_total_de_codigos_no_catalogo_e_34` |
| V-02 | `AE05` é `origem ≠ destino`; nenhuma regra de ciclo em `ALTERACAO_ESTRUTURA` | ✅ | `tests/validation/test_estrutura.py`, `tests/integracao/test_ae05_anti_regressao.py` (CN-A01/CN-A02 com árvore real) |
| V-03 | `validation/estrutura.py` não referencia `estrutura_pai_id` | ✅ (revisão manual) | Única ocorrência da string é no docstring que documenta a própria guarda |
| V-04 | `validation/` não importa ORM nem framework web | ✅ | `tests/arquitetura/test_imports.py` (verificação estática via AST) — inalterado pela revisão de processamento automático |
| V-05 | Nenhum arquivo do frontend contém decisão de validade | ✅ | Nenhuma ocorrência de padrão de regra de negócio em `frontend/src/app/features/**/*.ts`; `textoSemValidacao`/`mensagemSemValidacao` apenas escolhem texto de exibição a partir de um `status` já decidido pelo backend |
| V-06 | Nenhum endpoint novo de histórico de auditoria; a linha do tempo do detalhe (`APROVADA`) é client-side, montada só com campos já expostos por `GET /movimentacoes/{id}`, mais uma entrada fixa marcada como ilustrativa (RC-07, ADR-0010) | ✅ | Ainda apenas 3 rotas expostas (nenhuma rota nova); `auditoria_repository`/`job_validacao_repository` seguem uso interno; `DetalheComponent.historico()` não lê nada além de `mov.aprovacoes`/`mov.ultimaValidacao`; `detalhe.component.spec.ts` confirma a entrada `ilustrativo: true` |
| V-07 | Nenhuma menção a `PX01–PX05` como regra real, política real ou exigência legal | ✅ | Zero ocorrências em `backend/app`; únicas menções em docs estão em seções "não implementadas" |
| V-08 | Nenhuma meta numérica de regras ou de cobertura em qualquer documento | ✅ | Verificado inclusive nos documentos novos/atualizados desta revisão (`docs/architecture.md`, `docs/operations.md`, `README.md`) |
| V-09 | Auditoria sem operação de update ou delete | ✅ | `tests/persistencia/test_auditoria_repository.py::test_repositorio_nao_expoe_update_nem_delete`. `JobValidacao` é deliberadamente mutável (máquina de estados de infraestrutura) — spec §4.1 distingue isso da auditoria de validação |
| V-10 | `IA_REPORT.md` presente e atualizado | ✅ | `docs/IA_REPORT.md` — inclui a rodada 4 (revisão de objetivo) |
| V-11 | `DECISIONS.md` atualizado | ✅ | `DECISIONS.md` lista e linka os 9 ADRs, incluindo ADR-0009 (fila local + Worker) |
| V-12 | `docs/architecture.md` mostra fila local + Worker e evolução AWS | ✅ | `docs/architecture.md` §1 (fluxo automático com producer/`JobValidacao`/Worker) e §2 (evolução para SQS/EventBridge/consumers) |
| V-13 | `docs/operations.md` cobre HTTP, fila e Worker | ✅ | `docs/operations.md` §1.1 (métricas de fila/Worker), §2 (logs do Worker), §3 (alertas de backlog/erro/ausência de consumo), §4 (troubleshooting de Worker parado/job em erro/contenção SQLite) |
| V-14 | Exceção de regra não vira `SYS01` nem resultado falso | ✅ | ADR-0007; vale também no caminho do Worker (`tests/processing/test_worker.py::test_ca047_...`) |
| V-15 | Frontend só chama `POST /validar` pelo botão "Validar agora" do detalhe, visível apenas em `PENDENTE`/`REPROVADA` (ADR-0010); nenhum outro fluxo o chama | ✅ | `movimentacao.service.spec.ts` (POST correto, ausência de chamada em `listar`/`buscarPorId`), `detalhe.component.spec.ts` (visibilidade condicional do botão, sucesso/erro do clique, ausência do botão em `APROVADA`), verificado ao vivo no navegador |
| V-16 | Producer não agenda movimentação com aprovação pendente/rejeitada | ✅ | `tests/processing/test_producer.py::test_ca041_...`, `test_ca042_...` |
| V-17 | Producer é idempotente e não duplica `JobValidacao` | ✅ | `JobValidacao.movimentacao_id` único (schema); `test_ca043_cnq06_producer_e_idempotente` |
| V-18 | Worker reutiliza `ValidacaoService`, grava auditoria e conclui job | ✅ | `test_worker_reutiliza_validacao_service_nao_duplica_regras` (identidade de objeto — INV-11); `test_cnq04_...`/`test_cnq05_...` |
| V-19 | Seed simula solicitações e agenda apenas as aptas | ✅ | `tests/persistencia/test_seed.py` (7 testes novos desta revisão); confirmado em execução real (126 movimentações, 62 agendadas, 25 bloqueadas, 25 aguardando, 14 anômalas) |
| V-20 | README documenta os quatro passos locais: backend, seed, Worker, frontend | ✅ | `README.md` — seção dedicada ao Worker com o comando exato e a explicação de que ele precisa permanecer rodando |

## Suíte de testes ao final da revisão

- **Backend:** 237 testes (`pytest`), 0 falhas — inalterado por este ajuste pontual (nenhuma mudança de backend).
- **Frontend:** 29 testes (`ng test --browsers=ChromeHeadless`), 0 falhas — 24 da revisão de processamento automático + 5 ajustados/adicionados no ajuste do botão condicional (POST correto em `validar()`, visibilidade do botão por status, sucesso/erro do clique, histórico ilustrativo).
- **Build de produção do frontend:** `ng build` sem erros.
- **Desempenho:** ver `README.md` §"Desempenho" — os 3 endpoints respondem em milissegundos com o seed carregado (muito abaixo do limite de 2s, RNF-01); o Worker consome 62 jobs em 687 ms (~11 ms/job).
- **Fluxo automático demonstrado de ponta a ponta:** seed → producer (agenda/bloqueia/aguarda) → Worker (drena a fila) → `GET /movimentacoes`/`GET /movimentacoes/{id}` refletindo `APROVADA`/`REPROVADA`/`PENDENTE` sem nenhuma chamada automática a `POST /validar` — verificado tanto por teste automatizado (`tests/integracao/test_fluxo_automatico.py`) quanto manualmente no navegador. O único disparo de `POST /validar` pelo Angular é o clique manual e opcional no botão "Validar agora" (`PENDENTE`/`REPROVADA` — ADR-0010).
