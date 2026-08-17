# plan.md — Portal de Mobilidade Organizacional

**Feature:** 001-movimentacoes
**Depende de:** `spec.md` (domínio congelado)
**Escopo:** como ajustar e construir o que a spec revisada define. Nenhuma decisão de domínio nova fora da revisão de 2026-08-16.

---

## 1. Arquitetura

```text
┌──────────────────────────────────────────────┐
│ Angular (localhost:4200)                     │
│ Consulta / relatório                         │
│ listagem → busca → filtro → detalhe          │
└──────────────────────┬───────────────────────┘
                       │ GET /movimentacoes*
                       ▼
┌──────────────────────────────────────────────┐
│ FastAPI (localhost:8000)                     │
│ api/ → services/ → repositories/             │
│                 └→ validation/ (puro)        │
└──────────────────────┬───────────────────────┘
                       │
                       ▼
                ┌───────────────┐
                │    SQLite     │
                │ domínio       │
                │ auditoria     │
                │ JobValidacao  │
                └───────┬───────┘
                        ▲
                        │ producer agenda aptas
          seed / futura conclusão de aprovações
                        │
                        ▼
                ┌───────────────┐
                │ Worker Python │
                │ consumer local│
                └───────┬───────┘
                        │ chama o mesmo
                        │ ValidacaoService
                        ▼
                 ValidationEngine
```

**Monólito modular com processamento assíncrono local.** O Angular é somente leitura operacional. O FastAPI expõe consulta e mantém `POST /validar` como adaptador síncrono técnico. O fluxo normal do produto usa `JobValidacao` + Worker.

A fila local é uma decisão deliberada de MVP: demonstra producer/consumer sem introduzir broker externo. A fronteira é preparada para ser trocada por mensageria gerenciada na evolução.

---

## 2. Responsabilidades por camada

| Camada | Faz | Não faz |
|---|---|---|
| `api/` | Rotas, Pydantic, DTOs, códigos HTTP | Regra de negócio, polling, lógica de fila |
| `services/` | Orquestra casos de uso, transações, contexto, auditoria | Decidir se uma regra passou |
| `processing/` | Gate de aprovação, producer idempotente, consumo de `JobValidacao`, retry técnico | Implementar regra de movimentação |
| `validation/` | **Todas as 34 regras**, engine, resolução de resultado | Qualquer I/O |
| `repositories/` | Consultas, filtros, paginação, escrita de entidades/auditoria/jobs | Interpretar regra de negócio |
| `models/` | Mapeamento ORM, incluindo `JobValidacao` | Lógica |
| Angular | Consulta e apresentação | Chamar `POST /validar`, decidir validade ou aprovação |

**Fronteira crítica:** `validation/` permanece independente de SQLAlchemy/FastAPI/Pydantic/models. O Worker chama `ValidacaoService`; não reimplementa regra.

O producer reutiliza a fonte única das aprovações exigidas. Não deve existir um segundo mapa de `EXIGENCIAS_POR_TIPO`.

---

## 3. Stack

| Camada | Tecnologia | Motivo |
|---|---|---|
| Frontend | Angular | Definido pelo desafio; adequado ao portal de consulta |
| Backend HTTP | Python + FastAPI | OpenAPI, Pydantic, testes simples |
| Worker | Python, processo separado | Reutiliza domínio/casos de uso sem infraestrutura adicional |
| Fila local | Tabela `JobValidacao` no SQLite | Persistência simples, idempotência e demonstração producer/consumer local |
| ORM | SQLAlchemy | FKs explícitas e migração futura para Postgres |
| Banco | SQLite (WAL, `foreign_keys=ON`) | Adequado ao MVP local e ao volume |
| Testes backend | pytest | — |
| Testes frontend | Jasmine/Karma | Padrão Angular |

Não entram no MVP RabbitMQ, Kafka, Celery, Redis ou serviços AWS. Introduzir um broker agora aumentaria custo operacional sem melhorar a demonstração local.

Django REST Framework continua descartado: ORM/admin/convenções são mais pesados do que o necessário para este escopo.

---

## 4. Estrutura de diretórios

