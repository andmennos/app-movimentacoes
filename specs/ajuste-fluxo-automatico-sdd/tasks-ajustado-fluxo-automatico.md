# tasks.md — Portal de Mobilidade Organizacional

**Feature:** 001-movimentacoes
**Depende de:** `spec.md`, `plan.md`
**Status:** Implementação base concluída em 2026-08-15. **Revisão arquitetural aberta em 2026-08-16** para remover validação manual do frontend e introduzir processamento automático local. Tarefas afetadas foram reabertas e T-41 a T-44 foram adicionadas.

---

## 0. Regras de execução

| # | Regra |
|---|---|
| E-01 | Nenhuma tarefa inicia antes da revisão e aprovação do SDD. |
| E-02 | Uma tarefa só inicia com **todas** as suas dependências concluídas. |
| E-03 | Uma tarefa só é concluída quando **todos** os seus critérios de conclusão estão verificados. |
| E-04 | Nenhuma tarefa pode alterar decisões congeladas (`spec.md` §0). Divergência identificada durante a execução → parar e escalar, não decidir sozinho. |
| E-05 | Nenhuma tarefa adiciona tecnologia listada em RC-11. |
| E-06 | Nenhuma tarefa adiciona, remove ou renumera regra do catálogo. |

---

## 1. Mapa de fases

A implementação base T-01…T-40 existe e deve ser **ajustada**, não reescrita do zero.

```text
Base existente
F1 Fundação → F2 Persistência → F3 Motor → F4 API → F5 Frontend → F6 Fechamento

Revisão 2026-08-16
T-41 JobValidacao
      ↓
T-42 Producer / gate
      ↓
T-43 Worker
      ↓
T-44 Testes do processamento automático
      ↓
Reabrir T-09 / T-26 / T-27 / T-30 / T-33 / T-34 / T-38 / T-39 / T-40
```

Princípio da revisão: **o Angular deixa de disparar validação**. O fluxo normal passa a ser `aprovações concluídas → producer → JobValidacao → Worker → ValidacaoService → engine → auditoria → status`.

`POST /validar` permanece na API para cumprir o contrato do case e para Swagger/testes.

---

## Fase 1 — Fundação

### T-01 · Estrutura do projeto backend
**Depende de:** —
**Entrega:** árvore de diretórios de `plan.md` §4, `pyproject.toml`, configuração de pytest.
**Conclusão:**
- [x] Estrutura criada conforme `plan.md` §4, sem diretórios extras
- [x] `pytest` executa e coleta zero testes sem erro
- [x] Nenhuma dependência fora de FastAPI, SQLAlchemy, Pydantic, pytest e utilitários diretos

### T-02 · Configuração de banco e sessão
**Depende de:** T-01
**Entrega:** `database.py`, `config.py`.
**Conclusão:**
- [x] `journal_mode=WAL` ativo
- [x] `foreign_keys=ON` ativo e verificado por teste
- [x] Sessão por request; fixture de sessão em memória disponível para testes

---

## Fase 2 — Persistência

### T-03 · Modelos ORM
**Depende de:** T-02
**Entrega:** todas as entidades de `spec.md` §4.1.
**Conclusão:**
- [x] 9 entidades mapeadas com os atributos da spec
- [x] `Movimentacao` com as **10 FKs explícitas nullable** de `spec.md` §4.1 — nenhum campo polimórfico
- [x] `Cargo` com `nivel`, `permite_gestao`, `aprovacao_adicional` (enum `GERENCIA \| DIRETORIA \| null`)
- [x] `EstruturaOrganizacional` com `estrutura_pai_id`
- [x] Enums de `tipo`, `status`, `estado` de aprovação e `resultado` conforme a spec
- [x] Teste de criação de schema passa

### T-04 · Índices
**Depende de:** T-03
**Entrega:** índices de `plan.md` §7.1.
**Conclusão:**
- [x] Os 8 índices criados
- [x] Teste verifica presença dos índices no schema

### T-05 · Repositório de movimentações
**Depende de:** T-04
**Entrega:** listagem com filtro, busca, ordenação e paginação; consulta por id.
**Conclusão:**
- [x] Filtro por `status` funcional
- [x] Busca por matrícula exata **ou** nome parcial case-insensitive
- [x] Ordenação por whitelist, asc/desc; valor fora da whitelist rejeitado na camada
- [x] Paginação com limite máximo 100 aplicado no repositório
- [x] Testes de persistência cobrindo cada um dos itens acima

