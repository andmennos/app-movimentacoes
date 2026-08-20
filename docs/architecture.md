# Arquitetura — Portal de Mobilidade Organizacional

## 1. Arquitetura do MVP (implementada)

Monólito modular com **processamento assíncrono local** e uma camada de **autenticação/autorização** (JWT + RBAC + BOLA, ADR-0012/ADR-0013) na frente de toda rota protegida. O Angular consulta, cria solicitações e decide aprovações — mas nunca deriva regra de negócio: quem pode aprovar o quê, a ordem sequencial de promoção, e a elegibilidade do disparo manual condicional de validação (`processamento.podeValidarManualmente`, RC-13, ADR-0011) são sempre decididas pelo backend. O FastAPI expõe consulta/escrita e mantém `POST /validar` como adaptador síncrono técnico. O **fluxo normal do produto** usa um producer local, uma fila persistida no próprio SQLite (`JobValidacao`) e um Worker Python que consome essa fila — e o mesmo **orquestrador único** (`processing/orchestrator.py`) processa tanto o caminho automático quanto o manual (ADR-0011).

```
┌────────────────────────────────────────────┐
│  Angular (localhost:4200)                   │
│  login (JWT em memória) → authGuard/scopeGuard│
│  → interceptor → listagem/detalhe →          │
│  nova solicitação → aprovações               │
│  core/services/*.service                     │
└──────────────────┬───────────────────────────┘
                    │ Authorization: Bearer <jwt>
                    │ GET/POST /movimentacoes*, /aprovacoes/*, /colaboradores, /referencias/*
                    │ POST /validar (fallback manual condicional)
┌──────────────────▼───────────────────────────┐
│  FastAPI (localhost:8000)                    │
│ ┌────────────────────────────────────────┐  │
│ │ api/          rotas, schemas Pydantic,   │  │  HTTP, serialização,
│ │  + middleware  contrato de erro,          │  │  validação sintática,
│ │               rate limit/corpo/headers   │  │  hardening (ADR-0016)
│ ├────────────────────────────────────────┤  │
│ │ security/     senha (Argon2id), JWT       │  │  autenticação, RBAC,
│ │               (JWT_SECRET obrigatório,   │  │  BOLA (ADR-0012/0013),
│ │               sem fallback — T-77), RBAC,│  │  nunca cacheia decisão
│ │               BOLA, lockout, rate limit, │  │
│ │               cache referência           │  │
│ ├────────────────────────────────────────┤  │
│ │ services/     movimentacao_service,      │  │  monta ValidationContext,
│ │               validacao_service,         │  │  grava auditoria,
│ │               efetivacao_service,        │  │  aplica efeito local,
│ │               solicitacao_service,       │  │  cria solicitação,
│ │               aprovacao_service,         │  │  decide aprovação (atômico,
│ │               detalhe_service, motivo    │  │  dedup de aprovador — RC-42),
│ │                                          │  │  compõe impedimentos/processamento/motivo
│ ├────────────────────────────────────────┤  │
│ │ validation/   REGRAS + ENGINE + POLÍTICA │  │  puro, sem I/O,
│ │               (37 regras, 6 famílias;    │  │  sem ORM/framework
│ │               exigencias_para dinâmica)  │  │
│ ├────────────────────────────────────────┤  │
│ │ repositories/ consultas, paginação,      │  │  SQLAlchemy,
│ │               auditoria append-only,     │  │  índices
│ │               histórico append-only,     │  │
│ │               fila (job_validacao_repo)  │  │
│ └────────────────────────────────────────┘  │
└──────────────────┬───────────────────────────┘
                    │
             ┌──────▼──────┐
             │   SQLite    │
             │  domínio    │
             │  auditoria  │
             │  histórico  │
             │ JobValidacao│◄──────────┐
             └──────┬──────┘           │
                    │ producer agenda  │ Worker consome
                    │ movimentações    │ (python -m
                    │ aptas            │  app.processing.worker)
             ┌──────▼──────────────────┴───┐
             │  app/processing/              │
             │  approval_gate → producer     │
             │  worker ──► orchestrator ◄── POST /validar
             │                │                        │
             │                ▼                        │
             │       validacao_service (engine)         │
             │                │                         │
             │                ▼                         │
             │       efetivacao_service (se aprovada)   │
             └───────────────────────────────────────────┘
```

