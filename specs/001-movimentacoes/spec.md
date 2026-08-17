# spec.md — Portal de Mobilidade Organizacional

**Feature:** 001-movimentacoes
**Status:** Revisão arquitetural de 2026-08-16. Especificação para ajuste da implementação existente.
**Escopo:** MVP local (Angular → FastAPI + Worker Python → SQLite).

---

## 0. Restrições congeladas (não reabrir)

Estas afirmações são decisões fechadas para a revisão atual. Qualquer implementação que as contrarie está incorreta sem nova decisão registrada.

| # | Restrição |
|---|---|
| RC-01 | O catálogo possui exatamente **34 regras executáveis**. Nenhuma regra pode ser adicionada, removida ou renumerada sem nova decisão registrada. |
| RC-02 | **`ALTERACAO_ESTRUTURA` é a movimentação de um colaborador entre estruturas organizacionais.** Não é o reparentamento de nós da árvore. |
| RC-03 | **`AE05` é `origem ≠ destino`.** Não existe regra de ciclo organizacional em `ALTERACAO_ESTRUTURA`, em nenhuma forma, sob nenhum código. Ver §9. |
| RC-04 | Ciclo hierárquico é regra real **exclusivamente** em `TG05` (`TROCA_GESTOR`). |
| RC-05 | Aprovação superior baseada em cargo aplica-se **exclusivamente** a `PROMOCAO` (`P06`). Denominação obrigatória: *Política de aprovação de promoção baseada no cargo de destino*. |
| RC-06 | `PX01–PX05` são **políticas organizacionais fictícias e configuráveis**, criadas para demonstrar extensibilidade. Não são regras deste desafio, não são política real de nenhuma organização, não são exigência legal. Não implementar no MVP. |
| RC-07 | Auditoria de validação é **persistida e append-only**. Não há endpoint próprio, nem consulta paginada/filtrada, nem exposição de validações anteriores à última via API. **Exceção pontual (ADR-0010):** o detalhe de uma solicitação `APROVADA` mostra uma linha do tempo client-side (`historico()`), montada só com campos já expostos por `GET /movimentacoes/{id}` (aprovações + `ultimaValidacao`, RC-08), mais **uma** entrada fixa e claramente rotulada como cenário ilustrativo/fora de escopo — não é auditoria real, não lê validações anteriores, não introduz endpoint nem tabela nova. |
| RC-08 | Apenas a **última** validação é exposta, dentro de `GET /movimentacoes/{id}`. |
| RC-09 | `Movimentacao.status = PENDENTE` significa *não concluída*. No fluxo automático, movimentação aguardando aprovação permanece `PENDENTE` e ainda não precisa possuir validação. |
| RC-10 | Nenhuma regra de negócio no Angular. O frontend é **consulta/relatório**: lista, busca, filtra, ordena, detalha e exibe inconsistências; não dispara validação e não decide validade. |
| RC-11 | Fora do MVP: AWS em runtime, Docker obrigatório, Redis, Celery, RabbitMQ, Kafka, microsserviços, autenticação, Keycloak, Elasticsearch, workflow engine, regras configuráveis em banco, DSL de regras, event sourcing, CQRS, Kubernetes, IA no produto. **A fila persistente local em SQLite (`JobValidacao`) e o Worker Python fazem parte do MVP.** |
| RC-12 | Nenhuma meta numérica de testes ou de cobertura percentual é objetivo do projeto. |
| RC-13 | O fluxo normal de produto é **automático**: uma movimentação somente é agendada para validação quando as aprovações exigidas estiverem concluídas e aprovadas. Enquanto houver aprovação `PENDENTE`, não há job de validação. |
| RC-14 | O disparo local usa um producer + tabela `JobValidacao` no SQLite + Worker Python consumidor. A fronteira é deliberadamente substituível por mensageria gerenciada na evolução. |
| RC-15 | `POST /validar` permanece disponível para cumprir o contrato técnico do case, Swagger e testes, reutilizando o mesmo caso de uso de validação. **Não é o gatilho normal do produto** — o fluxo padrão é o automático (RC-13/RC-14). O Angular chama `POST /validar` em exatamente um ponto: o botão "Validar agora" do detalhe (ADR-0010), visível apenas para solicitações `PENDENTE` ou `REPROVADA` (ainda não efetivamente aprovadas), como validação sob demanda que funciona mesmo com o Worker parado/travado. Nenhum outro fluxo (listagem, carregamento normal do detalhe, solicitações `APROVADA`) chama esse endpoint. |

---

## 1. Objetivo

Permitir consultar movimentações organizacionais e demonstrar um fluxo **automatizado** de validação: solicitações são recebidas, passam pelo estado de aprovações e, quando aptas, são colocadas em uma fila local de validação consumida por um Worker Python. O motor retorna **todas** as inconsistências encontradas e mantém trilha de auditoria persistida.

O valor central não é o CRUD nem uma ação manual na interface. É responder, de forma auditável e automática: *esta movimentação pode seguir adiante, e se não, por quê — em todos os pontos em que falha.*

### 1.1 Visão do Produto e Resultado Esperado

O **Portal de Mobilidade Organizacional** é um MVP local de acompanhamento das movimentações internas de colaboradores.

O problema atacado é a dependência de análises manuais e validações operacionais. O MVP demonstra um fluxo automatizado, determinístico, rastreável e tecnicamente sustentável:

1. uma solicitação de movimentação entra no sistema;
2. suas aprovações evoluem fora da interface deste MVP;
3. enquanto houver aprovação pendente, a movimentação permanece `PENDENTE`;
4. se uma aprovação exigida for rejeitada, a movimentação não é enviada para validação automática e permanece bloqueada como `REPROVADA`;
5. quando todas as aprovações exigidas estiverem aprovadas, o producer cria um `JobValidacao`;
6. o Worker consome o job e chama o mesmo caso de uso de validação utilizado por `POST /validar`;
7. a engine coleta todas as inconsistências, grava auditoria e atualiza a movimentação;
8. somente movimentação validada como `APROVADA` está apta a seguir para um processamento posterior, que está fora do MVP.

O frontend **não possui botão de validar**. Ele funciona como relatório operacional e de rastreabilidade sobre o processamento realizado no backend.

O MVP contempla os cinco tipos de movimentação definidos para o domínio:

- transferência entre departamentos;
- promoção;
- troca de gestor;
- mudança de centro de custo;
- alteração de estrutura organizacional.

#### Experiência demonstrável

A banca avaliadora deve conseguir executar localmente o seguinte fluxo:

1. iniciar o backend conforme `README.md`;
2. inicializar o banco com o seed fictício determinístico;
3. iniciar o Worker de validação;
4. iniciar o frontend;
5. observar movimentações `PENDENTE` aguardando aprovações;
6. observar movimentações elegíveis sendo processadas automaticamente pelo Worker;
7. visualizar a listagem;
8. buscar por colaborador;
9. filtrar por status;
10. ordenar e paginar os resultados;
11. abrir o detalhe;
12. visualizar origem/destino, aprovações, última validação e inconsistências;
13. observar resultados `APROVADA` e `REPROVADA` produzidos automaticamente;
14. consultar `POST /validar` pelo Swagger como contrato técnico do case, sem dependência da interface;
15. executar os testes automatizados documentados.