### T-06 · Repositório de aprovações
**Depende de:** T-04
**Conclusão:**
- [x] Consulta de aprovações por movimentação
- [x] Teste de carga em consulta única (sem N+1)

### T-07 · Repositório de auditoria — append-only
**Depende de:** T-04
**Conclusão:**
- [x] Expõe apenas `criar` e `buscar_ultima`
- [x] **Nenhum método de update ou delete existe** (verificado por inspeção e por teste)
- [x] Teste: revalidar cria novo registro sem alterar os anteriores (CA-013)

### T-08 · Builders de teste
**Depende de:** T-03
**Entrega:** `tests/builders/`.
**Conclusão:**
- [x] Builders para Colaborador, Cargo, Departamento, CentroCusto, EstruturaOrganizacional, Movimentacao, Aprovacao
- [x] Todos produzem entidade **válida** por padrão; teste declara apenas o desvio

### T-09 · Seed — REABERTA NA REVISÃO
**Depende de:** T-05, T-06, T-42
**Entrega:** seed idempotente conforme `spec.md` §12.

**Base já existente:**
- [x] Toda movimentação possui todas as linhas de aprovação exigidas pelo seu tipo
- [x] `Departamento.gestor_id` e `CentroCusto.responsavel_id` preenchidos
- [x] ≥ 100 movimentações
- [x] Cenários hierárquicos/estruturais necessários às regras
- [x] Reexecução não duplica movimentações
- [x] Nenhum dado real

**Ajustes da revisão:**
- [ ] Seed passa a ser descrito e implementado como **simulação de solicitações recebidas**, não como ações de usuário do portal
- [ ] Dataset contém aprovações `PENDENTE`, `APROVADA` e `REPROVADA`
- [ ] Ao final do seed, o producer é executado
- [ ] Movimentações com aprovação pendente permanecem `PENDENTE` e não recebem `JobValidacao`
- [ ] Movimentações com aprovação rejeitada ficam bloqueadas `REPROVADA` e não recebem `JobValidacao`
- [ ] Movimentações com todas as aprovações aprovadas recebem exatamente um `JobValidacao`
- [ ] Reexecutar seed + producer não duplica jobs

---

## Fase 3 — Motor de validação

### T-10 · `types.py`
**Depende de:** T-01
**Entrega:** `ValidationContext`, `Inconsistencia`, enums de validação.
**Conclusão:**
- [x] Estruturas simples, sem ORM
- [x] `ValidationContext` contempla todos os campos de `plan.md` §5.1, incluindo `cadeia_hierarquica`, `responsaveis_derivados` e `conflitos`
- [x] Nenhum import de SQLAlchemy, FastAPI ou Pydantic

### T-11 · Teste de arquitetura de imports
**Depende de:** T-10
**Entrega:** `tests/arquitetura/`.
**Conclusão:**
- [x] Teste falha se `validation/` importar `sqlalchemy`, `fastapi`, `pydantic` ou `app.models` (INV-01, V-04)
- [x] Teste executa antes das demais tarefas da fase

### T-12 · `aprovacoes.py`
**Depende de:** T-10
**Entrega:** exigências por tipo + verificação de integridade.
**Conclusão:**
- [x] `EXIGENCIAS_POR_TIPO` conforme `spec.md` §5.2
- [x] Para PROMOCAO, acrescenta `cargo_destino.aprovacao_adicional` quando não for `null`
- [x] Nenhum outro tipo consulta `aprovacao_adicional` (RC-05)
- [x] Verificação de integridade conforme `spec.md` §5.3, emitindo sob o **código público da regra do tipo**, sem código próprio
- [x] Resolução do responsável esperado por `GESTOR_ORIGEM`/`GESTOR_DESTINO` segue exatamente `spec.md` §5.3.1 por tipo — não decidida durante a implementação
- [x] Testes cobrindo os 3 itens de integridade e os 5 mapeamentos de §5.3.1

### T-13 · `common.py` — G01 a G04
**Depende de:** T-10, T-08
**Conclusão:**
- [x] Exatamente 4 regras; nenhuma verifica existência/atividade de departamento, cargo, CC, estrutura ou gestor
- [x] G04 detecta conflito apenas do **mesmo tipo**, mesmo colaborador, `status = PENDENTE`, id diferente
- [x] Cada regra com cenário que dispara e cenário que suprime (CA-034)
- [x] Pré-condições respeitadas: G02 e G04 não avaliam se G01 falhou