`POST /validar` (não desenhado no fluxo principal acima) continua exposto pela API como **adaptador síncrono técnico** — usado pelo Swagger, por testes, e pelo botão manual condicional do detalhe, nunca em nenhum outro fluxo do Angular. Ver §1.2.

**A fronteira crítica** é `validation/`: não importa SQLAlchemy, FastAPI, Pydantic nem `models/`. Recebe um `ValidationContext` (estruturas de dados puras, `app/validation/types.py`) já montado por `services/`. Essa fronteira é verificada por teste estático de imports (`tests/arquitetura/test_imports.py`) e é o que torna as 37 regras (e a política dinâmica de aprovação, `validation/aprovacoes.py::exigencias_para`) testáveis sem banco. O Worker e `POST /validar` chamam o **mesmo orquestrador**, que chama o **mesmo `ValidacaoService`** — nenhuma das 37 regras é reimplementada (INV-09/INV-11, ADR-0011). A mesma política de aprovação é reaproveitada por criação de solicitação, gate, decisão de aprovação, integridade da engine **e seed** (`app/seed/seed.py` chama `montar_contexto`+`exigencias_para` — nenhum mapa paralelo, ADR-0014, RC-41). Promoção com `aprovacao_adicional` exige um bundle de duas anuências (`GERENCIA`/`DIRETORIA`, pessoa concreta via `Cargo.papel_lideranca` + `GESTOR_RH_ADICIONAL`, perfil `RH_GESTOR`) — ver [ADR-0014, Emenda T-75](decisoes/0014-matriz-dinamica-aprovacoes.md).

**Revisão corretiva pós-verificação integrada (2026-08-19, T-73–T-82):** uma verificação de ponta a ponta após T-72 encontrou e corrigiu divergências reais entre o comportamento observado e a spec — nenhuma pega por teste unitário isolado, todas exigindo rodar o sistema real (seed, API, ou leitura atenta do código gerado). Índice completo em [ADR-0017](decisoes/0017-revisao-corretiva-pos-verificacao.md) e `specs/001-movimentacoes/tasks.md`.

### 1.1 Fluxo automático — principal do produto

```
Seed / futura integração
        │
        ▼
Movimentação + aprovações (status inicial: AGUARDANDO_APROVACAO)
        │
        ▼
Gate de aprovação (app/processing/approval_gate.py)
  reutiliza exclusivamente app.validation.aprovacoes.tipos_exigidos — sem segundo mapa
  avalia somente o ESTADO de cada aprovação exigida (não a integridade do
  aprovador — isso é responsabilidade exclusiva da engine, spec §5.2)
   ├── alguma exigida PENDENTE ou linha ausente → Movimentacao=AGUARDANDO_APROVACAO, sem job
   ├── alguma exigida REPROVADA  → Movimentacao=BLOQUEADA, sem job,
   │                                sem passar pela engine
   └── todas exigidas APROVADA
                │
                ▼
          Producer local (app/processing/producer.py)
          idempotente por construção: só reprocessa movimentações
          com status=AGUARDANDO_APROVACAO
                │
                ▼
       Movimentacao=PENDENTE; JobValidacao = PENDENTE
                │
                ▼
          Worker Python (app/processing/worker.py)
          recupera jobs PROCESSANDO stale, consome o mais antigo,
          delega ao orquestrador
                │
                ▼
       processing/orchestrator.processar(origem=AUTOMATICO)
          1. reavalia o gate (protege contra corrida — spec §7.3)
          2. adquire o job por UPDATE condicional (compare-and-set)
          3. chama services/validacao_service.validar()  ── o MESMO usado por POST /validar
                │
                ▼
       ValidationEngine.executar() — 37 regras, gerais → específicas
        │             │
 inconsistências   nenhuma
        │             │
        ▼             ▼
   REPROVADA    services/efetivacao_service.efetivar()
                       │
                       ▼
                   APROVADA
        └──────┬──────┘
               ▼
     Auditoria append-only (ValidacaoAuditoria + InconsistenciaAuditoria)
     + evento real em HistoricoProcessamento (append-only)
               ▼
   Atualiza Movimentacao.status / resultado_ultima_validacao
   (+ efeito local no Colaborador, só se APROVADA)
               ▼
     Job = CONCLUIDO — commit único de toda a conclusão

  Falha técnica em qualquer passo da engine/efetivação/persistência:
  rollback, nenhuma auditoria/efetivação parcial, evento ERRO_TECNICO
  registrado em transação curta separada, Movimentacao volta/permanece
  PENDENTE (RC-19), job volta para PENDENTE (nova tentativa) ou vai
  para ERRO (limite de tentativas esgotado)
```

