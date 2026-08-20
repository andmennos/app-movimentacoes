# Portal de Mobilidade Organizacional

MVP local de acompanhamento de movimentações organizacionais (transferência, promoção, troca de gestor, mudança de centro de custo, alteração de estrutura), com um motor de validação determinístico que retorna **todas** as inconsistências encontradas e persiste uma trilha de auditoria append-only. O portal tem autenticação (JWT), autorização por perfil e por objeto (RBAC/BOLA), e permite criar e aprovar solicitações pelo próprio Angular — não é mais só consulta/relatório.

Cada movimentação tem um de **cinco status de negócio**: `AGUARDANDO_APROVACAO` (falta aprovação), `BLOQUEADA` (uma aprovação exigida foi reprovada — encerrada, sem passar pela engine), `PENDENTE` (aprovações concluídas, processamento final ainda não concluído), `APROVADA` e `REPROVADA` (a engine executou e decidiu). `BLOQUEADA` nunca é confundida com `REPROVADA`: a primeira é decisão humana de aprovação, a segunda é a engine encontrando inconsistência de negócio.

A validação é **automática**: assim que as aprovações exigidas de uma movimentação são concluídas, um producer local agenda a validação em uma fila persistida (`JobValidacao`), consumida por um **Worker Python** independente. Uma validação aprovada **efetiva a movimentação no cadastro do colaborador** (mesma transação da auditoria) e registra eventos reais numa timeline persistida (`HistoricoProcessamento`). O Angular consulta, cria solicitações e decide aprovações — mas nunca deriva regra de negócio: quem pode aprovar o quê, a ordem sequencial de promoção, e a elegibilidade do botão de validação manual condicional (`processamento.podeValidarManualmente`) são sempre decididas pelo backend. `POST /validar` e o botão manual passam pelo mesmo orquestrador do Worker (`processing/orchestrator.py`): reavaliam o gate de aprovação no instante do clique e não podem gerar dupla validação/efetivação para o mesmo job.

**Autenticação e autorização:** login local com seis usuários de demonstração (`admin`/`ADMIN`, `analistaRh`/`RH_ANALISTA`, `gestorRh`/`RH_GESTOR`, `coordenador`/`gerente`/`diretor`/`LIDERANCA` — ver tabela abaixo) — senhas nunca em texto puro, só hash Argon2id. JWT Bearer expira em 30 min, token só em memória no Angular (nunca `localStorage`), `JWT_SECRET` obrigatório via ambiente/`.env` (sem fallback funcional — ver "Configuração obrigatória" abaixo). `LIDERANCA` só vê/age sobre sua subárvore hierárquica inteira (`coordenador` ⊂ `gerente` ⊂ `diretor`, mesma cadeia real do seed); um objeto fora do escopo de qualquer usuário não aparece em listagem e, por id direto, responde `404` (nunca `403` — não revela existência). `ADMIN` é a única exceção que atravessa qualquer subárvore/departamento e pode decidir a própria solicitação. O Angular navega por scopes recebidos do backend (`scopeGuard`, sem matriz própria) — a autorização real é sempre reconferida no backend. Ver [`docs/decisoes/0012-autenticacao-local-jwt-rbac.md`](docs/decisoes/0012-autenticacao-local-jwt-rbac.md) e [`docs/decisoes/0013-bola-escopo-hierarquico.md`](docs/decisoes/0013-bola-escopo-hierarquico.md).

**Revisão E2E (2026-08-20):** testes no navegador sobre a entrega anterior encontraram e corrigiram não conformidades reais — `BLOQUEADA` deixava uma etapa nunca alcançada aparecer como "aguardando aprovação" (detalhe e histórico), a tela de Aprovações virou tabela pesquisável/ordenável (com um bug real de alinhamento de coluna corrigido), os cinco tipos de movimentação passaram a ser criáveis com colaborador pesquisável por nome/matrícula, entre outras (`specs/001-movimentacoes/tasks.md` T-83–T-92, [ADR-0018](docs/decisoes/0018-revisao-e2e-2026-08-20.md)).

**Revisão corretiva (2026-08-19):** uma verificação de ponta a ponta após a entrega inicial encontrou e corrigiu divergências reais — atalho de promoção Júnior→Pleno num passo só, snapshot do detalhe usando estado vivo do colaborador em vez da solicitação, aprovação adicional de promoção incompleta, `JWT_SECRET` com fallback hardcoded, entre outras (`specs/001-movimentacoes/tasks.md` T-73–T-82, [`DECISIONS.md`](DECISIONS.md)).