O seed deve disponibilizar cenários suficientes para demonstrar:

- solicitações ainda aguardando aprovação;
- solicitações com aprovação rejeitada;
- solicitações com todas as aprovações concluídas e aptas à fila;
- validações aprovadas;
- validações reprovadas;
- inconsistência única;
- múltiplas inconsistências simultâneas.

#### Composição da solução

O MVP será composto por:

- **Angular**, responsável apenas por consulta, navegação e apresentação dos resultados;
- **FastAPI/Python**, responsável pelos contratos HTTP e casos de uso;
- **motor de validação Python**, responsável pelas 34 regras e resolução determinística;
- **Producer local**, responsável por agendar movimentações aptas;
- **Worker Python**, responsável por consumir `JobValidacao` e executar a validação;
- **SQLite**, responsável pela persistência das entidades, auditoria e fila local;
- **dados fictícios determinísticos**, usados para simular solicitações e estados de aprovação.

O **motor de validação continua sendo o núcleo do produto**. A mudança desta revisão é o **gatilho**: no fluxo normal, a validação deixa de depender de ação humana no Angular e passa a ser iniciada automaticamente no backend.

#### Objetivo de engenharia

Além do fluxo funcional, a entrega deve tornar possível avaliar:

- transformação do problema de negócio em solução técnica clara;
- redução de manualidade por automação real do gatilho de validação;
- separação entre interface de consulta, processamento assíncrono e regras de domínio;
- arquitetura do MVP e caminho de evolução;
- decisões técnicas, alternativas e trade-offs;
- qualidade e testabilidade das regras;
- rastreabilidade das validações;
- operação do Worker e tratamento de falhas;
- estratégia de testes;
- riscos conhecidos;
- uso consciente de IA durante o desenvolvimento.

Esses aspectos devem ser sustentados pelo código e pelos artefatos `README.md`, `DECISIONS.md`, `IA_REPORT.md`, `docs/architecture.md` e `docs/operations.md`.

#### Arquitetura atual e evolução

O MVP executa integralmente em ambiente local. A fila é persistida no próprio SQLite para evitar dependência de broker externo.

A solução deve documentar a evolução para o cenário futuro do case, incluindo:

- aproximadamente 100 mil movimentações por mês;
- integração com múltiplos sistemas;
- indicadores para RH;
- escalabilidade e observabilidade;
- substituição da fila local por mensageria gerenciada;
- execução independente e escalável dos consumers;
- possível utilização de serviços AWS.

A arquitetura futura é documentada e diagramada, mas não implementada no MVP.

#### Critério de sucesso da entrega

O MVP é considerado demonstrável quando um avaliador consegue:

1. subir backend, Worker e frontend;
2. carregar os dados fictícios;
3. compreender que o seed simula solicitações de movimentação e estados de aprovação;
4. observar a validação automática de solicitações aptas sem clicar em “validar”;
5. navegar pela listagem e detalhe;
6. compreender por que uma movimentação está pendente, aprovada ou reprovada;
7. visualizar todas as inconsistências da última validação;
8. consultar o Swagger e exercitar `POST /validar` como contrato técnico;
9. executar os testes;
10. compreender como a fila local/Worker evoluem para mensageria e consumers em cloud.

O objetivo da entrega **não é reproduzir um sistema corporativo completo de RH**. A prioridade é uma solução simples, funcional e verificável que demonstre automação, rastreabilidade e capacidade de evolução.

---

## 2. Requisitos funcionais

### 2.1 Backend e validação

| ID | Requisito | Verificável por |
|---|---|---|
| RF-01 | Listar movimentações com paginação obrigatória | CA-001, CA-002 |
| RF-02 | Filtrar a listagem por `status` | CA-003 |
| RF-03 | Buscar por colaborador: matrícula exata **ou** nome parcial (case-insensitive) | CA-004 |
| RF-04 | Ordenar por campos de whitelist, asc/desc | CA-005 |
| RF-05 | Consultar movimentação por id, com entidades relacionadas resolvidas | CA-006 |
| RF-06 | Expor as aprovações da movimentação no detalhe | CA-007 |
| RF-07 | Expor a **última** validação no detalhe | CA-008 |
| RF-08 | Executar validação retornando **todas** as inconsistências | CA-009, CA-010 |
| RF-09 | Identificar em cada inconsistência: código, mensagem, severidade | CA-011 |
| RF-10 | Persistir em auditoria append-only cada validação concluída com resultado de negócio | CA-012, CA-013 |
| RF-11 | Atualizar `status` e `resultado_ultima_validacao` após validação concluída | CA-014 |
| RF-12 | Retornar 404 para movimentação inexistente em `GET /{id}` e `POST /validar` | CA-015 |

### 2.2 Processamento automático

| ID | Requisito | Verificável por |
|---|---|---|
| RF-18 | Agendar para validação automática uma movimentação quando todas as aprovações exigidas estiverem `APROVADA` | CA-040 |
| RF-19 | Não agendar movimentação com aprovação `PENDENTE`; aprovação `REPROVADA` bloqueia o fluxo e não gera job de validação | CA-041, CA-042 |
| RF-20 | Persistir o agendamento em `JobValidacao` e impedir job automático duplicado para a mesma movimentação | CA-043 |
| RF-21 | Worker local consome jobs pendentes e reutiliza o mesmo caso de uso de validação de `POST /validar` | CA-044 |
| RF-22 | O seed simula solicitações e estados de aprovação e, ao final, usa o producer para agendar os casos aptos | CA-045 |

### 2.3 Frontend

| ID | Requisito | Verificável por |
|---|---|---|
| RF-13 | Listagem com busca, filtro de status, ordenação e paginação | CA-016 |
| RF-14 | Detalhe da movimentação: dados, origem/destino, aprovações e última validação | CA-017 |
| RF-15 | Frontend apresenta o estado produzido pelo backend; o único gatilho de validação em Angular é o botão manual condicional "Validar agora" (PENDENTE/REPROVADA), que chama `POST /validar` sob demanda | CA-018 |
| RF-16 | Exibir inconsistências com código e mensagem | CA-019 |
| RF-17 | Estados de interface: carregando, vazio, erro, sem inconsistências e aguardando processamento/aprovação | CA-020 |

---

---

## 3. Requisitos não funcionais

| ID | Requisito | Como é atendido | Verificável por |
|---|---|---|---|
| RNF-01 | Resposta HTTP < 2s | Paginação + índices + carga única do contexto; processamento automático desacoplado da navegação | CA-021 |
| RNF-02 | Até 5.000 movimentações/dia | ~0,058 movimentação/s na média diária; fila persistente absorve rajadas sem bloquear o frontend | CA-046 |
| RNF-03 | Auditoria de toda validação concluída | Tabelas dedicadas, append-only | CA-012 |
| RNF-04 | Movimentação inválida não segue para processamento posterior | Apenas `APROVADA` fica apta após a engine; `REPROVADA` permanece bloqueada | CA-014, CA-044 |
| RNF-05 | Regras testáveis isoladamente | Funções puras sobre contexto pré-carregado | INV-01 |
| RNF-06 | Execução local reproduzível | Backend, Worker e frontend em comandos explícitos; banco em arquivo; seed idempotente | CA-022 |
| RNF-07 | Determinismo | Mesma entrada + mesmo estado → mesmas inconsistências, na mesma ordem | INV-05, CA-023 |
| RNF-08 | Agendamento idempotente | No máximo um job automático por movimentação no MVP | CA-043 |
| RNF-09 | Falha técnica não produz resultado falso | Rollback da validação; job registra erro/tentativa; nenhuma auditoria parcial | CA-024, CA-047 |

