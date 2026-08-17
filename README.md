# Portal de Mobilidade Organizacional

MVP local de acompanhamento de movimentações organizacionais (transferência, promoção, troca de gestor, mudança de centro de custo, alteração de estrutura), com um motor de validação determinístico que retorna **todas** as inconsistências encontradas e persiste uma trilha de auditoria append-only.

A validação é **automática**: assim que as aprovações exigidas de uma movimentação são concluídas, um producer local agenda a validação em uma fila persistida (`JobValidacao`), consumida por um **Worker Python** independente. O Angular é somente consulta/relatório — não existe botão de validar. `POST /validar` continua disponível como adaptador técnico síncrono (Swagger, testes), mas o produto não depende dele.

- Documentação funcional completa: [`specs/001-movimentacoes/spec.md`](specs/001-movimentacoes/spec.md)
- Decisões técnicas: [`DECISIONS.md`](DECISIONS.md) e [`docs/decisoes/`](docs/decisoes/)
- Arquitetura e evolução: [`docs/architecture.md`](docs/architecture.md)
- Operação e sustentação: [`docs/operations.md`](docs/operations.md)
- Catálogo das 34 regras: [`docs/regras/catalogo-regras.md`](docs/regras/catalogo-regras.md)
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

Popule o banco com solicitações fictícias determinísticas e agende automaticamente as que já estão aptas (idempotente — pode rodar mais de uma vez sem duplicar movimentações nem jobs):

```bash
.venv/Scripts/python -m app.seed.seed   # Windows
.venv/bin/python -m app.seed.seed       # macOS/Linux
```

O seed já executa o producer ao final e imprime quantas solicitações foram agendadas, bloqueadas (aprovação reprovada), ficaram aguardando aprovação, ou anômalas (integridade de aprovação quebrada — cenário de teste).

Suba a API:

```bash
.venv/Scripts/python -m uvicorn app.main:app --reload --port 8000   # Windows
.venv/bin/python -m uvicorn app.main:app --reload --port 8000       # macOS/Linux
```

- API: http://localhost:8000
- **Swagger/OpenAPI:** http://localhost:8000/docs (e `http://localhost:8000/redoc` para Redoc)

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

(`npm start` executa `ng serve`.) Acesse http://localhost:4200 com o backend já rodando na porta 8000. O frontend é consulta/relatório — nunca decide validade — mas o detalhe de uma solicitação `PENDENTE`/`REPROVADA` mostra o botão "Validar agora" (ADR-0010), que roda a validação sob demanda mesmo com o Worker parado. Uma solicitação `APROVADA` mostra em vez disso um histórico da solicitação, com uma última entrada explicitamente marcada como cenário ilustrativo.

### Rodar os testes do frontend

```bash
cd frontend
npm test -- --watch=false --browsers=ChromeHeadless
```

## Fluxo de ponta a ponta para avaliação

1. Suba o backend e rode o seed (passos acima) — o seed já agenda automaticamente as solicitações aptas.
2. Suba o **Worker** (em outro terminal) — ele começa a consumir a fila imediatamente.
3. Suba o frontend.
4. Acesse http://localhost:4200 — listagem de movimentações com busca, filtro por status, ordenação por coluna e paginação, tudo resolvido no servidor. Movimentações `PENDENTE` aguardando aprovação e `REPROVADA` bloqueadas pelo gate aparecem lado a lado com as já `APROVADA`/`REPROVADA` pelo Worker.
5. Clique em uma linha para abrir o detalhe: dados, origem/destino conforme o tipo, aprovações e a última validação. Se ainda não há validação, o detalhe explica por quê (aguardando aprovação/processamento, ou bloqueada por reprovação) e mostra o botão "Validar agora" — a única ação manual do frontend, disponível só em `PENDENTE`/`REPROVADA` (ADR-0010). Uma solicitação `APROVADA` não tem botão: mostra em vez disso um histórico da solicitação, com uma última entrada marcada como cenário ilustrativo.
6. Abra http://localhost:8000/docs para explorar `GET /movimentacoes`, `GET /movimentacoes/{id}` e o adaptador técnico `POST /validar` diretamente pelo Swagger — o mesmo endpoint que o botão "Validar agora" do Angular chama.
7. Rode os testes automatizados de backend e frontend (comandos acima).