Nenhuma ação do Angular participa deste fluxo — ele só lê o resultado via `GET /movimentacoes` e `GET /movimentacoes/{id}` depois que o Worker já processou o job.

### 1.2 `POST /validar` — adaptador síncrono técnico

```
Cliente HTTP (Swagger / teste / integração externa / botão "Validar agora" do Angular)
      │  POST /validar { movimentacaoId }
      ▼
api/routers/validacao.py
      │
      ▼
processing/orchestrator.processar(origem=MANUAL)   ◄── o MESMO orquestrador do Worker
      │
      ├─► reavalia o gate de aprovação no instante do clique (RF-16) ──────┐
      │     aprovação pendente/reprovada, ou solicitação já terminal      │
      │     → 409 VALIDACAO_MANUAL_NAO_PERMITIDA (+ impedimentos)         │
      │     job PROCESSANDO saudável (outra origem já processando)       │
      │     → 409 VALIDACAO_EM_ANDAMENTO                                 │
      │                                                                    │
      ├─► adquire o job por atualização condicional (compare-and-set) ◄───┘
      │
      ├─► services.movimentacao_service.montar_contexto()
      │     + repositories.aprovacao_repository (1 consulta)
      │     + repositories.movimentacao_repository.existe_conflito (1 consulta, G04)
      │     + repositories.movimentacao_repository.carregar_grafo_gestores
      │       (1 consulta, só para TROCA_GESTOR)
      │     → ValidationContext (puro)
      │
      ├─► validation.engine.executar(ctx)  — sem try/except por regra (ADR-0007)
      ├─► validation.engine.resolver_resultado(inconsistencias)
      ├─► repositories.auditoria_repository.criar()
      ├─► services.efetivacao_service.efetivar()  — só se aprovada
      ├─► atualiza Movimentacao.status / resultado_ultima_validacao
      ├─► registra HistoricoProcessamento (evento real)
      └─► session.commit()  — commit único de toda a conclusão
            ▼
      Resposta 200 { status, validadoEm, inconsistencias[] }

      Exceção não tratada → sessão revertida, resposta 500 { erro: ERRO_INTERNO }
```

Diferente do fluxo automático, uma chamada a `POST /validar` reavalia o gate no próprio instante do clique — protege contra tela desatualizada (a aprovação pode ter mudado entre o carregamento da tela e o clique). Se o gate não estiver apto, a resposta é `409`, não uma execução "vazia" da engine.

No máximo ~4 consultas SQL para montar o contexto completo de qualquer movimentação — nenhuma delas repetida por regra, o que elimina N+1 (verificado por teste de contagem de queries em `tests/persistencia/test_aprovacao_repository.py`).

---

## 2. Evolução proposta — cenário futuro (documentada, **não implementada** no MVP, RC-11)