---

---

## 4. Domínio

### 4.1 Entidades

#### Colaborador
Pessoa sujeita à movimentação e, quando aplicável, exercendo o papel de gestor.

| Atributo | Tipo | Nota |
|---|---|---|
| `id` | int PK | |
| `matricula` | str, único, indexado | busca exata |
| `nome` | str, indexado | busca parcial |
| `ativo` | bool | G02 |
| `cargo_id` | FK Cargo | base de P03 |
| `departamento_id` | FK Departamento | |
| `centro_custo_id` | FK CentroCusto | |
| `gestor_id` | FK Colaborador, nullable | árvore hierárquica; base de TG05 |
| `data_admissao` | date | exibição; base futura de PX01 |

**Gestor não é entidade.** É papel exercido por Colaborador via `gestor_id` e via `Departamento.gestor_id` / `CentroCusto.responsavel_id`.

#### Cargo

| Atributo | Tipo | Nota |
|---|---|---|
| `id` | int PK | |
| `codigo` | str, único | |
| `nome` | str | |
| `nivel` | int | ordenável; base de P03 |
| `ativo` | bool | P02 |
| `permite_gestao` | bool | base de TG03 |
| `aprovacao_adicional` | enum `GERENCIA \| DIRETORIA \| null` | nulo = nenhuma aprovação adicional. base de P06. **Somente PROMOCAO.** |

> **Renomeado de `nivel_aprovacao_necessaria`.** Os valores `GESTOR` e `RH` foram removidos: essas aprovações já são obrigatórias por P04/P05 em toda promoção, independentemente deste campo. `aprovacao_adicional` expressa exclusivamente a aprovação *extra* acima de gestor+RH — `null` significa que nenhuma é exigida.

#### Departamento
`id`, `codigo`, `nome`, `ativo`, `gestor_id` (FK Colaborador), `estrutura_id` (FK EstruturaOrganizacional).

#### CentroCusto
`id`, `codigo`, `nome`, `ativo`, `responsavel_id` (FK Colaborador), `estrutura_id` (FK EstruturaOrganizacional).

#### EstruturaOrganizacional
`id`, `codigo`, `nome`, `ativo`, `estrutura_pai_id` (FK auto, nullable), `nivel`.

> A árvore existe para representar o domínio e habilitar validações hierárquicas **futuras**. Nenhuma regra do MVP percorre esta árvore (RC-03).

#### Movimentacao — agregado raiz

| Atributo | Tipo | Nota |
|---|---|---|
| `id` | int PK | |
| `tipo` | enum | G03 |
| `status` | enum `PENDENTE \| APROVADA \| REPROVADA` | RC-09 |
| `colaborador_id` | FK Colaborador, obrigatório | G01, G02 |
| `data_solicitacao` | datetime, indexado | ordenação |
| `departamento_origem_id` | FK, nullable | TRANSFERENCIA |
| `departamento_destino_id` | FK, nullable | TRANSFERENCIA |
| `cargo_origem_id` | FK, nullable | PROMOCAO |
| `cargo_destino_id` | FK, nullable | PROMOCAO |
| `gestor_origem_id` | FK Colaborador, nullable | TROCA_GESTOR |
| `gestor_destino_id` | FK Colaborador, nullable | TROCA_GESTOR |
| `centro_custo_origem_id` | FK, nullable | MUDANCA_CENTRO_CUSTO |
| `centro_custo_destino_id` | FK, nullable | MUDANCA_CENTRO_CUSTO |
| `estrutura_origem_id` | FK, nullable | ALTERACAO_ESTRUTURA |
| `estrutura_destino_id` | FK, nullable | ALTERACAO_ESTRUTURA |
| `resultado_ultima_validacao` | enum, nullable | nulo = nunca validada |
| `data_ultima_validacao` | datetime, nullable | |

#### Aprovacao
`id`, `movimentacao_id` (FK), `tipo` (`GESTOR_ORIGEM \| GESTOR_DESTINO \| RH \| GERENCIA \| DIRETORIA`), `estado` (`PENDENTE \| APROVADA \| REPROVADA`), `aprovador_id` (FK Colaborador, nullable), `data_decisao` (nullable), `justificativa` (nullable).

#### ValidacaoAuditoria
`id`, `movimentacao_id` (FK, indexado), `data_hora`, `resultado`, `total_inconsistencias`, `versao_motor`.

#### InconsistenciaAuditoria
`id`, `validacao_id` (FK), `codigo_regra`, `mensagem`, `severidade`.

#### JobValidacao — infraestrutura local
Modelo persistente de infraestrutura, não regra de domínio. Representa a fila local consumida pelo Worker.

`id`, `movimentacao_id` (FK, único no fluxo automático do MVP), `status` (`PENDENTE | PROCESSANDO | CONCLUIDO | ERRO`), `tentativas`, `criado_em`, `iniciado_em` (nullable), `finalizado_em` (nullable), `ultimo_erro` (nullable).

O job não substitui `Movimentacao.status`: o primeiro representa a execução técnica da validação; o segundo representa o estado de negócio visível no portal.

### 4.2 Entidades rejeitadas

`Gestor` (papel, não entidade) · `Regra` em banco (regra é código — RC-11) · `Usuario`/`Perfil` (sem autenticação) · `HistoricoCargo`/`HistoricoLotacao` (antecipação) · `WorkflowAprovacao`/`Etapa` (antecipação) · `Notificacao` (fora de escopo).

### 4.3 Mapa de campos por tipo

| Tipo | Campos obrigatórios | Campos que devem ser nulos |
|---|---|---|
| TRANSFERENCIA | `departamento_origem_id`, `departamento_destino_id` | todos os demais pares |
| PROMOCAO | `cargo_origem_id`, `cargo_destino_id` | todos os demais pares |
| TROCA_GESTOR | `gestor_origem_id`, `gestor_destino_id` | todos os demais pares |
| MUDANCA_CENTRO_CUSTO | `centro_custo_origem_id`, `centro_custo_destino_id` | todos os demais pares |
| ALTERACAO_ESTRUTURA | `estrutura_origem_id`, `estrutura_destino_id` | todos os demais pares |

> **TROCA_GESTOR exige `gestor_origem_id`.** Colaborador sem gestor atual está **fora do escopo do MVP** — não existe fluxo de troca de gestor para esse caso. `Colaborador.gestor_id` continua nullable como atributo geral (ex.: topo da hierarquia), mas toda movimentação `TROCA_GESTOR` deve referenciar um gestor de origem.

---

## 5. Aprovações

### 5.1 Premissa fundamental

**Toda movimentação possui, desde sua criação, todas as linhas de aprovação exigidas pelo seu tipo.** O estado inicial natural dessas linhas é `PENDENTE`.

Para demonstração, o seed materializa cenários com aprovações `PENDENTE`, `APROVADA` e `REPROVADA`, preservando a existência das linhas obrigatórias e a integridade dos aprovadores.