- Documentação funcional completa: [`specs/001-movimentacoes/spec.md`](specs/001-movimentacoes/spec.md)
- Decisões técnicas: [`DECISIONS.md`](DECISIONS.md) e [`docs/decisoes/`](docs/decisoes/)
- Arquitetura e evolução: [`docs/architecture.md`](docs/architecture.md)
- Operação e sustentação: [`docs/operations.md`](docs/operations.md)
- Catálogo das 37 regras: [`docs/regras/catalogo-regras.md`](docs/regras/catalogo-regras.md)
- Uso de IA no desenvolvimento: [`docs/IA_REPORT.md`](docs/IA_REPORT.md)

## Pré-requisitos

- Python 3.11+ (testado com 3.12)
- Node.js 20+ e npm (testado com Node 22.18, Angular CLI 18)
- Nenhuma infraestrutura externa — tudo roda localmente (SQLite em arquivo, fila de validação no mesmo banco)

## Backend (FastAPI)

Porta: **8000**. Banco: arquivo SQLite em `backend/portal_mobilidade.db` (criado automaticamente na primeira execução).

```bash
cd backend
python -m venv .venv
```

Windows:

```bash
.venv/Scripts/pip install -e ".[dev]"
```

macOS/Linux:

```bash
.venv/bin/pip install -e ".[dev]"
```

### Configuração obrigatória: `JWT_SECRET`

`JWT_SECRET` não tem mais valor padrão hardcoded no repositório (revisão corretiva de 2026-08-19, T-77) — sem ele, `Settings()` falha explicitamente na importação e nada sobe (nem o seed, nem o `uvicorn`). Copie o exemplo e gere um valor local:

```bash
cd backend
cp .env.example .env
python -c "import secrets; print(secrets.token_urlsafe(48))"   # cole o resultado em JWT_SECRET= no .env
```

`backend/.env` nunca é commitado (`.gitignore`); `backend/.env.example` documenta a variável sem conter segredo funcional. A suíte de testes injeta seu próprio segredo automaticamente (`tests/conftest.py`) — não depende deste `.env`.

Popule o banco com solicitações fictícias determinísticas e agende automaticamente as que já estão aptas (idempotente — pode rodar mais de uma vez sem duplicar movimentações nem jobs):

```bash
.venv/Scripts/python -m app.seed.seed   # Windows
.venv/bin/python -m app.seed.seed       # macOS/Linux
```

O seed já executa o producer ao final e imprime quantas solicitações foram agendadas, bloqueadas (aprovação reprovada), ficaram aguardando aprovação, ou anômalas (integridade de aprovação quebrada — cenário de teste). Também cria os seis usuários de demonstração autenticáveis (ver abaixo), um cenário dedicado de trilha granular de promoção (duas famílias de cargo, onze solicitações nomeadas cobrindo P03/P07/P08/P09 — incluindo Pleno3→Sênior1) e um cenário dedicado do bundle de aprovação adicional (GERENCIA e DIRETORIA, com a hierarquia real diretor→gerente→coordenador, T-75/T-79).

Suba a API:

```bash
.venv/Scripts/python -m uvicorn app.main:app --reload --port 8000   # Windows
.venv/bin/python -m uvicorn app.main:app --reload --port 8000       # macOS/Linux
```

- API: http://localhost:8000
- **Swagger/OpenAPI:** http://localhost:8000/docs (e `http://localhost:8000/redoc` para Redoc)

### Login de demonstração

O seed cria seis usuários autenticáveis (senhas só como hash Argon2id — nunca texto puro; `coordenador`/`gerente`/`diretor` usam o mesmo perfil técnico `LIDERANCA` — RC-52, a capacidade real vem da hierarquia/BOLA/`papel_lideranca`, não de um perfil por cargo):