### T-14 · `transferencia.py` — T01 a T06
**Depende de:** T-12, T-13
**Conclusão:**
- [x] Exatamente 6 regras, códigos T01–T06
- [x] Pré-condições: T02 exige T01; T04 exige T03; T05 exige T01 e T03
- [x] CN-N03 emite `T03` **apenas** (CA-010)
- [x] Cenários CN-N03, CN-N04, CN-N05 verificados
- [x] Cenário de múltiplas inconsistências do tipo (CA-036)

### T-15 · `promocao.py` — P01 a P06
**Depende de:** T-12, T-13
**Conclusão:**
- [x] Exatamente 6 regras, códigos **P01–P06**
- [x] **`P01` é "cargo de destino existe"**, não "colaborador ativo" — a regra de colaborador ativo é `G02` e não se repete aqui (PA-01 = B)
- [x] `P06` implementa a *Política de aprovação de promoção baseada no cargo de destino*; a denominação "mecanismo de aprovação superior" não aparece no código nem em comentários
- [x] Nenhuma referência a tempo de empresa, tempo no cargo, avaliação, faixa salarial ou headcount (RC-06)
- [x] Cenários CN-N06, CN-N07, CN-N08, CN-N09 verificados
- [x] Cenário CN-M02 verificado

### T-16 · `centro_custo.py` — CC01 a CC06
**Depende de:** T-12, T-13
**Conclusão:**
- [x] Exatamente 6 regras, códigos CC01–CC06
- [x] Pré-condições análogas às de transferência
- [x] Cenários CN-N14, CN-N15 verificados
- [x] Cenário de múltiplas inconsistências do tipo

### T-17 · `troca_gestor.py` — TG01 a TG06
**Depende de:** T-12, T-13
**Conclusão:**
- [x] Exatamente 6 regras, códigos TG01–TG06
- [x] `TG05` implementa o algoritmo de `spec.md` §6.5, com conjunto de visitados **e** limite de profundidade
- [x] Cenários CN-N10, CN-N11, CN-N12, CN-N13 verificados
- [x] CA-038: dados com ciclo pré-existente não causam laço infinito
- [x] Cenário CN-M03 verificado

### T-18 · `estrutura.py` — AE01 a AE06
**Depende de:** T-12, T-13
**Conclusão — leitura obrigatória de `spec.md` §9 antes de iniciar:**
- [x] Exatamente 6 regras, códigos AE01–AE06
- [x] **`AE05` é `origem ≠ destino`** (RC-03)
- [x] **Nenhuma regra de ciclo organizacional existe neste módulo, sob nenhum código**
- [x] **O módulo não referencia `estrutura_pai_id` em nenhum ponto** (spec §9.1 item 3 — verificado por revisão de código, sem teste automatizado dedicado)
- [x] Cenário CN-N16 e CN-N17 verificados
- [x] Cenário de múltiplas inconsistências do tipo

### T-19 · Testes de anti-regressão de AE05
**Depende de:** T-18
**Entrega:** categoria própria de testes, não diluída entre os testes de estrutura.
**Conclusão:**
- [x] `test_ae_destino_ancestral_valida` — CN-A01: destino ancestral da origem, ambas ativas e distintas → **sem inconsistência de estrutura**
- [x] `test_ae_destino_descendente_valida` — CN-A02
- [x] `test_codigos_emitiveis_alteracao_estrutura` — CN-A04 / CA-028, conjunto exatamente `{G01, G02, G03, G04, AE01–AE06}`
- [x] Os dois testes comportamentais (`test_ae_destino_ancestral_valida`, `test_ae_destino_descendente_valida`) falham se a regra de ciclo for reintroduzida
- [x] **Sem teste estático de inspeção de `estrutura_pai_id`** — essa verificação é feita por revisão de código (`plan.md` V-03), não por teste automatizado, por testar implementação em vez de comportamento

> Esta tarefa existe porque `AE05` já foi especificado como regra de ciclo em versões anteriores da análise. Os testes comportamentais são a barreira que impede a reintrodução por inércia.