Linha exigida ausente é erro de integridade/configuração e permanece como cenário negativo de teste das regras; não é o fluxo operacional normal.

### 5.2 Exigências por tipo

| Tipo | Aprovações exigidas |
|---|---|
| TRANSFERENCIA | `GESTOR_ORIGEM`, `GESTOR_DESTINO` |
| PROMOCAO | `GESTOR_ORIGEM`, `RH`, + `cargo_destino.aprovacao_adicional` quando não for `null` |
| TROCA_GESTOR | `GESTOR_ORIGEM`, `GESTOR_DESTINO` |
| MUDANCA_CENTRO_CUSTO | `GESTOR_DESTINO` |
| ALTERACAO_ESTRUTURA | `GESTOR_ORIGEM` |

### 5.3 Integridade do aprovador

Uma aprovação é **íntegra** quando:

1. a linha existe com o tipo exigido;
2. se `estado ∈ {APROVADA, REPROVADA}` → `aprovador_id` preenchido, colaborador existe e está **ativo**;
3. para `GESTOR_ORIGEM` / `GESTOR_DESTINO` → o responsável esperado existe e está ativo.

Falha de integridade emite inconsistência **sob o código da regra de aprovação do tipo** (T06, P04, P05, P06, TG06, CC06, AE06), sem código público adicional.

**Restrição de seed:** `Departamento.gestor_id` e `CentroCusto.responsavel_id` sempre preenchidos.

### 5.3.1 Origem do aprovador esperado, por tipo

| Tipo | `GESTOR_ORIGEM` deriva de | `GESTOR_DESTINO` deriva de | Demais aprovações |
|---|---|---|---|
| TRANSFERENCIA | `departamento_origem.gestor_id` | `departamento_destino.gestor_id` | — |
| PROMOCAO | `colaborador.gestor_id` (gestor atual) | — | `RH` + `cargo_destino.aprovacao_adicional` quando não `null` |
| TROCA_GESTOR | `movimentacao.gestor_origem_id` | `movimentacao.gestor_destino_id` | — |
| MUDANCA_CENTRO_CUSTO | — | `centro_custo_destino.responsavel_id` | — |
| ALTERACAO_ESTRUTURA | `colaborador.gestor_id` | — | — |

### 5.4 Gate de aprovação do fluxo automático

O producer usa as exigências de §5.2 como fonte única; não mantém outro mapa de aprovações.

| Situação | Ação normal do produto |
|---|---|
| Ao menos uma aprovação exigida `PENDENTE` | Mantém `Movimentacao.status = PENDENTE`; **não cria `JobValidacao`**; não há nova auditoria de validação |
| Ao menos uma aprovação exigida `REPROVADA` | `Movimentacao.status = REPROVADA`; **não cria `JobValidacao`**; a reprovação decorre do fluxo de aprovação, não de uma validação executada |
| Todas as aprovações exigidas `APROVADA` | Producer cria `JobValidacao` idempotentemente |
| Linha exigida ausente / dado de aprovação não íntegro | Cenário anômalo. Não deve ser mascarado pelo producer; continua coberto pelas regras de integridade e pelos testes do motor |

### 5.5 Resolução quando a engine é executada

O mecanismo existente de resolução permanece compatível com `POST /validar`. No fluxo automático, o Worker recebe somente movimentações cujo gate normal esteja concluído, portanto o resultado esperado do Worker é `APROVADA` ou `REPROVADA`.

| Situação durante a chamada de validação | Resultado |
|---|---|
| Existem inconsistências | `REPROVADA` |
| Sem inconsistências e alguma aprovação `REPROVADA` | `REPROVADA` |
| Sem inconsistências e alguma aprovação `PENDENTE` | `AGUARDANDO_APROVACAO` |
| Sem inconsistências e todas `APROVADA` | `APROVADA` |

`AGUARDANDO_APROVACAO` permanece no contrato técnico para chamadas diretas de `POST /validar`, mas **não é o gatilho normal do portal nem exige ação no frontend**.

---

## 6. Catálogo de regras — 34 executáveis

### 6.1 Convenções

- **Código** é contrato público. Aparece na API e na auditoria. **Nunca é reciclado.**
- **Pré-condição** define quando a regra **não avalia** (retorna vazio). Evita cascata de inconsistências redundantes.
- Severidade única no MVP: `ERRO`.
- Ordem de execução: gerais → específicas, na ordem do catálogo.

### 6.2 Gerais — G (4)

| Código | Regra | Pré-condição | Falha quando | Mensagem |
|---|---|---|---|---|
| G01 | Colaborador existe | — | `colaborador` é nulo | Colaborador não encontrado |
| G02 | Colaborador está ativo | G01 passou | `colaborador.ativo = false` | Colaborador não está ativo |
| G03 | Tipo de movimentação é válido | — | `tipo` não pertence ao enum | Tipo de movimentação inválido |
| G04 | Sem movimentação conflitante | G01 passou | existe outra movimentação do **mesmo tipo**, mesmo colaborador, `status = PENDENTE`, id diferente | Existe outra movimentação do mesmo tipo em aberto para este colaborador |

> Existência e atividade de departamento, cargo, centro de custo, estrutura e gestor **não pertencem às gerais**. Vivem nas específicas.

### 6.3 Transferência — T (6)

| Código | Regra | Pré-condição | Falha quando | Mensagem |
|---|---|---|---|---|
| T01 | Departamento de origem existe | — | `departamento_origem` nulo | Departamento de origem não encontrado |
| T02 | Departamento de origem ativo | T01 passou | `.ativo = false` | Departamento de origem não está ativo |
| T03 | Departamento de destino existe | — | `departamento_destino` nulo | Departamento de destino não encontrado |
| T04 | Departamento de destino ativo | T03 passou | `.ativo = false` | Departamento de destino não está ativo |
| T05 | Origem ≠ destino | T01 e T03 passaram | ids iguais | Departamento de origem e destino são iguais |
| T06 | Aprovações exigidas registradas e íntegras | — | falta linha exigida ou linha não íntegra (§5.3) | Aprovação {tipo} ausente / aprovador inválido |

### 6.4 Promoção — P (6)

> `P01 — colaborador ativo` **não existe**. Foi removido por duplicar `G02` (decisão PA-01 = B).

| Código | Regra | Pré-condição | Falha quando | Mensagem |
|---|---|---|---|---|
| P01 | Cargo de destino existe | — | `cargo_destino` nulo | Cargo de destino não encontrado |
| P02 | Cargo de destino ativo | P01 passou | `.ativo = false` | Cargo de destino não está ativo |
| P03 | Cargo de destino possui nível superior | P01 passou e `cargo_atual` conhecido | `cargo_destino.nivel <= cargo_atual.nivel` | Cargo de destino não possui nível superior ao cargo atual |
| P04 | Aprovação do gestor registrada e íntegra | — | falta `GESTOR_ORIGEM` ou não íntegra | Aprovação do gestor ausente / aprovador inválido |
| P05 | Aprovação de RH registrada e íntegra | — | falta `RH` ou não íntegra | Aprovação de RH ausente / aprovador inválido |
| P06 | Aprovação superior registrada e íntegra quando aplicável | P01 passou | `cargo_destino.aprovacao_adicional` não é `null` e a linha correspondente falta ou não é íntegra | Aprovação de {nível} ausente / aprovador inválido |