## Estrutura do projeto

```
portal-mobilidade/
├── README.md
├── DECISIONS.md
├── docs/                     # arquitetura, operação, catálogo de regras, ADRs, IA_REPORT
├── specs/001-movimentacoes/  # spec.md, plan.md, tasks.md (SDD)
├── backend/
│   └── app/
│       ├── api/              # rotas, schemas Pydantic, contrato de erro
│       ├── services/         # orquestração — monta contexto, chama o motor, persiste
│       ├── processing/       # gate de aprovação, producer idempotente, Worker
│       ├── validation/       # as 34 regras + engine — puro, sem I/O
│       ├── repositories/     # consultas, paginação, auditoria append-only, fila
│       ├── models/           # ORM (SQLAlchemy), incluindo JobValidacao
│       └── seed/             # seed idempotente (solicitações + producer)
└── frontend/
    └── src/app/
        ├── core/              # models (DTOs) e services (MovimentacaoService — somente GETs)
        └── features/movimentacoes/
            ├── listagem/
            ├── detalhe/
            └── inconsistencias/
```

## Desempenho (CA-021/CA-046, RNF-01/RNF-02)

O requisito do case é até **5.000 movimentações/dia** — distribuído uniformemente, isso é **≈0,058 movimentação/s em média**. Este README não assume nenhum pico específico sem hipótese de negócio documentada (`docs/architecture.md` §3). A fila local existe para **desacoplar o gatilho de validação e amortecer rajadas**, não porque a média exija infraestrutura distribuída.

Medição local (`curl -w "%{time_total}"`, 5 execuções por endpoint) com o banco populado pelo seed (126 movimentações), servidor rodando via `uvicorn` sem `--reload`:

| Endpoint | Tempo observado |
|---|---|
| `GET /movimentacoes?pageSize=20` | ~5–16 ms |
| `GET /movimentacoes/{id}` | ~4–40 ms |
| `POST /validar` | ~9–12 ms |

Todos os três, muito abaixo do limite de 2s exigido (RNF-01). Nenhum cache ou componente de infraestrutura adicional foi introduzido para atingir esse resultado — paginação obrigatória, índices (`plan.md` §7.1) e carga em consulta única (`docs/architecture.md` §1.2) já são suficientes no volume do MVP.

**Tempo de consumo do Worker:** medido drenando a fila gerada pelo seed (`worker.drenar_fila`, banco recém-populado) — 62 jobs processados em **687 ms** no total, **≈11 ms por job** em média (mesma engine e mesma carga única de `POST /validar`, sem I/O adicional). Ver `docs/operations.md` §1.1 para as consultas usadas para medir isso a qualquer momento sobre um banco real.

## Notas

- O motor de validação (`backend/app/validation/`) é o núcleo do produto: funções puras, sem banco, sem framework — testáveis isoladamente (`backend/tests/validation/`).
- O Worker e `POST /validar` chamam exatamente o mesmo `ValidacaoService` — nenhuma das 34 regras é reimplementada (`backend/tests/processing/test_worker.py`).
- O frontend nunca decide se uma movimentação é válida nem dispara validação — apenas apresenta o resultado já produzido pelo backend (verificado por `tests/api/test_movimentacoes_api.py`, `frontend/src/app/core/services/movimentacao.service.spec.ts` e `detalhe.component.spec.ts`).
- Para reiniciar os dados do zero em desenvolvimento, apague `backend/portal_mobilidade.db*` e rode o seed novamente.