### T-20 · `engine.py`
**Depende de:** T-13 a T-18
**Conclusão:**
- [x] `REGRAS_POR_TIPO` com listas explícitas, sem herança
- [x] O conjunto total de códigos registrados é **exatamente 34** (V-01)
- [x] INV-02: não para na primeira inconsistência
- [x] INV-04: exceção não tratada em uma regra **propaga** (sem `try/except` por regra, sem `SYS01`); engine não a converte em inconsistência (CA-024)
- [x] INV-05: ordem determinística, gerais → específicas (CA-023)
- [x] Cenário CN-M04 não lança exceção

### T-21 · Resolução do resultado
**Depende de:** T-20, T-12
**Conclusão:**
- [x] Precedência de `plan.md` §5.4 implementada
- [x] Matriz de testes: CA-029, CA-030, CA-031, CA-032, CA-033
- [x] Cenário CN-P06 retorna `AGUARDANDO_APROVACAO`

---

## Fase 4 — API

### T-22 · Schemas e contrato de erro
**Depende de:** T-01
**Conclusão:**
- [x] Schemas de request/response conforme `spec.md` §8
- [x] Contrato de erro §8.4 com os 4 códigos
- [x] Swagger acessível

### T-23 · `GET /movimentacoes`
**Depende de:** T-05, T-22
**Conclusão:**
- [x] Contrato de `spec.md` §8.1
- [x] CA-001, CA-002, CA-003, CA-004, CA-005 verificados
- [x] `resultadoUltimaValidacao` nulo quando nunca validada

### T-24 · `GET /movimentacoes/{id}`
**Depende de:** T-05, T-06, T-07, T-22
**Conclusão:**
- [x] Contrato de `spec.md` §8.2
- [x] CA-006, CA-007, CA-008, CA-015 verificados
- [x] **Apenas a última validação** é exposta; nenhum histórico (RC-08)
- [x] Campos de origem/destino coerentes com o tipo

### T-25 · `POST /validar` + auditoria
**Depende de:** T-21, T-07, T-22
**Conclusão:**
- [x] Fluxo de `plan.md` §6 implementado, passos 1 a 10
- [x] Contrato de `spec.md` §8.3
- [x] CA-009, CA-011, CA-012, CA-014 verificados
- [x] INV-07: exatamente um registro de auditoria por validação concluída com resultado de negócio
- [x] Contexto carregado em **carga única**; teste verifica ausência de N+1
- [x] Transação: falha na persistência não deixa auditoria parcial
- [x] Exceção não tratada durante `engine.executar` ou persistência produz **500 `ERRO_INTERNO`**, rollback da transação, nenhum `ValidacaoAuditoria` criado, `Movimentacao` inalterada (CA-024, INV-04)

### T-26 · Testes de integração — REABERTA
**Depende de:** T-23, T-24, T-25, T-09, T-43, T-44
**Conclusão:**
- [ ] Fluxo automático: seed → producer → `JobValidacao` → Worker → auditoria → GET detalhe
- [ ] Cenário automático `APROVADA`
- [ ] Cenário automático `REPROVADA` por inconsistências
- [ ] Cenário `PENDENTE` por aprovação sem job e sem validação automática
- [ ] Cenário de aprovação `REPROVADA` bloqueado sem job
- [ ] `POST /validar` continua funcional de forma síncrona e usa o mesmo `ValidacaoService`
- [ ] Nenhuma lógica das 34 regras foi duplicada no Worker

---

## Fase 5 — Frontend — REABERTA

### T-27 · Modelos e service Angular
**Depende de:** T-22
**Conclusão:**
- [ ] Interfaces continuam espelhando os DTOs de consulta
- [ ] `MovimentacaoService` usado pelo produto expõe chamadas de `GET /movimentacoes` e `GET /movimentacoes/{id}`
- [ ] Remover chamada Angular a `POST /validar`
- [ ] Testes de service confirmam que o frontend não dispara validação

### T-28 · Listagem
**Depende de:** T-27, T-23
**Conclusão:**
- [x] Busca, filtro, ordenação e paginação via API
- [x] Nenhum filtro/ordenação/paginação executado no cliente
- [x] Testes dos controles existentes continuam passando

### T-29 · Detalhe
**Depende de:** T-27, T-24
**Conclusão:**
- [ ] Dados, origem/destino e aprovações exibidos
- [ ] `ultimaValidacao` exibida quando presente
- [ ] Quando `status=PENDENTE` e `ultimaValidacao=null`, interface comunica que a solicitação aguarda aprovação/processamento, sem sugerir ação manual
- [ ] Testes de componente atualizados