**P06 — denominação obrigatória:** *Política de aprovação de promoção baseada no cargo de destino*. Não usar "mecanismo de aprovação superior". Aplica-se **somente** a PROMOCAO.

**Extensões documentadas — não implementar (RC-06):**

| Código | Extensão | Natureza |
|---|---|---|
| PX01 | Tempo mínimo de empresa | Política organizacional fictícia e configurável |
| PX02 | Tempo mínimo no cargo | Política organizacional fictícia e configurável |
| PX03 | Avaliação de desempenho mínima | Política organizacional fictícia e configurável |
| PX04 | Faixa salarial compatível | Política organizacional fictícia e configurável |
| PX05 | Posição / headcount disponível | Política organizacional fictícia e configurável |

### 6.5 Troca de gestor — TG (6)

| Código | Regra | Pré-condição | Falha quando | Mensagem |
|---|---|---|---|---|
| TG01 | Novo gestor existe | — | `gestor_destino` nulo | Novo gestor não encontrado |
| TG02 | Novo gestor está ativo | TG01 passou | `.ativo = false` | Novo gestor não está ativo |
| TG03 | Novo gestor possui função compatível | TG01 passou | `gestor_destino.cargo.permite_gestao = false` ou cargo nulo | Novo gestor não possui cargo com função de gestão |
| TG04 | Colaborador ≠ seu próprio gestor | G01 e TG01 passaram | `gestor_destino.id == colaborador.id` | Colaborador não pode ser seu próprio gestor |
| TG05 | Alteração não cria ciclo hierárquico | G01 e TG01 passaram | percorrendo `gestor_id` a partir de `gestor_destino`, alcança-se `colaborador.id` | A alteração criaria um ciclo hierárquico |
| TG06 | Aprovações exigidas registradas e íntegras | — | falta linha exigida ou não íntegra | Aprovação {tipo} ausente / aprovador inválido |

**TG05 — algoritmo obrigatório:**

```
visitados = conjunto vazio
atual = gestor_destino
profundidade = 0
enquanto atual não é nulo e profundidade < LIMITE_PROFUNDIDADE:
    se atual.id == colaborador.id: → CICLO
    se atual.id em visitados:      → interromper (ciclo pré-existente nos dados)
    visitados.adiciona(atual.id)
    atual = atual.gestor
    profundidade += 1
```

O conjunto de visitados e o limite de profundidade protegem contra ciclo já presente nos dados. Sem eles, laço infinito.

### 6.6 Mudança de centro de custo — CC (6)

| Código | Regra | Pré-condição | Falha quando | Mensagem |
|---|---|---|---|---|
| CC01 | CC de origem existe | — | nulo | Centro de custo de origem não encontrado |
| CC02 | CC de origem ativo | CC01 passou | `.ativo = false` | Centro de custo de origem não está ativo |
| CC03 | CC de destino existe | — | nulo | Centro de custo de destino não encontrado |
| CC04 | CC de destino ativo | CC03 passou | `.ativo = false` | Centro de custo de destino não está ativo |
| CC05 | Origem ≠ destino | CC01 e CC03 passaram | ids iguais | Centro de custo de origem e destino são iguais |
| CC06 | Aprovação do responsável pelo destino registrada e íntegra | — | falta `GESTOR_DESTINO` ou não íntegra | Aprovação do responsável pelo centro de custo ausente / inválida |

### 6.7 Alteração de estrutura — AE (6)

> **RC-02 / RC-03.** `ALTERACAO_ESTRUTURA` move um **colaborador** entre estruturas. Não altera a árvore. Mover um colaborador entre nós **não pode** criar ciclo. Por isso `AE05` é `origem ≠ destino`.

| Código | Regra | Pré-condição | Falha quando | Mensagem |
|---|---|---|---|---|
| AE01 | Estrutura de origem existe | — | nulo | Estrutura de origem não encontrada |
| AE02 | Estrutura de origem ativa | AE01 passou | `.ativo = false` | Estrutura de origem não está ativa |
| AE03 | Estrutura de destino existe | — | nulo | Estrutura de destino não encontrada |
| AE04 | Estrutura de destino ativa | AE03 passou | `.ativo = false` | Estrutura de destino não está ativa |
| AE05 | **Origem ≠ destino** | AE01 e AE03 passaram | ids iguais | Estrutura de origem e destino são iguais |
| AE06 | Aprovações exigidas registradas e íntegras | — | falta `GESTOR_ORIGEM` ou não íntegra | Aprovação do gestor ausente / aprovador inválido |

### 6.8 Totalização

| Família | Regras |
|---|---|
| Gerais | 4 |
| Transferência | 6 |
| Promoção | 6 |
| Troca de gestor | 6 |
| Centro de custo | 6 |
| Alteração de estrutura | 6 |
| **Total** | **34** |

---

## 7. Motor de validação e processamento automático

### 7.1 Invariantes

| ID | Invariante | Verificável por |
|---|---|---|
| INV-01 | Nenhuma regra executa I/O. Todo dado vem do `ValidationContext` pré-carregado. | Teste de import |
| INV-02 | O motor não para na primeira inconsistência. Executa todas as regras aplicáveis. | CA-009 |
| INV-03 | Regra cuja pré-condição falhou não avalia e não emite inconsistência. | CA-010 |
| INV-04 | Falha inesperada em uma regra não é resultado de negócio. Propaga, faz rollback, não persiste auditoria e não altera `Movimentacao`; `POST /validar` responde 500 `ERRO_INTERNO`. | CA-024 |
| INV-05 | Ordem das inconsistências é determinística: gerais → específicas, na ordem do catálogo. | CA-023 |
| INV-06 | Toda inconsistência carrega código pertencente ao catálogo de 34. | CA-011 |
| INV-07 | Toda validação concluída com resultado de negócio grava exatamente um `ValidacaoAuditoria`. Execuções interrompidas por erro técnico não produzem auditoria de validação. | CA-012, CA-024 |
| INV-08 | Registros de auditoria nunca são atualizados ou removidos. | CA-013 |
| INV-09 | No fluxo automático, aprovação pendente não executa a engine e não cria auditoria de validação. | CA-041 |
| INV-10 | O producer não cria job automático duplicado para a mesma movimentação. | CA-043 |
| INV-11 | Worker e `POST /validar` reutilizam o mesmo caso de uso; não existem duas implementações das 34 regras. | CA-044 |

### 7.2 Fluxo normal automatizado

```text
Seed / futura integração
        │
        ▼
Movimentação + aprovações
        │
        ▼
Gate de aprovação
   ├── PENDENTE   → Movimentacao=PENDENTE → sem job
   ├── REPROVADA  → Movimentacao=REPROVADA → sem job
   └── todas APROVADA
                │
                ▼
          Producer local
                │
                ▼
       JobValidacao=PENDENTE
                │
                ▼
          Worker Python
                │
                ▼
       ValidacaoService
                │
                ▼
       ValidationEngine
        │             │
 inconsistências   nenhuma
        │             │
        ▼             ▼
   REPROVADA       APROVADA
        └──────┬──────┘
               ▼
     Auditoria append-only
               ▼
   Atualiza Movimentacao
```

Nenhuma ação do Angular participa desse fluxo.

