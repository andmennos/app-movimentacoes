# Arquitetura — Portal de Mobilidade Organizacional

## 1. Arquitetura do MVP (implementada)

Monólito modular com **processamento assíncrono local**. O Angular é consulta/relatório — nunca decide validade — mas expõe, no detalhe, um único disparo manual e condicional de validação sob demanda (ADR-0010). O FastAPI expõe consulta e mantém `POST /validar` como adaptador síncrono técnico. O **fluxo normal do produto** usa um producer local, uma fila persistida no próprio SQLite (`JobValidacao`) e um Worker Python que consome essa fila.

```
┌────────────────────────────────────────────┐
│  Angular (localhost:4200)                   │
│  Consulta / relatório — somente leitura      │
│  listagem → busca → filtro → detalhe         │
│  → core/services/MovimentacaoService (GETs)  │
└──────────────────┬───────────────────────────┘
                    │ GET /movimentacoes*
┌──────────────────▼───────────────────────────┐
│  FastAPI (localhost:8000)                    │
│ ┌────────────────────────────────────────┐  │
│ │ api/          rotas, schemas Pydantic,   │  │  HTTP, serialização,
│ │               contrato de erro           │  │  validação sintática
│ ├────────────────────────────────────────┤  │
│ │ services/     orquestração,              │  │  transação, monta
│ │               movimentacao_service,      │  │  ValidationContext,
│ │               validacao_service          │  │  grava auditoria
│ ├────────────────────────────────────────┤  │
│ │ validation/   REGRAS + ENGINE            │  │  puro, sem I/O,
│ │               (34 regras, 5 famílias)    │  │  sem ORM/framework
│ ├────────────────────────────────────────┤  │
│ │ repositories/ consultas, paginação,      │  │  SQLAlchemy,
│ │               auditoria append-only,     │  │  índices
│ │               fila (job_validacao_repo)  │  │
│ └────────────────────────────────────────┘  │
└──────────────────┬───────────────────────────┘
                    │
             ┌──────▼──────┐
             │   SQLite    │
             │  domínio    │
             │  auditoria  │
             │ JobValidacao│◄──────────┐
             └──────┬──────┘           │
                    │ producer agenda  │ Worker consome
                    │ movimentações    │ (python -m
                    │ aptas            │  app.processing.worker)
             ┌──────▼──────────────────┴───┐
             │  app/processing/              │
             │  approval_gate → producer     │
             │  worker → ValidacaoService     │
             └────────────────────────────────┘
```

`POST /validar` (não desenhado no fluxo principal acima) continua exposto pela API como **adaptador síncrono técnico** — usado pelo Swagger, por testes, e pelo botão manual condicional do detalhe (ADR-0010), nunca em nenhum outro fluxo do Angular. Ver §1.2.

**A fronteira crítica** é `validation/`: não importa SQLAlchemy, FastAPI, Pydantic nem `models/`. Recebe um `ValidationContext` (estruturas de dados puras, `app/validation/types.py`) já montado por `services/`. Essa fronteira é verificada por teste estático de imports (`tests/arquitetura/test_imports.py`) e é o que torna as 34 regras testáveis sem banco. O Worker e `POST /validar` chamam o **mesmo** `ValidacaoService` — nenhuma das 34 regras é reimplementada (INV-11, ADR-0009).

### 1.1 Fluxo automático — principal do produto

```
Seed / futura integração
        │
        ▼
Movimentação + aprovações
        │
        ▼
Gate de aprovação (app/processing/approval_gate.py)
  reutiliza exclusivamente app.validation.aprovacoes — sem segundo mapa
   ├── alguma exigida PENDENTE   → Movimentacao=PENDENTE, sem job
   ├── alguma exigida REPROVADA  → Movimentacao=REPROVADA, sem job,
   │                                sem passar pela engine
   ├── linha ausente / aprovação sem integridade → ANOMALO, sem job
   │                                (não mascarado — spec §5.4)
   └── todas exigidas APROVADA
                │
                ▼
          Producer local (app/processing/producer.py)
          idempotente: nunca duplica job p/ mesma movimentação
                │
                ▼
       JobValidacao = PENDENTE
                │
                ▼
          Worker Python (app/processing/worker.py)
          marca PROCESSANDO, incrementa tentativa
                │
                ▼
       ValidacaoService.validar()  ── o MESMO usado por POST /validar
                │
                ▼
       ValidationEngine.executar() — 34 regras, gerais → específicas
        │             │
 inconsistências   nenhuma
        │             │
        ▼             ▼
   REPROVADA       APROVADA
        └──────┬──────┘
               ▼
     Auditoria append-only (ValidacaoAuditoria + InconsistenciaAuditoria)
               ▼
   Atualiza Movimentacao.status / resultado_ultima_validacao
               ▼
     Job = CONCLUIDO

  Falha técnica em qualquer passo da engine/persistência:
  rollback, nenhuma auditoria parcial, job registra tentativa/erro,
  volta para PENDENTE (nova tentativa) ou vai para ERRO (limite esgotado)
```