### T-30 · Inconsistências e relatório — REABERTA
**Depende de:** T-29
**Conclusão:**
- [ ] **Remover botão/ação de validar**
- [ ] Nenhum componente chama `POST /validar`
- [ ] Código e mensagem das inconsistências continuam exibidos exatamente como retornados
- [ ] Estados carregando, vazio, erro, sem inconsistências e aguardando aprovação/processamento continuam claros
- [ ] CA-018, CA-019, CA-020 e CA-039 verificados

---

## Fase 6 — Fechamento — PARCIALMENTE REABERTA

### T-31 · Catálogo de regras documentado
**Depende de:** T-20
**Conclusão:**
- [x] 34 regras documentadas
- [x] Extensões fictícias separadas
- [x] `AE05` mantida como `origem ≠ destino`
- [x] Nenhuma alteração de catálogo nesta revisão

### T-32 · ADRs
**Depende de:** T-31
**Conclusão:**
- [x] ADRs anteriores preservados
- [ ] Adicionar ADR da revisão: frontend de consulta + fila local `JobValidacao` + Worker
- [ ] Registrar trade-off SQLite queue agora vs. SQS na evolução

### T-33 · README — REABERTA
**Depende de:** T-26, T-30, T-43
**Conclusão:**
- [ ] Execução local em comandos explícitos para backend, seed, Worker e frontend
- [ ] Documentar `python -m app.processing.worker` (ou comando real equivalente)
- [ ] Explicar que o Worker deve permanecer em execução para processamento automático
- [ ] Portas, banco e Swagger mantidos
- [ ] CA-022 verificado em ambiente limpo

### T-34 · Verificação de performance — REABERTA
**Depende de:** T-26, T-09, T-43
**Conclusão:**
- [ ] CA-021: os três endpoints < 2s com seed carregado
- [ ] Corrigir documentação: 5.000/dia ≈ 0,058/s de média, sem inventar pico
- [ ] Medir/registrar tempo típico de consumo do Worker
- [ ] Explicar fila como desacoplamento/amortecimento de rajadas
- [ ] Não adicionar broker externo no MVP

### T-35 · `IA_REPORT.md`
**Depende de:** T-33
**Conclusão:**
- [ ] Registrar a revisão de objetivo identificada pelo candidato
- [ ] Registrar a remoção do botão manual e a adoção do Worker/fila local
- [ ] Explicar o que a IA sugeriu e o que foi decidido/ajustado pelo humano
- [ ] Manter ferramentas, prompts, limitações e lições aprendidas

### T-37 · `DECISIONS.md`
**Depende de:** T-32
**Conclusão:**
- [ ] Incluir decisão da automação do gatilho de validação
- [ ] Incluir decisão de manter `POST /validar` sem uso no Angular
- [ ] Referenciar ADR de `JobValidacao`/Worker

### T-38 · `docs/architecture.md` — REABERTA
**Depende de:** T-43
**Conclusão:**
- [ ] Diagrama do MVP mostra Angular de consulta, FastAPI, SQLite, producer, `JobValidacao` e Worker
- [ ] Fluxo principal automático documentado
- [ ] `POST /validar` rotulado como adaptador técnico síncrono
- [ ] Arquitetura futura mostra substituição da fila local por SQS/EventBridge e consumers escaláveis
- [ ] Futuro permanece explicitamente não implementado

### T-39 · `docs/operations.md` — REABERTA
**Depende de:** T-34
**Conclusão:**
- [ ] Métricas HTTP existentes preservadas
- [ ] Adicionar tamanho/idade da fila, jobs processados, falhas e tentativas do Worker
- [ ] Logs do Worker incluem `job_id`, `movimentacao_id`, tentativa e resultado técnico
- [ ] Alertas futuros para backlog, job em erro e ausência de consumo
- [ ] Troubleshooting inclui Worker parado, job em erro e contenção SQLite

### T-40 · Checklist de conformidade — REABERTA
**Depende de:** todas as tarefas da revisão
**Conclusão:**
- [ ] V-01 a V-20 de `plan.md` §13 verificados
- [ ] Nenhuma regressão nas 34 regras
- [ ] Nenhum botão/chamada de validação no Angular
- [ ] Fluxo automático demonstrável de ponta a ponta

---

## Fase 7 — Processamento automático local — NOVA