```text
portal-mobilidade/
├── README.md
├── DECISIONS.md
├── docs/
│   ├── IA_REPORT.md
│   ├── architecture.md
│   ├── operations.md
│   ├── decisoes/
│   └── regras/catalogo-regras.md
├── specs/001-movimentacoes/
│   ├── spec.md
│   ├── plan.md
│   └── tasks.md
├── backend/
│   ├── pyproject.toml
│   ├── app/
│   │   ├── main.py
│   │   ├── config.py
│   │   ├── database.py
│   │   ├── api/
│   │   │   ├── routers/
│   │   │   │   ├── movimentacoes.py
│   │   │   │   └── validacao.py
│   │   │   ├── schemas/
│   │   │   └── errors.py
│   │   ├── services/
│   │   │   ├── movimentacao_service.py
│   │   │   └── validacao_service.py
│   │   ├── processing/
│   │   │   ├── approval_gate.py
│   │   │   ├── producer.py
│   │   │   └── worker.py
│   │   ├── validation/
│   │   │   ├── types.py
│   │   │   ├── common.py
│   │   │   ├── transferencia.py
│   │   │   ├── promocao.py
│   │   │   ├── troca_gestor.py
│   │   │   ├── centro_custo.py
│   │   │   ├── estrutura.py
│   │   │   ├── aprovacoes.py
│   │   │   └── engine.py
│   │   ├── models/
│   │   │   └── job_validacao.py
│   │   ├── repositories/
│   │   │   └── job_validacao_repository.py
│   │   └── seed/
│   │       ├── seed.py
│   │       └── dados/*.json
│   └── tests/
│       ├── validation/
│       ├── engine/
│       ├── api/
│       ├── persistencia/
│       ├── processing/
│       ├── integracao/
│       └── arquitetura/
└── frontend/
    └── src/app/
        ├── core/
        │   ├── models/
        │   └── services/
        ├── features/movimentacoes/
        │   ├── listagem/
        │   ├── detalhe/
        │   └── inconsistencias/
        └── shared/
```

Arquivos já existentes devem ser reaproveitados. A revisão não autoriza reorganização cosmética ampla; criar apenas o necessário para o fluxo automático.

---

## 5. Motor de validação

### 5.1 `types.py`

```
ValidationContext
├── movimentacao
├── colaborador
├── cargo_atual, cargo_destino
├── departamento_origem, departamento_destino
├── centro_custo_origem, centro_custo_destino
├── estrutura_origem, estrutura_destino
├── gestor_origem, gestor_destino
├── cadeia_hierarquica        # pré-carregada para TG05
├── aprovacoes                # lista
├── responsaveis_derivados    # gestor do depto / responsável do CC
└── conflitos                 # movimentações do mesmo tipo em aberto

Inconsistencia
├── codigo
├── mensagem
└── severidade   (ERRO)
```

Estruturas simples, sem ORM. Montadas pelo service.

### 5.2 Regras

Funções puras nomeadas por intenção:

```
validate_colaborador_existe(ctx)          -> list[Inconsistencia]
validate_colaborador_ativo(ctx)           -> list[Inconsistencia]
validate_departamento_destino_existe(ctx) -> list[Inconsistencia]
validate_cargo_destino_nivel_superior(ctx)-> list[Inconsistencia]
validate_ciclo_hierarquico(ctx)           -> list[Inconsistencia]
validate_aprovacoes_exigidas(ctx)         -> list[Inconsistencia]
```

Sem classe por regra, sem DSL, sem registro dinâmico. Cada função retorna lista vazia quando passa **ou quando sua pré-condição não é satisfeita** (INV-03).

### 5.3 `engine.py`

```
REGRAS_POR_TIPO = {
    TRANSFERENCIA:        [*REGRAS_GERAIS, *REGRAS_TRANSFERENCIA],
    PROMOCAO:             [*REGRAS_GERAIS, *REGRAS_PROMOCAO],
    TROCA_GESTOR:         [*REGRAS_GERAIS, *REGRAS_TROCA_GESTOR],
    MUDANCA_CENTRO_CUSTO: [*REGRAS_GERAIS, *REGRAS_CENTRO_CUSTO],
    ALTERACAO_ESTRUTURA:  [*REGRAS_GERAIS, *REGRAS_ESTRUTURA],
}
```

Listas explícitas, não herança. `ValidationEngine.executar(ctx)`:

1. Seleciona a lista pelo tipo
2. Itera na ordem, chamando cada função. **Sem `try/except` por regra**: uma exceção não tratada interrompe a execução imediatamente e propaga para `services/` (INV-04) — não vira inconsistência, não há `SYS01`
3. Concatena as inconsistências coletadas até o momento da exceção, preservando a ordem (INV-05)
4. Delega a `resolver_resultado(inconsistencias, aprovacoes)` quando a execução completa sem exceção

`services/` não captura essa exceção para seguir o fluxo normal: deixa-a propagar até a camada `api/`, que responde 500 `ERRO_INTERNO` sem commitar a transação.