Nenhuma ação do Angular participa deste fluxo — ele só lê o resultado via `GET /movimentacoes` e `GET /movimentacoes/{id}` depois que o Worker já processou o job.

### 1.2 `POST /validar` — adaptador síncrono técnico

```
Cliente HTTP (Swagger / teste / integração externa / botão "Validar agora" do Angular — ADR-0010)
      │  POST /validar { movimentacaoId }
      ▼
api/routers/validacao.py
      │
      ▼
services/validacao_service.validar()   ◄── idêntico ao chamado pelo Worker
      │
      ├─► repositories.movimentacao_repository.carregar_para_validacao()
      │     1 consulta SQL (joinedload em cadeia) — movimentação +
      │     todas as entidades de origem/destino relevantes
      │
      ├─► services.movimentacao_service.montar_contexto()
      │     + repositories.aprovacao_repository (1 consulta)
      │     + repositories.movimentacao_repository.existe_conflito (1 consulta, G04)
      │     + repositories.movimentacao_repository.carregar_grafo_gestores
      │       (1 consulta, só para TROCA_GESTOR)
      │     → ValidationContext (puro)
      │
      ├─► validation.engine.executar(ctx)  — sem try/except por regra (ADR-0007)
      ├─► validation.engine.resolver_resultado(inconsistencias, aprovações)
      ├─► repositories.auditoria_repository.criar()
      ├─► atualiza Movimentacao.status / resultado_ultima_validacao
      └─► session.commit()
            ▼
      Resposta 200 { status, validadoEm, inconsistencias[] }

      Exceção não tratada → sessão revertida, resposta 500 { erro: ERRO_INTERNO }
```

Diferente do fluxo automático, uma chamada direta a `POST /validar` **não passa pelo gate/producer** — pode ser feita mesmo com aprovação `PENDENTE` (retornando `AGUARDANDO_APROVACAO`, por compatibilidade de contrato — spec §7.3), mas isso não cria job nem é o caminho que o produto usa.

No máximo ~4 consultas SQL para montar o contexto completo de qualquer movimentação — nenhuma delas repetida por regra, o que elimina N+1 (verificado por teste de contagem de queries em `tests/persistencia/test_aprovacao_repository.py`).

---

## 2. Evolução proposta — cenário futuro (documentada, **não implementada** no MVP, RC-11)

O case descreve um cenário de crescimento para ~100 mil movimentações/mês, integração com múltiplos sistemas corporativos, geração de indicadores para RH, e necessidade de escalabilidade e observabilidade. ~100 mil/mês ainda é um volume modesto (~2,3 movimentações/minuto em média, com picos administráveis) — a resposta correta não é reescrever a arquitetura, é **trocar a implementação da fila e do consumer** (já isolados em `app/processing/`) por componentes gerenciados, mantendo o monólito modular e as 34 regras como núcleo pelo maior tempo possível.

```
                                   ┌─────────────────────────┐
                                   │   Sistemas corporativos  │
                                   │  (RH, ERP, provisionamento)│
                                   └────────────┬────────────┘
                                                │ eventos / API
                                   ┌────────────▼────────────┐
                                   │  Anti-corruption layer   │
                                   │  (tradução de contratos) │
                                   └────────────┬────────────┘
                                                │
┌──────────────┐   HTTPS    ┌──────────────────▼──────────────────┐
│   Angular    │───────────►│         API (FastAPI, N réplicas)     │
│  (estático,  │            │   api/ · services/ · validation/      │
│  CDN/S3)     │            │   (mesmo núcleo do MVP, sem reescrita)│
└──────────────┘            └───────┬───────────────┬──────────────┘
                                     │               │ aprovações concluídas
                       leitura/escrita│               │ (substitui o producer local)
                          síncrona    │               ▼
                                     ▼        ┌─────────────────┐
                          ┌────────────────┐  │ EventBridge /    │
                          │  PostgreSQL     │  │ Producer         │
                          │  (RDS, multi-AZ)│  └────────┬────────┘
                          └────────────────┘           ▼
                                                     ┌─────┐
                                                     │ SQS │  (substitui JobValidacao/SQLite)
                                                     └──┬──┘
                                                        ▼
                                          ┌─────────────────────────┐
                                          │  Validation Consumers    │
                                          │  (ECS/Fargate ou Lambda) │  (substitui o Worker único)
                                          │  ValidationEngine        │
                                          └──────────┬──────────────┘
                                                      │
                                          ┌───────────┼────────────────┐
                                          ▼            ▼                ▼
                                  ┌──────────────┐ ┌─────────────┐ ┌──────────────┐
                                  │ Outbox/eventos│ │ Camada       │ │ CloudWatch    │
                                  │ para outros   │ │ analítica    │ │ (logs,        │
                                  │ sistemas      │ │ (indicadores │ │ métricas,     │
                                  │ reagirem      │ │ de RH)       │ │ alertas, DLQ) │
                                  └──────────────┘ └─────────────┘ └──────────────┘
```