| Usuário | Senha | Perfil | Pode |
|---|---|---|---|
| `admin` | `admin` | `ADMIN` | Ver/criar/aprovar tudo, fora de qualquer subárvore — único perfil que pode aprovar a própria solicitação |
| `analistaRh` | `analistaRh` | `RH_ANALISTA` | Ver tudo, criar solicitações — nunca aprova |
| `gestorRh` | `gestorRh` | `RH_GESTOR` | Decide as etapas de perfil `RH`/`GESTOR_RH`/`GESTOR_RH_ADICIONAL` |
| `coordenador` | `coordenador` | `LIDERANCA` | Vê/age só na própria (menor) subárvore hierárquica |
| `gerente` | `gerente` | `LIDERANCA` | Subárvore maior que `coordenador`; cargo com `papel_lideranca=GERENCIA` — resolvido como aprovador de etapas `GERENCIA` de promoção |
| `diretor` | `diretor` | `LIDERANCA` | Subárvore que cobre toda a hierarquia demo; cargo com `papel_lideranca=DIRETORIA` — resolvido como aprovador de etapas `DIRETORIA` |

`POST /auth/login` devolve um JWT (`accessToken`, expira em 30 min). Toda rota protegida exige `Authorization: Bearer <token>`.

### Bloqueio de força bruta e reset

3 falhas de login em 5 minutos bloqueiam o IP por 30 minutos (`429` + `Retry-After`), persistido em `SecurityLockout`. Para a apresentação, limpar só os bloqueios sem apagar dados:

```bash
.venv/Scripts/python -m app.security.reset_lockouts   # Windows
.venv/bin/python -m app.security.reset_lockouts        # macOS/Linux
```

Apagar `portal_mobilidade.db*` e rodar o seed de novo também limpa os bloqueios, mas não é o único jeito.

### Worker de validação (processamento automático)

**Precisa estar rodando** para que solicitações agendadas sejam efetivamente validadas — sem ele, jobs ficam `PENDENTE` na fila indefinidamente. É um processo Python independente, em outro terminal:

```bash
.venv/Scripts/python -m app.processing.worker   # Windows
.venv/bin/python -m app.processing.worker       # macOS/Linux
```

Ele consome o job pendente mais antigo, chama o mesmo `ValidacaoService` usado por `POST /validar`, grava auditoria e atualiza a movimentação — em loop contínuo (poll a cada poucos segundos quando a fila está vazia). Para parar, `Ctrl+C`.

### Rodar os testes do backend

```bash
cd backend
.venv/Scripts/python -m pytest -q   # Windows
.venv/bin/python -m pytest -q       # macOS/Linux
```

## Frontend (Angular)

Porta: **4200**. Espera a API em `http://localhost:4200` → `http://localhost:8000` (ver `frontend/src/app/core/services/api-config.ts` para trocar a URL base, caso a API rode em outra porta/host).

```bash
cd frontend
npm install
npm start
```

(`npm start` executa `ng serve`.) Acesse http://localhost:4200 — redireciona para `/login` se não houver sessão. Depois do login (ver credenciais acima), o menu mostra "Movimentações" (todos), "Nova solicitação" (perfis com escopo de criação) e "Aprovações" (perfis com escopo de aprovação) — a exibição do menu é só conveniência de UX; o backend reautoriza cada chamada independentemente do que o menu mostra. O token fica só em memória (nunca `localStorage`) — um reload completo da página exige novo login (aceito no MVP).

O frontend nunca decide validade nem elegibilidade de negócio — mas o detalhe mostra o botão "Validar agora" sempre que o backend retorna `processamento.podeValidarManualmente=true` (na prática, movimentações `PENDENTE` cujo processamento ainda não terminou ou pode ser retomado); roda a validação sob demanda mesmo com o Worker parado, pelo mesmo orquestrador que ele usa. Toda movimentação mostra, ao final, um histórico de processamento real (`HistoricoProcessamento`) persistido pelo backend, com o ator e o solicitante quando aplicável — sem nenhum evento sintetizado no cliente. `BLOQUEADA`/`AGUARDANDO_APROVACAO` mostram os impedimentos de aprovação em vez de uma última validação (que ainda não existe, pois a engine não rodou). A listagem e o detalhe mostram `motivoResumo` (calculado pelo backend, nunca montado no Angular) e o solicitante da movimentação.

### Rodar os testes do frontend

```bash
cd frontend
npm test -- --watch=false --browsers=ChromeHeadless
```

## Fluxo de ponta a ponta para avaliação