**Movimentações inválidas não seguem para processamento posterior.** O MVP termina na decisão e rastreabilidade; a efetivação da movimentação em sistemas corporativos fica fora de escopo.

### 7.3 `POST /validar` — adaptador síncrono técnico

O endpoint pedido pelo case é preservado para Swagger, testes e demonstração técnica:

```text
POST /validar
      ▼
ValidacaoService
      ▼
ValidationEngine
      ▼
Auditoria + atualização de status
      ▼
Resposta HTTP
```

Ele usa exatamente o mesmo caso de uso chamado pelo Worker — por isso funciona independentemente da fila `JobValidacao`/Worker estarem saudáveis (timeout, travamento ou queda do Worker não o afetam). O Angular chama esse endpoint em um único ponto: o botão "Validar agora" do detalhe, visível apenas para solicitações `PENDENTE` ou `REPROVADA` (RC-15, ADR-0010). Nenhum outro fluxo do Angular o chama.

Por compatibilidade com o contrato existente, uma chamada direta sobre movimentação ainda aguardando aprovação pode retornar `AGUARDANDO_APROVACAO`. Isso não altera o fluxo normal: o producer não agenda esse caso automaticamente.

### 7.4 Resultado e estado

| Resultado da validação | Significado | `Movimentacao.status` |
|---|---|---|
| `REPROVADA` | Uma ou mais inconsistências impedem o avanço | `REPROVADA` |
| `AGUARDANDO_APROVACAO` | Resultado possível apenas na chamada direta quando o fluxo de aprovação ainda está incompleto | `PENDENTE` |
| `APROVADA` | Todas as regras passaram e as aprovações necessárias estão aprovadas | `APROVADA` |

No fluxo normal, `PENDENTE` com `resultado_ultima_validacao = null` representa uma solicitação que ainda não chegou à etapa automática de validação.

### 7.5 Falhas técnicas do Worker

Exceção não tratada durante a validação:

- não é convertida em inconsistência;
- não altera `Movimentacao`;
- não grava auditoria parcial;
- incrementa `JobValidacao.tentativas`;
- registra `ultimo_erro` de forma técnica, sem dados sensíveis;
- o job pode ser reprocessado conforme política simples do MVP; após esgotar tentativas, fica `ERRO`.

O detalhe de retry pertence à infraestrutura do Worker e não altera as 34 regras.

---

## 8. Contratos de API

### 8.1 `GET /movimentacoes`

**Query:** `page` (int ≥1, default 1) · `pageSize` (int 1–100, default 20) · `status` (enum, opcional) · `busca` (str, opcional) · `ordenarPor` (whitelist: `dataSolicitacao`, `tipo`, `status`, `colaboradorNome`) · `direcao` (`asc|desc`).

**200:**
```json
{
  "items": [
    {
      "id": 1001,
      "tipo": "PROMOCAO",
      "status": "PENDENTE",
      "colaborador": { "id": 12, "matricula": "M0012", "nome": "..." },
      "dataSolicitacao": "2026-08-01T10:00:00Z",
      "resultadoUltimaValidacao": null
    }
  ],
  "page": 1,
  "pageSize": 20,
  "total": 137,
  "totalPages": 7
}
```

No fluxo automático, `resultadoUltimaValidacao = null` é esperado para movimentação ainda aguardando aprovação.

### 8.2 `GET /movimentacoes/{id}`

**200:**
```json
{
  "id": 1001,
  "tipo": "PROMOCAO",
  "status": "PENDENTE",
  "dataSolicitacao": "2026-08-01T10:00:00Z",
  "colaborador": { "id": 12, "matricula": "M0012", "nome": "...", "ativo": true },
  "cargoAtual": { "id": 3, "nome": "Analista Pleno", "nivel": 3 },
  "cargoDestino": { "id": 4, "nome": "Analista Sênior", "nivel": 4 },
  "aprovacoes": [
    { "tipo": "GESTOR_ORIGEM", "estado": "APROVADA",
      "aprovador": { "id": 7, "nome": "..." }, "dataDecisao": "2026-08-02T09:00:00Z" },
    { "tipo": "RH", "estado": "PENDENTE", "aprovador": null, "dataDecisao": null }
  ],
  "ultimaValidacao": null
}
```

Quando a validação automática já ocorreu, `ultimaValidacao` contém resultado, data e todas as inconsistências. Apenas a **última** validação é exposta (RC-08); o histórico permanece no banco.

**404:** movimentação inexistente.

### 8.3 `POST /validar`

Mantido como **adaptador síncrono técnico** do caso de uso de validação. Usado pelo Angular apenas pelo botão manual condicional "Validar agora" do detalhe (RC-15, ADR-0010).

**Request:** `{ "movimentacaoId": 1001 }`

**200:**
```json
{
  "movimentacaoId": 1001,
  "status": "REPROVADA",
  "validadoEm": "2026-08-16T11:03:22Z",
  "inconsistencias": [
    {
      "codigo": "P03",
      "mensagem": "Cargo de destino não possui nível superior ao cargo atual",
      "severidade": "ERRO"
    }
  ]
}
```

`inconsistencias` é `[]` quando não existem erros. Uma chamada direta ainda pode retornar `AGUARDANDO_APROVACAO`; o fluxo automático, porém, não agenda movimentações pendentes.

**404:** movimentação inexistente. **422:** payload inválido. **500:** falha técnica sem resultado de negócio.

### 8.4 Contrato de erro

```json
{
  "erro": {
    "codigo": "MOVIMENTACAO_NAO_ENCONTRADA",
    "mensagem": "Movimentação 9999 não encontrada"
  }
}
```

| HTTP | Código |
|---|---|
| 400 | `PARAMETRO_INVALIDO` |
| 404 | `MOVIMENTACAO_NAO_ENCONTRADA` |
| 422 | `PAYLOAD_INVALIDO` |
| 500 | `ERRO_INTERNO` |

---

---

## 9. Guarda anti-regressão de AE05

Este bloco existe porque `AE05` já foi especificado como regra de ciclo em versões anteriores da análise. A decisão foi revertida e **não pode ser reintroduzida por inércia**.

### 9.1 Afirmações normativas

1. `AE05` é `origem ≠ destino`. Ponto final.
2. Não existe, no MVP, nenhuma regra de ciclo organizacional em `ALTERACAO_ESTRUTURA`, sob qualquer código.
3. `EstruturaOrganizacional.estrutura_pai_id` **não é lido por nenhuma regra do MVP**.
4. `AEX02` (validação hierárquica sobre a árvore) é extensão futura, documentada e **não implementada**.
5. Ciclo é regra real apenas em `TG05`.

### 9.2 Critérios de aceite dedicados

| ID | Critério |
|---|---|
| CA-025 | Movimentação `ALTERACAO_ESTRUTURA` com `estrutura_origem_id == estrutura_destino_id` produz inconsistência `AE05` com a mensagem de origem e destino iguais, **e nenhuma menção a ciclo**. |
| CA-026 | Movimentação `ALTERACAO_ESTRUTURA` cuja estrutura de destino é ancestral ou descendente da estrutura de origem, ambas ativas e distintas, valida **sem nenhuma inconsistência de estrutura**. Este é o cenário que reprovaria se a regra de ciclo fosse reintroduzida. |
| CA-028 | O conjunto de códigos emitíveis por `ALTERACAO_ESTRUTURA` é exatamente `{G01, G02, G03, G04, AE01, AE02, AE03, AE04, AE05, AE06}`. |