### T-41 · Persistência de `JobValidacao`
**Depende de:** T-02, T-03
**Entrega:** modelo + repositório da fila local.
**Conclusão:**
- [ ] Modelo com `movimentacao_id`, `status`, `tentativas`, timestamps e `ultimo_erro`
- [ ] Estados `PENDENTE`, `PROCESSANDO`, `CONCLUIDO`, `ERRO`
- [ ] Índice para consumo por `status/criado_em`
- [ ] Idempotência do job automático por movimentação
- [ ] Testes de persistência

### T-42 · Gate e producer
**Depende de:** T-06, T-41
**Entrega:** `processing/approval_gate.py` e `processing/producer.py`.
**Conclusão:**
- [ ] Reutiliza a fonte única `EXIGENCIAS_POR_TIPO`
- [ ] Aprovação `PENDENTE` → não agenda
- [ ] Aprovação `REPROVADA` → bloqueia movimentação, não agenda
- [ ] Todas `APROVADA` → agenda exatamente um job
- [ ] Reexecução é idempotente
- [ ] Nenhuma das 34 regras é duplicada no producer

### T-43 · Worker Python
**Depende de:** T-41, T-42, T-25
**Entrega:** processo executável localmente.
**Conclusão:**
- [ ] Comando explícito para iniciar o Worker
- [ ] Consome job pendente
- [ ] Marca `PROCESSANDO`
- [ ] Chama o mesmo `ValidacaoService` de `POST /validar`
- [ ] Sucesso → job `CONCLUIDO`
- [ ] Falha técnica → rollback do negócio, incremento de tentativa e registro de erro técnico
- [ ] Nenhuma regra copiada para o Worker
- [ ] Worker único no MVP; sem coordenação distribuída

### T-44 · Testes do processamento automático
**Depende de:** T-41, T-42, T-43
**Conclusão:**
- [ ] CA-040 a CA-047 cobertos
- [ ] CN-Q01 a CN-Q07 cobertos
- [ ] Teste prova que aprovação pendente não executa engine
- [ ] Teste prova producer idempotente
- [ ] Teste prova Worker → auditoria → status
- [ ] Teste prova rollback em falha técnica

---

## 2. Matriz de dependências

A matriz abaixo destaca a revisão; dependências históricas T-01…T-40 permanecem válidas onde não foram reabertas.

| Tarefa | Depende de |
|---|---|
| T-41 | T-02, T-03 |
| T-42 | T-06, T-41 |
| T-43 | T-41, T-42, T-25 |
| T-44 | T-41, T-42, T-43 |
| T-09 (revisão) | T-05, T-06, T-42 |
| T-26 (revisão) | T-23, T-24, T-25, T-09, T-43, T-44 |
| T-27 | T-22 |
| T-29 | T-27, T-24 |
| T-30 | T-29 |
| T-32 (revisão) | T-31 |
| T-33 (revisão) | T-26, T-30, T-43 |
| T-34 (revisão) | T-26, T-09, T-43 |
| T-35 (revisão) | T-33 |
| T-37 (revisão) | T-32 |
| T-38 (revisão) | T-43 |
| T-39 (revisão) | T-34 |
| T-40 (revisão) | todas as tarefas da revisão |

---

## 3. Rastreabilidade — critério de aceite → tarefa

| CA | Tarefa |
|---|---|
| CA-001 a CA-005 | T-23 |
| CA-006 a CA-008, CA-015 | T-24 |
| CA-009, CA-011, CA-012, CA-014 | T-25 |
| CA-010 | T-14 |
| CA-013 | T-07 |
| CA-016 | T-28 |
| CA-017 | T-29 |
| CA-018 a CA-020, CA-039 | T-27, T-29, T-30 |
| CA-021 | T-34 |
| CA-022 | T-33 |
| CA-023 | T-20 |
| CA-024 | T-20, T-25, T-43, T-44 |
| CA-025, CA-026, CA-028 | T-19 |
| CA-029 a CA-033 | T-21, T-25 |
| CA-034 | T-13 a T-18 |
| CA-035, CA-036 | T-14 a T-18 |
| CA-037, CA-038 | T-17 |
| CA-040 a CA-043 | T-41, T-42, T-44 |
| CA-044 | T-43, T-44, T-26 |
| CA-045 | T-09, T-44 |
| CA-046 | T-34 |
| CA-047 | T-43, T-44 |

A revisão não altera o catálogo de 34 regras; altera **o gatilho e a orquestração** da validação.