1. Suba o backend e rode o seed (passos acima) — o seed já agenda automaticamente as solicitações aptas e cria `admin`/`analistaRh`.
2. Suba o **Worker** (em outro terminal) — ele começa a consumir a fila imediatamente, recuperando qualquer job travado antes de começar.
3. Suba o frontend e acesse http://localhost:4200 — entre com `admin`/`admin`.
4. Listagem de movimentações com `ID` como primeira coluna, busca (aceita ID numérico, matrícula ou nome), filtro pelos cinco status, ordenação por coluna (com desempate determinístico por id), paginação e as colunas **Solicitante**/**Motivo** (`motivoResumo` curto, calculado pelo backend — só essa célula quebra linha), tudo resolvido no servidor. Como `coordenador`/`gerente`/`diretor` (todos `LIDERANCA`), a listagem só mostra a subárvore hierárquica do usuário, aninhada nessa ordem — `admin`/`analistaRh`/`gestorRh` veem tudo. O item ativo do menu (`Movimentações`/`Nova solicitação`/`Aprovações`) fica destacado conforme a rota atual.
5. Clique em uma linha para abrir o detalhe: dados, solicitante, origem/destino conforme o tipo, aprovações e a última validação. Em `BLOQUEADA`/`AGUARDANDO_APROVACAO`, o detalhe mostra os impedimentos reais (qual aprovação falta ou quem reprovou) em vez de "nenhuma inconsistência". O botão "Validar agora" só aparece quando o backend confirma que há algo para processar (`processamento.podeValidarManualmente`). Uma solicitação `APROVADA` reflete a efetivação real no cadastro do colaborador e mostra o histórico de processamento completo, com ator/solicitante em cada evento.
6. Em "Nova solicitação", crie qualquer um dos cinco tipos (`TRANSFERENCIA`/`PROMOCAO`/`MUDANCA_CENTRO_CUSTO`/`TROCA_GESTOR`/`ALTERACAO_ESTRUTURA`) — o colaborador é localizado digitando nome ou matrícula (autocomplete, resultados já filtrados por BOLA pelo backend); origem e solicitante são sempre derivados pelo backend a partir do JWT, nunca enviados pelo formulário.
7. Em "Aprovações", a tabela é pesquisável (ID/matrícula/nome) e ordenável (ID/data/tipo/solicitante/colaborador/setor, padrão data mais recente primeiro) — decida (Aprovar azul/Reprovar vermelho, com justificativa opcional) as etapas que o usuário logado pode decidir; a tela só mostra o que `GET /aprovacoes/pendentes` devolve e recarrega da API após cada decisão. Como `admin`, é possível aprovar a própria solicitação e decidir fora de qualquer subárvore (única exceção do sistema); como `diretor`, reprovar uma etapa `DIRETORIA` bloqueia a movimentação terminalmente — nenhuma etapa posterior (ex.: `GESTOR_RH_ADICIONAL`) aparece como pendente em lugar nenhum depois disso.
8. Abra http://localhost:8000/docs para explorar a API diretamente pelo Swagger (autentique com "Authorize" usando o Bearer de `POST /auth/login`) — o mesmo orquestrador que o botão "Validar agora" do Angular aciona. Uma aprovação pendente/reprovada, ou uma solicitação já concluída, retorna `409` com os impedimentos atuais em vez de rodar a engine.
9. Rode os testes automatizados de backend e frontend (comandos acima).

## Estrutura do projeto

```
portal-mobilidade/
├── README.md
├── DECISIONS.md
├── docs/                     # arquitetura, operação, catálogo de regras, ADRs, IA_REPORT
├── specs/001-movimentacoes/  # spec.md, plan.md, tasks.md (SDD)
├── backend/
│   └── app/
│       ├── api/              # rotas, schemas Pydantic, contrato de erro, middleware de hardening
│       ├── security/         # senha (Argon2id), JWT, RBAC, BOLA, lockout, rate limit, cache de referência
│       ├── services/         # monta contexto, valida, efetiva, compõe detalhe, solicitação, aprovação
│       ├── processing/       # gate de aprovação, producer, orquestrador único
│       │                     # (Worker e POST /validar), Worker
│       ├── validation/       # as 37 regras + engine + política dinâmica de aprovação — puro, sem I/O
│       ├── repositories/     # consultas, paginação, auditoria e histórico
│       │                     # append-only, fila (JobValidacao)
│       ├── models/           # ORM (SQLAlchemy): Usuario, SecurityLockout, JobValidacao,
│       │                     # HistoricoProcessamento etc.
│       └── seed/             # seed idempotente (usuários, solicitações + producer)
└── frontend/
    └── src/app/
        ├── core/              # models (DTOs), services (auth/movimentação/solicitação/aprovação/referência),
        │                      # guards (authGuard, scopeGuard), interceptors (authInterceptor)
        └── features/
            ├── auth/login/
            ├── movimentacoes/{listagem,detalhe,inconsistencias}/
            ├── solicitacoes/nova/
            └── aprovacoes/
```

## Desempenho (CA-021/CA-046, RNF-01/RNF-02)

O requisito do case é até **5.000 movimentações/dia** — distribuído uniformemente, isso é **≈0,058 movimentação/s em média**. Este README não assume nenhum pico específico sem hipótese de negócio documentada (`docs/architecture.md` §3). A fila local existe para **desacoplar o gatilho de validação e amortecer rajadas**, não porque a média exija infraestrutura distribuída.

Medição real via `backend/scripts/benchmark_performance.py` (SQLite de arquivo temporário, seed completo — 141 movimentações, incluindo os cenários dedicados de promoção do T-69/T-73/T-79 —, `TestClient` medindo a camada de aplicação real: queries + serialização, sem overhead de rede; reexecutada na revisão E2E de 2026-08-20, T-90):

| Endpoint | p50 | p95 | máx |
|---|---|---|---|
| `GET /movimentacoes` (paginado, várias páginas/filtros — 42 chamadas) | 7,0 ms | 19,2 ms | 74,0 ms |
| `GET /movimentacoes/{id}` (100 chamadas) | 8,4 ms | 10,6 ms | 48,3 ms |

Todos muito abaixo do limite de 2s exigido (RNF-01/spec §13) — por uma margem de ~100x. Otimizações aplicadas antes de qualquer cache: BOLA aplicado na query antes da paginação, aprovações buscadas em lote por página (não uma consulta por linha), consulta de última validação só quando o status realmente precisa dela. Cache local TTL curto (60s, configurável) só para `cargos`/`departamentos`/`centros de custo` (`GET /referencias/*`) — nunca para senha, JWT, aprovação, status/timeline de movimentação ou qualquer decisão de autorização/BOLA. Reexecute `python -m scripts.benchmark_performance` (a partir de `backend/`) para medir de novo se o schema/seed mudar.

**Tempo de consumo do Worker:** medido drenando a fila gerada pelo seed (`worker.drenar_fila`, banco recém-populado) — 89 jobs processados em **≈1,85 s** no total, **≈20,7 ms por job** em média (mesma engine de `POST /validar`, mais o custo do orquestrador: reavaliação do gate, aquisição condicional do job, efetivação local e registro de histórico; medido novamente na revisão E2E de 2026-08-20). Ver `docs/operations.md` §1.1 para as consultas usadas para medir isso a qualquer momento sobre um banco real.

## Suíte de testes

- **Backend:** `pytest -q` → **448 testes**, 0 falhas.
- **Frontend:** `ng test --browsers=ChromeHeadless` → **92 testes**, 0 falhas. `ng build` verde (um aviso não bloqueante de orçamento de CSS em `detalhe.component.css`).

## Notas

- O motor de validação (`backend/app/validation/`) é o núcleo do produto: funções puras, sem banco, sem framework — testáveis isoladamente (`backend/tests/validation/`).
- O Worker e `POST /validar` chamam exatamente o mesmo orquestrador (`processing/orchestrator.py`) e o mesmo `ValidacaoService` — nenhuma das 37 regras é reimplementada (`backend/tests/processing/test_orchestrator.py`).
- O frontend nunca decide se uma movimentação é válida, nunca deriva elegibilidade de validação manual, nunca calcula quem pode aprovar o quê nem em que ordem, e nunca sintetiza histórico — apenas apresenta o que o backend já decidiu e persistiu. O menu por perfil é só exibição; toda autorização real é reconferida no backend a cada chamada.
- Uma validação `APROVADA` efetiva a movimentação no cadastro do colaborador (`departamento`/`cargo`/`gestor`/`centro de custo`/`estrutura`, conforme o tipo) — inclui, para `PROMOCAO`, o incremento do custo comprometido do centro de custo atual.
- Senha nunca é persistida nem cacheada em texto puro — só o hash Argon2id. O token JWT nunca é persistido no frontend (só em memória).
- Para reiniciar os dados do zero em desenvolvimento, apague `backend/portal_mobilidade.db*` e rode o seed novamente — isso também limpa qualquer bloqueio de força bruta ativo.