### 5.4 Resolução do resultado da engine

```
se inconsistencias não vazio        -> REPROVADA
senão se alguma aprovação REPROVADA -> REPROVADA
senão se alguma aprovação PENDENTE  -> AGUARDANDO_APROVACAO
senão                               -> APROVADA
```

Aprovação exigida ausente ou não íntegra já gerou inconsistência na etapa anterior, portanto cai no primeiro ramo.

No **fluxo automático**, o producer só agenda movimentações cujo gate normal esteja concluído e aprovado. Por isso o Worker tende a produzir `APROVADA` ou `REPROVADA`. `AGUARDANDO_APROVACAO` permanece necessário para a chamada direta de `POST /validar` e para compatibilidade dos testes existentes.

### 5.5 `aprovacoes.py`

Fonte única da verdade sobre exigências:

```
EXIGENCIAS_POR_TIPO = {
    TRANSFERENCIA:        [GESTOR_ORIGEM, GESTOR_DESTINO],
    PROMOCAO:             [GESTOR_ORIGEM, RH],   # + nível do cargo destino
    TROCA_GESTOR:         [GESTOR_ORIGEM, GESTOR_DESTINO],
    MUDANCA_CENTRO_CUSTO: [GESTOR_DESTINO],
    ALTERACAO_ESTRUTURA:  [GESTOR_ORIGEM],
}
```

Para `PROMOCAO`, acrescenta `cargo_destino.aprovacao_adicional` quando não for `null` — *Política de aprovação de promoção baseada no cargo de destino*, aplicável somente a este tipo.

A verificação de integridade (spec §5.3) vive aqui e é chamada pelas regras de aprovação de cada tipo, emitindo sob o código público correspondente. A resolução do responsável esperado por `GESTOR_ORIGEM`/`GESTOR_DESTINO` segue exatamente a tabela de spec §5.3.1 — não é decisão de implementação.

### 5.6 `estrutura.py` — restrição explícita

Contém exatamente `AE01–AE06`. `AE05` é `origem ≠ destino`.

**Este módulo não importa e não referencia `estrutura_pai_id`.** Nenhuma navegação de árvore. Ver spec §9 e teste de arquitetura.

---

---

## 6. Fluxos de processamento

### 6.1 Fluxo automático — principal do produto

| Passo | Componente | Ação |
|---|---|---|
| 1 | Seed / futura integração | Persiste movimentação + aprovações |
| 2 | `processing/approval_gate.py` | Avalia somente o estado necessário para decidir se pode agendar, reutilizando a fonte única de exigências |
| 3a | Producer | Aprovação pendente → não cria job, mantém `PENDENTE` |
| 3b | Producer | Aprovação rejeitada → bloqueia como `REPROVADA`, não cria job |
| 3c | Producer | Todas aprovadas → cria `JobValidacao=PENDENTE` idempotentemente |
| 4 | Worker | Busca o job pendente mais antigo |
| 5 | Worker | Marca `PROCESSANDO` e incrementa tentativa |
| 6 | `ValidacaoService` | Carrega `ValidationContext` em carga única |
| 7 | `ValidationEngine` | Executa as 34 regras e coleta todas as inconsistências |
| 8 | `ValidacaoService` | Persiste auditoria append-only e atualiza a movimentação |
| 9 | Worker | Marca job `CONCLUIDO` |
| 10 | Frontend | Consulta o resultado por GET; não participa do disparo |

**Falha técnica:** a unidade transacional deve impedir auditoria/status parcial. O job registra tentativa/erro e pode ser reprocessado. O Worker do MVP é único; não há requisito de coordenação entre múltiplos consumers locais.

### 6.2 `POST /validar` — adaptador síncrono técnico

| Passo | Camada | Ação |
|---|---|---|
| 1 | api | Recebe `{ movimentacaoId }` |
| 2 | services | Abre transação |
| 3 | repositories | Carrega movimentação → 404 se ausente |
| 4 | services | Monta `ValidationContext` em carga única |
| 5 | validation | `engine.executar(ctx)` |
| 6 | validation | resolve resultado |
| 7 | services | Persiste auditoria |
| 8 | services | Atualiza status/última validação |
| 9 | services | Commit |
| 10 | api | Serializa resposta |

O endpoint existe porque o case o pede e continua útil no Swagger/testes. **Nenhum componente Angular o chama.**

Worker e endpoint devem compartilhar o mesmo `ValidacaoService`; copiar a lógica para `processing/` é proibido.

---

## 7. Persistência