CA-026 é o teste comportamental que efetivamente impede a reintrodução: falha se alguém adicionar verificação de ciclo, independentemente de como a implementação for escrita. A afirmação 9.1.3 (não ler `estrutura_pai_id`) permanece como princípio de design e é conferida por **revisão de código**, não por um teste automatizado dedicado — um teste que inspeciona estaticamente o texto do módulo testa implementação, não comportamento, e foi removido do catálogo de testes obrigatórios por esse motivo.

---

## 10. Critérios de aceite

### 10.1 Listagem e consulta

| ID | Critério |
|---|---|
| CA-001 | `GET /movimentacoes` sem parâmetros retorna a primeira página com paginação correta. |
| CA-002 | `pageSize=500` é truncado para 100. |
| CA-003 | `status=REPROVADA` retorna apenas movimentações nesse status. |
| CA-004 | Busca por matrícula exata e nome parcial case-insensitive funciona. |
| CA-005 | Ordenação por whitelist funciona; campo inválido retorna 400. |
| CA-006 | `GET /movimentacoes/{id}` resolve as entidades relacionadas conforme o tipo. |
| CA-007 | O detalhe lista todas as aprovações com tipo, estado e aprovador. |
| CA-008 | O detalhe traz `ultimaValidacao` quando existente e `null` quando ainda não houve validação. |
| CA-015 | `GET /movimentacoes/{id}` e `POST /validar` com id inexistente retornam 404. |

### 10.2 Validação

| ID | Critério |
|---|---|
| CA-009 | Movimentação com múltiplos defeitos independentes retorna **todas** as inconsistências. |
| CA-010 | Destino inexistente em transferência emite `T03` e suprime regras dependentes. |
| CA-011 | Toda inconsistência traz `codigo`, `mensagem` e `severidade`; código pertence ao catálogo. |
| CA-023 | Duas execuções sobre o mesmo estado produzem inconsistências idênticas e na mesma ordem. |
| CA-024 | Exceção forçada em regra produz rollback, sem auditoria e sem alteração da movimentação; chamada HTTP direta responde 500. |
| CA-029 | Movimentação válida com aprovações aprovadas resulta `APROVADA`. |
| CA-030 | Chamada **direta** de `POST /validar` em movimentação válida com aprovação `PENDENTE` pode retornar `AGUARDANDO_APROVACAO`; o producer automático não cria job para esse caso. |
| CA-031 | Chamada direta com aprovação `REPROVADA` retorna `REPROVADA`; no fluxo automático, o gate bloqueia sem criar job. |
| CA-032 | Linha de aprovação exigida ausente continua coberta pela regra de aprovação correspondente. |
| CA-033 | Aprovação concluída com aprovador nulo/inativo produz inconsistência de integridade sob o código público da regra. |

### 10.3 Auditoria

| ID | Critério |
|---|---|
| CA-012 | Cada validação concluída cria exatamente um `ValidacaoAuditoria` e N inconsistências correspondentes; erro técnico não cria auditoria. |
| CA-013 | Revalidar por chamada direta cria novo registro; históricos anteriores não são alterados. |
| CA-014 | Após validação concluída, `status` e `resultado_ultima_validacao` refletem o resultado. |

### 10.4 Regras por tipo

| ID | Critério |
|---|---|
| CA-034 | Cada uma das 34 regras possui cenário que dispara e cenário que suprime. |
| CA-035 | Cada tipo possui cenários de entidade inexistente, inativa e regra específica. |
| CA-036 | Cada tipo possui cenário de múltiplas inconsistências. |
| CA-037 | `TG05` reprova ciclo direto e indireto. |
| CA-038 | `TG05` não entra em laço infinito com ciclo pré-existente. |
| CA-025, CA-026, CA-028 | Guarda anti-regressão de AE05 (§9.2). |

### 10.5 Frontend

| ID | Critério |
|---|---|
| CA-016 | Listagem aplica busca, filtro, ordenação e paginação via API. |
| CA-017 | Detalhe exibe dados, origem/destino, aprovações e última validação. |
| CA-018 | **O único botão/ação de validar no frontend é "Validar agora" no detalhe, visível apenas quando `status` é `PENDENTE` ou `REPROVADA`; some quando `APROVADA`. Nenhum outro service/componente Angular chama `POST /validar` (ADR-0010).** |
| CA-019 | Inconsistências são exibidas com código e mensagem exatamente como retornadas. |
| CA-020 | Estados carregando, vazio, erro, sem inconsistências e aguardando aprovação/processamento são distinguíveis. |
| CA-039 | Nenhum arquivo do frontend contém lógica de decisão de validade. |

### 10.6 Processamento automático

| ID | Critério |
|---|---|
| CA-040 | Com todas as aprovações exigidas `APROVADA`, o producer cria `JobValidacao=PENDENTE`. |
| CA-041 | Com qualquer aprovação exigida `PENDENTE`, não existe job automático e a movimentação permanece `PENDENTE` sem nova auditoria. |
| CA-042 | Com qualquer aprovação exigida `REPROVADA`, não existe job automático e a movimentação fica bloqueada como `REPROVADA`. |
| CA-043 | Reexecutar o producer não cria job automático duplicado para a mesma movimentação. |
| CA-044 | Worker consome job, chama o mesmo `ValidacaoService`, grava auditoria e conclui a movimentação como `APROVADA` ou `REPROVADA`. |
| CA-045 | Após o seed, existem cenários pendentes sem job e cenários aprovados com job pronto para consumo. |
| CA-047 | Falha técnica no Worker não deixa auditoria/status parcial e registra a tentativa no job. |

### 10.7 Não funcionais

| ID | Critério |
|---|---|
| CA-021 | Os três endpoints permanecem abaixo de 2s com o seed carregado. |
| CA-022 | Projeto sobe localmente com comandos documentados para backend, seed, Worker e frontend. |
| CA-046 | O desenho documenta 5.000 movimentações/dia como volume suportado e explica a fila como amortecimento de rajadas, sem alegar pico não fundamentado. |

---

---

## 11. Cenários de teste obrigatórios

### 11.1 Positivos da engine

| ID | Cenário | Esperado |
|---|---|---|
| CN-P01 | TRANSFERENCIA íntegra, aprovações todas `APROVADA` | `APROVADA`, sem inconsistências |
| CN-P02 | PROMOCAO com cargo de nível superior, aprovações todas `APROVADA` | `APROVADA` |
| CN-P03 | TROCA_GESTOR com gestor válido fora da cadeia hierárquica | `APROVADA` |
| CN-P04 | MUDANCA_CENTRO_CUSTO íntegra | `APROVADA` |
| CN-P05 | ALTERACAO_ESTRUTURA entre estruturas distintas e ativas | `APROVADA` |
| CN-P06 | Chamada direta em movimentação íntegra com uma aprovação `PENDENTE` | `AGUARDANDO_APROVACAO`, `status=PENDENTE` |

### 11.2 Negativos por tipo