### 2.1 Componentes e gatilho de introdução

| Componente MVP → evolução | Gatilho | Por quê |
|---|---|---|
| `JobValidacao` (SQLite) **→ Amazon SQS** | Múltiplos escritores/instâncias, integrações externas, necessidade de retry/DLQ gerenciados | SQLite tem escritor único — suficiente para 1 Worker local, insuficiente para múltiplos consumers concorrentes; SQS resolve visibilidade, retry e DLQ sem código próprio |
| Producer local (`app/processing/producer.py`) **→ serviço de ingestão + EventBridge/SQS** | Múltiplos sistemas originadores da conclusão de aprovação | O gate de aprovação (lógica de negócio) não muda — só a forma como o evento "aprovações concluídas" chega até ele |
| Worker Python único **→ consumers em ECS/Fargate ou Lambda** | Aumento de throughput/concorrência | `ValidacaoService`/`ValidationEngine` são reaproveitados sem alteração — só o mecanismo de invocação muda |
| SQLite **→ PostgreSQL/RDS** | Múltiplos escritores concorrentes ou acesso multi-instância | FKs explícitas (ADR-0002) já preparam a migração |
| **Anti-corruption layer** | Integração com sistemas corporativos (RH, ERP) | Isola o modelo de domínio deste serviço de mudanças em contratos externos |
| **Outbox + eventos de domínio** | Outros sistemas precisam reagir a uma validação (ex.: provisionar acesso após `APROVADA`) | Publica o evento na mesma transação que persiste o resultado, sem risco de inconsistência dual-write |
| **Camada analítica (data warehouse / OLAP)** | Indicadores de RH agregados (taxa de reprovação por tipo, tempo médio de aprovação) | `InconsistenciaAuditoria` já é a fonte natural — extrair para um modelo analítico evita que consultas de BI concorram com o tráfego transacional |
| **CloudWatch (logs, métricas, alertas) + X-Ray/OpenTelemetry** | Mais de um processo em produção | Rastrear uma requisição através de API → fila → consumer exige tracing distribuído, que 1 processo local não precisa. Ver `docs/operations.md` |
| **Autenticação corporativa (Cognito/SSO)** | Antes de qualquer uso real (fora de um ambiente de demonstração) | Habilita o campo `ator` na auditoria — quem/o que iniciou, não só quando |
| **CDN / hospedagem estática (S3 + CloudFront) para o Angular** | Uso além de localhost | Frontend compilado é estático; não precisa de servidor de aplicação |
| **Versionamento de regras** | Reprodutibilidade histórica da auditoria | `ValidacaoAuditoria.versao_motor` já é a semente — formalizar como estratégia de deploy versionado do motor |

### 2.2 Deliberadamente não recomendado, mesmo na evolução

- **Microsserviços por tipo de movimentação** — o domínio é coeso (mesmo agregado `Movimentacao`, mesmas 34 regras compartilhando `aprovacoes.py`); fatiar por tipo criaria 5 serviços que precisariam do mesmo contexto e duplicaria a lógica de aprovação.
- **Kafka como fila padrão** — a um volume de ~100 mil/mês (~0,04 mov/s em média), SQS resolve; Kafka se justifica quando há múltiplos consumidores independentes do mesmo stream com necessidade de replay extensivo, não antes.
- **Kubernetes** — sem múltiplos serviços heterogêneos a orquestrar, um serviço gerenciado (ECS/Fargate, App Runner, Lambda) entrega a mesma elasticidade com muito menos operação.
- **Regras de negócio configuráveis em banco / DSL de regras** — RC-11 e RC-06 já rejeitam isso para o MVP; mesmo na evolução, regra como código (testável, revisável em PR) continua preferível a uma DSL própria, a menos que o volume de regras cresça por ordens de grandeza.

---

## 3. Limitações assumidas no MVP

- **Escritor único do SQLite:** irrelevante no volume atual (RNF-02: ~5.000 movimentações/dia ≈ 0,058/s em média — não há hipótese de pico documentada para este case, e nenhuma conclusão de capacidade é tirada de um pico não especificado); é o primeiro gatilho de evolução (§2.1).
- **Sem cache:** não há necessidade — paginação obrigatória e índices já mantêm os 3 endpoints abaixo de 2s (RNF-01, medido em `docs/operations.md` e no `README.md`).
- **Fila local single-consumer:** um único Worker Python processa a fila; suficiente para o volume do MVP (ver `docs/operations.md` para tempo de consumo medido), mas não coordena múltiplos consumers — isso pertence à evolução com SQS (§2.1). A fila existe para **desacoplar o gatilho de validação e amortecer rajadas**, não porque o volume médio exija infraestrutura distribuída.