### 7.1 Índices

| Tabela | Índice | Uso |
|---|---|---|
| `movimentacao` | `colaborador_id` | busca, G04 |
| `movimentacao` | `status` | filtro |
| `movimentacao` | `data_solicitacao` | ordenação default |
| `movimentacao` | `(colaborador_id, tipo, status)` | G04 |
| `colaborador` | `matricula` (único) | busca exata |
| `colaborador` | `nome` | busca parcial, ordenação |
| `aprovacao` | `movimentacao_id` | carga do contexto/gate |
| `validacao_auditoria` | `(movimentacao_id, data_hora)` | última validação |
| `job_validacao` | `status, criado_em` | consumo FIFO aproximado |
| `job_validacao` | `movimentacao_id` (único no automático) | idempotência do producer |

### 7.2 Configuração

`journal_mode=WAL` · `foreign_keys=ON` · sessão por request/execução.

### 7.3 Paginação

Limite máximo 100. Campos ordenáveis por whitelist.

### 7.4 Auditoria append-only

Sem update/delete de `ValidacaoAuditoria` e `InconsistenciaAuditoria`.

### 7.5 Fila local

`JobValidacao` é infraestrutura persistente:

- `PENDENTE`: aguardando consumer;
- `PROCESSANDO`: execução em andamento;
- `CONCLUIDO`: validação terminada com resultado de negócio;
- `ERRO`: falha técnica após política de tentativas.

O Worker processa um job por vez no MVP. Não implementar locking distribuído ou coordenação multi-consumer; isso pertence à evolução com broker gerenciado.

---

## 8. Frontend

### 8.1 Estrutura

| Módulo | Responsabilidade |
|---|---|
| `core/models` | Interfaces dos DTOs de consulta |
| `core/services` | `MovimentacaoService` — **somente GETs usados pelo produto** |
| `features/listagem` | Tabela, busca, filtro, ordenação, paginação |
| `features/detalhe` | Dados, origem/destino, aprovações e última validação |
| `features/inconsistencias` | Código + mensagem das inconsistências |

### 8.2 Regras de projeto

1. **Sem botão de validar.**
2. Nenhum service/componente Angular chama `POST /validar`.
3. Zero lógica de validade no frontend.
4. Filtro, ordenação e paginação server-side.
5. Inconsistências exibidas exatamente como retornadas.
6. Estados explícitos: carregando, vazio, erro, aguardando aprovação, aguardando processamento, sem inconsistências.

O Swagger continua sendo a superfície para demonstrar `POST /validar`.

---

## 9. Estratégia de testes

### 9.1 Backend

| Escopo | Diretório | Conteúdo |
|---|---|---|
| Regras | `tests/validation/` | 34 regras, positivos/negativos, múltiplas inconsistências |
| Engine | `tests/engine/` | composição, ordem, pré-condições, exceções, resolução |
| API | `tests/api/` | 3 endpoints e contratos HTTP |
| Auditoria | `tests/persistencia/` | append-only e última validação |
| Processing | `tests/processing/` | gate, producer idempotente, estados de job, retry técnico |
| Integração | `tests/integracao/` | seed → producer → job → Worker → auditoria → GET |
| Arquitetura | `tests/arquitetura/` | imports de `validation/`; ausência de lógica duplicada |

### 9.2 Frontend

Testar:

- listagem/busca/filtro/ordenação/paginação;
- detalhe e aprovações;
- exibição de `ultimaValidacao` e inconsistências;
- estados pendente/processado;
- **ausência de chamada a `POST /validar`**.

Remover testes que esperam clique em botão de validação.

### 9.3 Fábricas de dados

Manter builders existentes e adicionar `JobValidacaoBuilder` apenas se reduzir duplicação real nos testes de processing.

### 9.4 Anti-regressão AE05

Manter os testes atuais de CN-A01/CN-A02/CN-A04 sem alterar o catálogo.

### 9.5 Fora do escopo de testes

E2E · teste de carga · mutation testing · meta percentual de cobertura.

---

## 10. Performance

O requisito do case é **até 5.000 movimentações por dia**. Distribuído uniformemente, isso representa aproximadamente **0,058 movimentação/s em média**. Não assumir um pico específico sem dado de negócio.

A fila local existe principalmente para **desacoplar o gatilho de validação e absorver rajadas**, não porque a média exija infraestrutura distribuída.