O case descreve um cenário de crescimento para ~100 mil movimentações/mês, integração com múltiplos sistemas corporativos, geração de indicadores para RH, e necessidade de escalabilidade e observabilidade. ~100 mil/mês ainda é um volume modesto (~2,3 movimentações/minuto em média, com picos administráveis) — a resposta correta não é reescrever a arquitetura, é **trocar a implementação da fila e do consumer** (já isolados em `app/processing/`) por componentes gerenciados, mantendo o monólito modular e as 37 regras como núcleo pelo maior tempo possível.

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
| **Autenticação corporativa (Microsoft Entra ID ou Keycloak)** | Antes de qualquer uso real (fora de um ambiente de demonstração) | O MVP já tem `ator`/`solicitante` na auditoria (`Usuario`, JWT local — ADR-0012); um IdP corporativo substitui o login local por SSO real, sem mudar o contrato de autorização (RBAC/BOLA continuam no backend) |
| **Azure DDoS Protection + Azure Front Door/WAF + API Management** (ou equivalente AWS: Shield + CloudFront/WAF + API Gateway) | Exposição além de localhost/demonstração | O rate limiter local (`app/security/rate_limit.py`, ADR-0016) é defesa de aplicação, não proteção volumétrica — a borda de rede precisa filtrar tráfego antes de chegar ao processo FastAPI |
| **CDN / hospedagem estática (S3 + CloudFront ou Azure Static Web Apps) para o Angular** | Uso além de localhost | Frontend compilado é estático; não precisa de servidor de aplicação |
| **Versionamento de regras** | Reprodutibilidade histórica da auditoria | `ValidacaoAuditoria.versao_motor` já é a semente — formalizar como estratégia de deploy versionado do motor |
| **`MUDANCA_CARREIRA`** | Negócio real precisar de troca de família de cargo (não só progressão dentro da mesma família) | Fora de escopo deliberado desta revisão (RC-06) — `P07` bloqueia troca de família como uma promoção; uma mudança de carreira real teria regras próprias, distintas de promoção |

### 2.2 Deliberadamente não recomendado, mesmo na evolução

- **Microsserviços por tipo de movimentação** — o domínio é coeso (mesmo agregado `Movimentacao`, mesmas 37 regras compartilhando `aprovacoes.py`); fatiar por tipo criaria 5 serviços que precisariam do mesmo contexto e duplicaria a lógica de aprovação.
- **Kafka como fila padrão** — a um volume de ~100 mil/mês (~0,04 mov/s em média), SQS resolve; Kafka se justifica quando há múltiplos consumidores independentes do mesmo stream com necessidade de replay extensivo, não antes.
- **Kubernetes** — sem múltiplos serviços heterogêneos a orquestrar, um serviço gerenciado (ECS/Fargate, App Runner, Lambda) entrega a mesma elasticidade com muito menos operação.
- **Regras de negócio configuráveis em banco / DSL de regras** — RC-11 e RC-06 já rejeitam isso para o MVP; mesmo na evolução, regra como código (testável, revisável em PR) continua preferível a uma DSL própria, a menos que o volume de regras cresça por ordens de grandeza.

---

## 3. Limitações assumidas no MVP

- **Escritor único do SQLite:** irrelevante no volume atual (RNF-02: ~5.000 movimentações/dia ≈ 0,058/s em média — não há hipótese de pico documentada para este case, e nenhuma conclusão de capacidade é tirada de um pico não especificado); é o primeiro gatilho de evolução (§2.1).
- **Sem cache:** não há necessidade — paginação obrigatória e índices já mantêm os 3 endpoints abaixo de 2s (RNF-01, medido em `docs/operations.md` e no `README.md`).
- **Fila local single-consumer:** um único Worker Python processa a fila; suficiente para o volume do MVP (ver `docs/operations.md` para tempo de consumo medido), mas não coordena múltiplos consumers — isso pertence à evolução com SQS (§2.1). A fila existe para **desacoplar o gatilho de validação e amortecer rajadas**, não porque o volume médio exija infraestrutura distribuída.
- **Rate limiting local, não distribuído, não é proteção contra DDoS volumétrico** (ADR-0016): a janela em memória (`app/security/rate_limit.py`) é por processo único — reinício limpa o estado, e múltiplas réplicas não compartilhariam a contagem. Nunca alegar que o MVP resiste a um ataque de grande escala; essa camada pertence à borda de rede na evolução (§2.1: Azure DDoS Protection/Front Door+WAF/API Management, ou equivalente AWS).
- **Lockout de força bruta é persistido, mas local ao SQLite do MVP** (`SecurityLockout`) — separado do rate limiter geral; sobrevive a reinício do processo, mas não é compartilhado entre múltiplas instâncias.