| ID | Cenário | Códigos esperados |
|---|---|---|
| CN-N01 | Colaborador inativo | `G02` |
| CN-N02 | Segunda TRANSFERENCIA em aberto para o mesmo colaborador | `G04` |
| CN-N03 | Departamento de destino inexistente | `T03` apenas |
| CN-N04 | Departamento de destino inativo | `T04` |
| CN-N05 | Transferência com origem igual ao destino | `T05` |
| CN-N06 | Cargo de destino inativo | `P02` |
| CN-N07 | Promoção para cargo de nível igual | `P03` |
| CN-N08 | Promoção sem aprovação de RH registrada | `P05` |
| CN-N09 | Promoção com `aprovacao_adicional=DIRETORIA` e linha ausente | `P06` |
| CN-N10 | Novo gestor com cargo sem `permite_gestao` | `TG03` |
| CN-N11 | Colaborador como seu próprio gestor | `TG04` |
| CN-N12 | Ciclo hierárquico direto | `TG05` |
| CN-N13 | Ciclo hierárquico indireto | `TG05` |
| CN-N14 | CC de destino inativo | `CC04` |
| CN-N15 | CC origem igual destino | `CC05` |
| CN-N16 | Estrutura de destino inativa | `AE04` |
| CN-N17 | Estrutura origem igual destino | `AE05` |
| CN-N18 | Aprovação `APROVADA` com aprovador inativo | código da regra de aprovação do tipo |

### 11.3 Múltiplas inconsistências

| ID | Cenário | Esperado |
|---|---|---|
| CN-M01 | Colaborador inativo + departamento destino inexistente + aprovações ausentes | `G02`, `T03`, `T06` |
| CN-M02 | Promoção: destino inativo + nível não superior + RH ausente | `P02`, `P03`, `P05` |
| CN-M03 | Troca de gestor: gestor inativo + sem gestão + aprovações ausentes | `TG02`, `TG03`, `TG06` |
| CN-M04 | Colaborador inexistente + destino inexistente + aprovações ausentes | Sem exceção; `G01` e regras aplicáveis conforme pré-condições |

### 11.4 Processamento automático

| ID | Cenário | Esperado |
|---|---|---|
| CN-Q01 | Todas as aprovações exigidas aprovadas | Um único `JobValidacao=PENDENTE` |
| CN-Q02 | Uma aprovação pendente | Nenhum job; movimentação `PENDENTE`; `ultimaValidacao` pode permanecer `null` |
| CN-Q03 | Uma aprovação rejeitada | Nenhum job; movimentação bloqueada `REPROVADA` |
| CN-Q04 | Worker consome job de movimentação válida | Job `CONCLUIDO`; movimentação `APROVADA`; auditoria criada |
| CN-Q05 | Worker consome job de movimentação com múltiplas inconsistências | Job `CONCLUIDO`; movimentação `REPROVADA`; todas as inconsistências auditadas |
| CN-Q06 | Producer executado duas vezes | Nenhum job duplicado |
| CN-Q07 | Exceção técnica durante consumo | Nenhum estado/auditoria parcial; tentativa/erro registrados no job |

### 11.5 Anti-regressão

| ID | Cenário | Esperado |
|---|---|---|
| CN-A01 | ALTERACAO_ESTRUTURA com destino ancestral, ambas ativas e distintas | Sem inconsistência de estrutura |
| CN-A02 | ALTERACAO_ESTRUTURA com destino descendente, ambas ativas e distintas | Sem inconsistência de estrutura |
| CN-A04 | Códigos emitíveis por ALTERACAO_ESTRUTURA | Exatamente os 10 de CA-028 |

---

---

## 12. Seed

O seed representa **solicitações fictícias recebidas de sistemas/processos anteriores**. Ele não representa um usuário clicando em “validar”.

Requisitos:

1. Criar movimentações dos cinco tipos: transferência, promoção, troca de gestor, mudança de centro de custo e alteração de estrutura.
2. Toda movimentação possui todas as linhas de aprovação exigidas pelo tipo, exceto nos cenários negativos isolados de teste que não pertencem ao dataset normal de demonstração.
3. Distribuir aprovações entre `PENDENTE`, `APROVADA` e `REPROVADA`.
4. Ao final da carga, invocar o **producer local** para:
   - não agendar movimentações ainda pendentes;
   - bloquear movimentações com aprovação rejeitada;
   - criar `JobValidacao` para movimentações com todas as aprovações concluídas e aprovadas.
5. Incluir casos que, quando consumidos pelo Worker, terminem `APROVADA` e `REPROVADA`.
6. Incluir casos com inconsistência única e múltiplas inconsistências.
7. `Departamento.gestor_id` e `CentroCusto.responsavel_id` sempre preenchidos.
8. Manter os cenários estruturais/hierárquicos necessários a CN-A01/CN-A02, CN-N13 e CN-N09.
9. Volume ≥ 100 movimentações para exercitar paginação.
10. Seed e agendamento devem ser idempotentes: reexecutar não duplica movimentações nem jobs.
11. Nenhum dado real de pessoa ou organização.

Fluxo de demonstração:

```text
python -m app.seed.seed
        │
        ├── cria solicitações + aprovações
        └── producer agenda apenas as aptas

python -m app.processing.worker
        │
        └── consome JobValidacao e atualiza/audita resultados
```

---

---

## 13. Fora de escopo

Endpoint público de criação de movimentação · tela/endpoint para aprovar ou reprovar · endpoint de histórico de auditoria (consulta real de validações passadas) · autenticação e ator · efetivação real da movimentação em sistemas corporativos após aprovação · broker externo no MVP (SQS, RabbitMQ, Kafka etc.) · cache distribuído · severidade `AVISO` · E2E · teste de carga · versionamento temporal de entidades · implementação de `PX01–PX05` · demais itens de RC-11.

O `POST /validar` existe por exigência técnica do case e, adicionalmente, é o alvo do botão manual condicional "Validar agora" do detalhe (RC-15, ADR-0010) — não é chamado em nenhum outro fluxo. A linha do tempo "Histórico da solicitação" exibida para `APROVADA` (RC-07) é ilustrativa/client-side, não uma tela de auditoria real; sua última entrada é explicitamente marcada como cenário fora de escopo e não representa efetivação real da movimentação.

---

---

## 14. Riscos residuais

| # | Risco | Mitigação |
|---|---|---|
| R1 | Reintrodução de ciclo em `AE05` | Guarda anti-regressão §9 |
| R2 | Regra passa a consultar banco | Teste de imports de `validation/` |
| R3 | Frontend dispara validação fora do botão manual condicional (ex.: na listagem, no carregamento normal do detalhe, ou com `APROVADA`) | CA-018 + teste de service/componente |
| R4 | `PX01–PX05` apresentadas como regras reais | RC-06 + revisão documental |
| R5 | Laço infinito em `TG05` | Visitados + limite de profundidade |
| R6 | Job duplicado produz validação automática duplicada | Idempotência do producer + CA-043 |
| R7 | Falha do Worker deixa estado parcial | Transação/rollback + CA-047 |
| R8 | SQLite sofre contenção de escrita em evolução multi-instância | Worker único no MVP; migrar persistência/fila na evolução |
| R9 | Fila local passa a ser confundida com arquitetura final | `docs/architecture.md` deve explicitar a substituição por SQS/eventos na evolução |
| R10 | Deriva entre catálogo, código e testes | CA-034 + verificações de conformidade |