| Risco | Mitigação |
|---|---|
| N+1 na validação | `ValidationContext` em carga única; regras sem I/O |
| Listagem sem paginação | paginação obrigatória + índices |
| Rajada de movimentações aptas | `JobValidacao` persistente; Worker drena a fila |
| Contenção de escrita SQLite | um Worker local; transações curtas; WAL |

Os endpoints HTTP devem permanecer abaixo de 2s com o seed carregado. O processamento automático não bloqueia a navegação do Angular.

O primeiro gatilho de evolução é concorrência/múltiplas instâncias: nesse ponto a fila local deixa de ser adequada.

---

## 11. Evolução — arquitetura futura

O MVP já estabelece a fronteira producer/consumer. A evolução substitui infraestrutura, não as 34 regras.

| MVP local | Evolução sugerida | Gatilho |
|---|---|---|
| SQLite | PostgreSQL/RDS | múltiplos escritores/instâncias |
| `JobValidacao` em SQLite | Amazon SQS | integrações externas, elasticidade, retry/DLQ gerenciados |
| Producer local | serviço de ingestão + EventBridge/SQS | múltiplos sistemas originadores |
| Worker Python único | consumers em ECS/Fargate ou Lambda, conforme perfil de execução | aumento de throughput/concor­rência |
| logs locais | CloudWatch + métricas/alertas | produção |
| auditoria relacional | camada analítica/warehouse | indicadores de RH |
| chamada direta entre módulos | eventos de resultado/outbox | outros sistemas reagindo à decisão |

Fluxo futuro de referência:

```text
Sistemas de origem
      │
      ▼
API/Integração
      │
      ▼
Aprovações concluídas
      │
      ▼
EventBridge / Producer
      │
      ▼
     SQS
      │
      ▼
Validation Consumers
      │
      ├── ValidationEngine
      ├── RDS/PostgreSQL
      ├── Auditoria
      └── métricas/logs
```

**Kafka não é a primeira escolha para esse cenário.** Só passa a fazer sentido se surgirem requisitos de streaming contínuo, replay extensivo e múltiplos consumidores independentes que SQS/eventos simples não atendam. Kubernetes também não é necessário por padrão.

---

## 12. Entregáveis de documentação

| Arquivo | Conteúdo |
|---|---|
| `README.md` | comandos explícitos para backend, seed, Worker e frontend; portas; banco; Swagger |
| `DECISIONS.md` | decisões congeladas e ADR da revisão: frontend de consulta + processamento automático local |
| `docs/regras/catalogo-regras.md` | 34 regras MVP + extensões fictícias |
| `docs/decisoes/` | ADRs existentes + decisão sobre `JobValidacao`/Worker e evolução para SQS |
| `docs/architecture.md` | diagrama do MVP com Worker/fila local; fluxo automático; `POST /validar` como adaptador técnico; arquitetura AWS futura |
| `docs/operations.md` | métricas/logs/alertas do HTTP **e do Worker/fila**; troubleshooting; incidentes |
| `docs/IA_REPORT.md` | registrar esta revisão arquitetural, decisões aceitas/rejeitadas e ajustes feitos com IA |

---

## 13. Verificações de conformidade

| # | Verificação |
|---|---|
| V-01 | Catálogo implementado tem exatamente 34 códigos |
| V-02 | `AE05 = origem ≠ destino`; sem ciclo em ALTERACAO_ESTRUTURA |
| V-03 | `validation/estrutura.py` não referencia `estrutura_pai_id` |
| V-04 | `validation/` não importa ORM/framework web |
| V-05 | Nenhum arquivo Angular decide validade |
| V-06 | Nenhum endpoint/tela de histórico de auditoria |
| V-07 | `PX01–PX05` não são apresentados como regra real |
| V-08 | Nenhuma meta numérica de cobertura |
| V-09 | Auditoria sem update/delete |
| V-10 | `IA_REPORT.md` presente e atualizado |
| V-11 | `DECISIONS.md` atualizado |
| V-12 | `docs/architecture.md` mostra fila local + Worker e evolução AWS |
| V-13 | `docs/operations.md` cobre HTTP, fila e Worker |
| V-14 | Exceção de regra não vira `SYS01` nem resultado falso |
| V-15 | **Frontend não possui botão/ação de validar e não chama `POST /validar`** |
| V-16 | Producer não agenda movimentação com aprovação pendente/rejeitada |
| V-17 | Producer é idempotente e não duplica `JobValidacao` |
| V-18 | Worker reutiliza `ValidacaoService`, grava auditoria e conclui job |
| V-19 | Seed simula solicitações e agenda apenas as aptas |
| V-20 | README documenta os quatro passos locais: backend, seed, Worker, frontend |
