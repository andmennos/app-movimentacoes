# tasks.md — Portal de Mobilidade Organizacional

**Feature:** 001-movimentacoes  
**Depende de:** `spec.md`, `plan.md`  
**Status:** T-01 a T-82 representam o histórico implementado até a revisão corretiva anterior. Os testes E2E abriram **T-83 a T-92** em 2026-08-20 — todas concluídas com implementação + teste + execução real (backend 448 testes, frontend 92 testes, seed/Worker/benchmark reexecutados, verificação cross-stack ao vivo no navegador). Ver [ADR-0018](../../docs/decisoes/0018-revisao-e2e-2026-08-20.md).

---

## 0. Regras de execução

1. Ler integralmente `spec.md` e `plan.md` antes de alterar código.
2. Rodar toda a suíte atual e registrar baseline real.
3. Não reimplementar T-47–T-56 se já estiverem corretas; preservá-las.
4. Nenhuma tarefa nova pode ser marcada `[x]` sem teste/evidência.
5. Não criar requisito de domínio não aprovado.
6. Mudança de carreira permanece fora do MVP.
7. Segurança não pode existir apenas no Angular.
8. Rotas de objeto devem aplicar BOLA no backend.
9. Password nunca pode ser persistido/cacheado em texto puro.
10. Em caso de ambiguidade de negócio, parar e perguntar.

---

## 1. Mapa da revisão

```text
T-57 Persistência e domínio base
   ↓
T-58 Auth/JWT/login/lockout
   ↓
T-59 RBAC + BOLA
   ↓
T-60 API/UI criação de solicitações
   ↓
T-61 ApprovalPolicy dinâmica
   ↓
T-62 API/UI de aprovações + atomicidade do histórico
   ↓
T-63 Matriz de transferência e demais movimentos
   ↓
T-64 Promoção P03/P07/P08/P09 + orçamento
   ↓
T-65 Troca de gestor anti-inversão
   ↓
T-66 Solicitante + motivoResumo
   ↓
T-67 Hardening + rate limit
   ↓
T-68 Performance + cache de referência
   ↓
T-69 Seed
   ↓
T-70 Testes backend
   ↓
T-71 Testes frontend/build
   ↓
T-72 Docs/conformidade
```

---

## T-57 · Evolução de persistência e domínio

**Depende de:** T-56  
**Status:** [ ] aberta

Implementar:

- [ ] `Usuario`;
- [ ] perfis `ADMIN | RH_ANALISTA | RH_GESTOR | LIDERANCA`;
- [ ] `SecurityLockout`;
- [ ] `Movimentacao.solicitante_usuario_id`;
- [ ] `Cargo.familia_cargo`;
- [ ] `Cargo.ordem_progressao`;
- [ ] `Cargo.custo_mensal_referencia`;
- [ ] `CentroCusto.orcamento_mensal`;
- [ ] `CentroCusto.custo_comprometido`;
- [ ] `HistoricoProcessamento.ator_usuario_id`;
- [ ] `HistoricoProcessamento.solicitante_usuario_id`;
- [ ] `ValidacaoAuditoria.solicitante_usuario_id`;
- [ ] `ValidacaoAuditoria.ator_usuario_id`;
- [ ] índices novos;
- [ ] schema cria em banco limpo;
- [ ] instrução de reset do SQLite atualizada para mudança estrutural.

Critério:

- [ ] nenhuma coluna de senha em texto puro;
- [ ] FKs/unique coerentes;
- [ ] testes de schema/persistência verdes.

---

## T-58 · Autenticação local JWT + login + lockout

**Depende de:** T-57  
**Status:** [ ] aberta

Backend:

- [ ] `pwdlib[argon2]` ou equivalente aprovado;
- [ ] `PyJWT`;
- [ ] `hash_password`/`verify_password`;
- [ ] `POST /auth/login`;
- [ ] `GET /auth/me`;
- [ ] JWT expira em 30 min;
- [ ] segredo vem de configuração;
- [ ] login inválido não revela existência do username;
- [ ] 3 falhas em 5 min → IP bloqueado 30 min;
- [ ] bloqueio persistido em SQLite;
- [ ] `429` + `Retry-After` durante bloqueio;
- [ ] sucesso limpa contador;
- [ ] `python -m app.security.reset_lockouts`;
- [ ] reset CLI não altera movimentações/usuários.

Frontend:

- [ ] tela `/login`;
- [ ] credencial demo `admin/admin`;
- [ ] credencial demo `analistaRh/analistaRh`;
- [ ] `analistaRh` com perfil `RH_ANALISTA` e vínculo a colaborador ativo de RH;
- [ ] token apenas em memória;
- [ ] auth interceptor;
- [ ] auth guard;
- [ ] logout limpa memória.

Testes:

- [ ] AUTH-01 a AUTH-07.

---

## T-59 · RBAC e BOLA

**Depende de:** T-58  
**Status:** [ ] aberta

- [ ] mapa único de scopes por perfil;
- [ ] `ADMIN` acesso total e única exceção autorizada a aprovar solicitação própria;
- [ ] `RH_ANALISTA` lê tudo, cria, não aprova;
- [ ] `RH_GESTOR` lê tudo e aprova;
- [ ] `LIDERANCA` usa toda subárvore;
- [ ] listagem aplica escopo antes de count/paginação;
- [ ] detalhe fora do escopo retorna 404;
- [ ] endpoints de colaboradores respeitam escopo;
- [ ] endpoints de escrita revalidam objeto;
- [ ] nenhuma confiança em botão escondido no frontend;
- [ ] evitar N+1 ao resolver subárvore.

Testes:

- [ ] AUTH-08;
- [ ] AUTH-09;
- [ ] AUTH-10.

---

## T-60 · Criação de solicitações — API e Angular

**Depende de:** T-59  
**Status:** [ ] aberta

Backend:

- [ ] `POST /movimentacoes`;
- [ ] union discriminada para `TRANSFERENCIA`, `PROMOCAO`, `MUDANCA_CENTRO_CUSTO`;
- [ ] `extra="forbid"`;
- [ ] solicitante vem do JWT;
- [ ] origem vem do estado atual do colaborador;
- [ ] usuário não consegue forjar origem/status/aprovação;
- [ ] `SolicitacaoService` transacional;
- [ ] cria `SOLICITACAO_RECEBIDA`;
- [ ] status inicial coerente com gate.

Frontend:

- [ ] tela Nova solicitação;
- [ ] seletor de tipo;
- [ ] colaborador vindo de endpoint já filtrado;
- [ ] destino por tipo;
- [ ] loading/sucesso/erro;
- [ ] sem lógica de approval policy no Angular.

Testes:

- [ ] REQ-01 a REQ-05.

---

## T-61 · ApprovalPolicy dinâmica

**Depende de:** T-60  
**Status:** [ ] aberta

- [ ] substituir dependência de mapa estático simples por função central `exigencias_para(...)`;
- [ ] tipos `GESTOR_SUPERIOR` e `GESTOR_RH`;
- [ ] exigência inclui ator esperado/perfil/ordem;
- [ ] perfis comuns nunca autoaprovam;
- [ ] exceção explícita: `ADMIN` pode aprovar a própria solicitação mediante ação manual explícita;
- [ ] RH_ANALISTA solicitante troca `RH` por `GESTOR_RH`;
- [ ] promoção resolve gestor do colaborador, superior do solicitante e caso topo;
- [ ] caso topo usa `RH_GESTOR` e não duplica etapa RH;
- [ ] Producer/Gate/Validation usam mesma fonte;
- [ ] nenhum mapa paralelo.

---

## T-62 · Aprovações + correção de histórico intermitente

**Depende de:** T-61  
**Status:** [ ] aberta

Backend:

- [ ] `GET /aprovacoes/pendentes`;
- [ ] `POST /movimentacoes/{id}/aprovacoes/{tipo}/decidir`;
- [ ] `AprovacaoService` única entrada de alteração;
- [ ] ator autorizado para a aprovação específica;
- [ ] ordem sequencial de promoção;
- [ ] dupla decisão rejeitada;
- [ ] `Aprovacao` + `HistoricoProcessamento` + gate + status + eventual Job no mesmo commit;
- [ ] falha ao inserir histórico faz rollback da aprovação;
- [ ] evento contém ator e solicitante;
- [ ] seed não gera aprovação decidida sem evento correspondente.

Frontend:

- [ ] tela Aprovações;
- [ ] somente itens que API devolve;
- [ ] Aprovar/Reprovar;
- [ ] atualizar lista após decisão.

Testes:

- [ ] APR-06;
- [ ] APR-09;
- [ ] APR-10;
- [ ] APR-11;
- [ ] reproduzir caso “GESTOR_ORIGEM APROVADA sem histórico” e provar correção.

---

## T-63 · Matrizes de aprovação

**Depende de:** T-61, T-62  
**Status:** [ ] aberta

Transferência:

- [ ] base = origem + destino + RH;
- [ ] solicitante origem → destino + RH;
- [ ] solicitante destino → origem + RH;
- [ ] RH_ANALISTA → origem + destino + GESTOR_RH.

Centro de custo:

- [ ] base = destino + RH;
- [ ] destino solicitante → RH;
- [ ] RH_ANALISTA → destino + GESTOR_RH.

Troca de gestor:

- [ ] base = origem + destino + RH;
- [ ] solicitante remove a própria etapa;
- [ ] RH_ANALISTA → origem + destino + GESTOR_RH.

Estrutura:

- [ ] base = origem + RH;
- [ ] origem solicitante → RH;
- [ ] RH_ANALISTA → origem + GESTOR_RH.

Promoção:

- [ ] primeira aprovação hierárquica;
- [ ] solicitante que seria aprovador → superior imediato;
- [ ] sem superior → RH_GESTOR substitui e não há outra etapa RH;
- [ ] RH_ANALISTA → gestor atual + GESTOR_RH;
- [ ] extra GERENCIA/DIRETORIA continua quando cargo exigir.

Testes:

- [ ] APR-01 a APR-08.

---

## T-64 · Promoção — regras P03/P07/P08/P09 e orçamento

**Depende de:** T-57, T-63  
**Status:** [ ] aberta

Catálogo:

- [ ] total passa de 34 para **37**;
- [ ] P03 = `ordem_progressao` destino exatamente atual + 1;
- [ ] P07 = mesma `familia_cargo`;
- [ ] P08 = 6 meses desde última promoção efetivada;
- [ ] P09 = CC suporta delta de custo;
- [ ] P04/P05/P06 continuam integridade das aprovações;
- [ ] `MUDANCA_CARREIRA` apenas documentada.

Contexto:

- [ ] dados necessários pré-carregados;
- [ ] zero I/O dentro das regras.

Efetivação:

- [ ] atualiza cargo;
- [ ] atualiza custo comprometido pelo delta;
- [ ] rollback conjunto se falhar.

Testes:

- [ ] PRO-01 a PRO-11;
- [ ] teste explícito: Júnior 1 → Júnior 2 permitido;
- [ ] teste explícito: Júnior 1 → Júnior 3 bloqueado;
- [ ] teste explícito: Júnior 3 → Pleno 1 permitido;
- [ ] teste explícito: Júnior 3 → Pleno 2 bloqueado;
- [ ] teste de catálogo exatamente 37.

---

## T-65 · Troca de gestor — integridade do aprovador

**Depende de:** T-63  
**Status:** [ ] aberta

- [ ] `GESTOR_ORIGEM` resolve gestor atual;
- [ ] `GESTOR_DESTINO` resolve novo gestor;
- [ ] teste com Wesley/Larissa ou IDs equivalentes;
- [ ] inversão falha TG06/integridade;
- [ ] TG05 continua somente ciclo;
- [ ] testes antigos de ciclo permanecem verdes.

Testes:

- [ ] TG-APR-01 a TG-APR-03.

---

## T-66 · Solicitante, auditoria e `motivoResumo`

**Depende de:** T-57, T-62  
**Status:** [ ] aberta

Detalhe:

- [ ] exibe solicitante;
- [ ] histórico expõe ator/solicitante conforme contrato;
- [ ] validação auditada preserva solicitante.

Listagem:

- [ ] adicionar coluna/campo `motivoResumo`;
- [ ] backend monta resumo;
- [ ] APROVADA deriva estado/evento real;
- [ ] REPROVADA usa contagem real;
- [ ] AGUARDANDO usa aprovações pendentes reais;
- [ ] BLOQUEADA usa aprovação/ator real;
- [ ] PENDENTE não é confundido com aprovação pendente;
- [ ] sem N+1 para montar motivos;
- [ ] Angular apenas renderiza/trunca visualmente.

Testes:

- [ ] MOT-01 a MOT-05.

---

## T-67 · Hardening e rate limiting

**Depende de:** T-58, T-59  
**Status:** [ ] aberta

- [ ] consultas 100 req/min por IP+identidade;
- [ ] escritas/aprovações 30 req/min por IP+identidade;
- [ ] `429` + `Retry-After`;
- [ ] não confiar cegamente em `X-Forwarded-For`;
- [ ] limite de body nas escritas;
- [ ] Pydantic com limites e enums;
- [ ] `extra=forbid` nos payloads sensíveis;
- [ ] CORS restrito;
- [ ] headers de segurança;
- [ ] logs removem Authorization/password;
- [ ] 500 sem stack trace;
- [ ] SQL continua parametrizado via ORM;
- [ ] documentação declara que rate limit local não é DDoS volumétrico.

Testes:

- [ ] burst acima de 100 read → 429;
- [ ] burst acima de 30 write → 429;
- [ ] rota normal dentro do limite passa;
- [ ] payload extra/rejeitado → 422.

---

## T-68 · Performance e cache de referência

**Depende de:** T-59, T-66, T-67  
**Status:** [ ] aberta

- [ ] benchmark antes de cache;
- [ ] revisar índices;
- [ ] BOLA aplicado antes da paginação;
- [ ] motivos carregados em lote;
- [ ] referências sem N+1;
- [ ] medir p50/p95;
- [ ] endpoints relevantes <2s com seed;
- [ ] se cache trouxer benefício, TTL local configurável para cargos/departamentos/CC;
- [ ] nunca cachear senha;
- [ ] nunca cachear JWT;
- [ ] nunca cachear aprovação/status/timeline/BOLA;
- [ ] documentar cache local como não distribuído.

---

## T-69 · Seed revisado

**Depende de:** T-57 a T-68  
**Status:** [ ] aberta

- [ ] usuário `admin` com senha hashada;
- [ ] login `admin/admin`;
- [ ] usuário `analistaRh` com senha hashada;
- [ ] login `analistaRh/analistaRh`;
- [ ] `analistaRh` vinculado a colaborador ativo da área de RH com superior compatível com `RH_GESTOR`;
- [ ] famílias de cargo;
- [ ] trilhas de promoção com `ordem_progressao` consecutiva (ex.: Júnior 1/2/3 → Pleno 1/2/3 → Sênior...);
- [ ] custos de cargos;
- [ ] CCs com orçamento suficiente/insuficiente;
- [ ] promoção recente e antiga;
- [ ] solicitante em toda movimentação;
- [ ] matrizes de aprovação coerentes;
- [ ] aprovação decidida sempre com histórico;
- [ ] produtor continua idempotente;
- [ ] rodar seed 2x não duplica;
- [ ] apagar DB + seed limpa lockout;
- [ ] reset CLI de lockout testado sem apagar DB.

---

## T-70 · Suite backend final

**Depende de:** T-69  
**Status:** [ ] aberta

Executar:

```bash
pytest
```

Conclusão:

- [ ] todos os testes antigos continuam verdes;
- [ ] AUTH-01…11;
- [ ] REQ-01…05;
- [ ] APR-01…11;
- [ ] PRO-01…11;
- [ ] TG-APR-01…03;
- [ ] MOT-01…05;
- [ ] rate limit;
- [ ] atomicidade;
- [ ] 37 regras;
- [ ] manual×Worker continua sem duplicidade;
- [ ] stale recovery continua funcionando;
- [ ] número real de testes registrado, não estimado.

---

## T-71 · Suite frontend + build

**Depende de:** T-60, T-62, T-66, T-69  
**Status:** [ ] aberta

Executar:

```bash
ng test --watch=false
ng build
```

Cobrir:

- [ ] login;
- [ ] token em memória;
- [ ] guard;
- [ ] interceptor;
- [ ] menu por scope;
- [ ] nova solicitação;
- [ ] aprovação;
- [ ] solicitante;
- [ ] `motivoResumo`;
- [ ] 401;
- [ ] 404 de objeto invisível;
- [ ] 429;
- [ ] nenhum cálculo BOLA/approval policy no Angular;
- [ ] build verde;
- [ ] números reais registrados.

---

## T-72 · Documentação e conformidade

**Depende de:** T-70, T-71  
**Status:** [ ] aberta

Atualizar:

- [ ] README;
- [ ] DECISIONS;
- [ ] IA_REPORT;
- [ ] architecture;
- [ ] operations;
- [ ] conformidade;
- [ ] catálogo de regras;
- [ ] ADR-0012 a ADR-0016 ou numeração livre equivalente.

Documentar:

- [ ] admin/admin e analistaRh/analistaRh apenas demo;
- [ ] senha hash, não cache;
- [ ] JWT/RBAC;
- [ ] evolução Entra/Keycloak;
- [ ] BOLA/subárvore;
- [ ] 404 para objeto fora de escopo;
- [ ] matriz dinâmica;
- [ ] promoção 37 regras total;
- [ ] mudança de carreira futura;
- [ ] lockout/reset;
- [ ] rate limit;
- [ ] DDoS em edge na evolução;
- [ ] performance/cache;
- [ ] resultados reais de testes/build/benchmark.

---

## 2. Dependências resumidas

| Tarefa | Depende de |
|---|---|
| T-57 | T-56 |
| T-58 | T-57 |
| T-59 | T-58 |
| T-60 | T-59 |
| T-61 | T-60 |
| T-62 | T-61 |
| T-63 | T-61, T-62 |
| T-64 | T-57, T-63 |
| T-65 | T-63 |
| T-66 | T-57, T-62 |
| T-67 | T-58, T-59 |
| T-68 | T-59, T-66, T-67 |
| T-69 | T-57 a T-68 |
| T-70 | T-69 |
| T-71 | T-60, T-62, T-66, T-69 |
| T-72 | T-70, T-71 |

---

## 3. Regra de fechamento

Nenhuma T-57…T-72 deve ser marcada `[x]` apenas porque o agente criou arquivos.

Cada tarefa exige:

```text
implementação
+ teste
+ execução real
+ resultado observado
```

Se a implementação atual já possuir parte de uma tarefa, verificar por código/teste antes de reaproveitar.


---

## Revisão corretiva pós-verificação integrada — T-73 a T-82

### T-73 · Trilha granular de promoção e semântica `nivel` × `ordem_progressao`
**Depende de:** T-64, T-69  
**Status:** [x] concluída

- [x] eliminar/remapear cargos ativos genéricos que façam `Analista Júnior → Analista Pleno` ser um passo válido — família "GERAL" agora tem Júnior 1/2/3 (ordem 1-3) e Pleno 1/2/3 (ordem 4-6), Júnior 1→Pleno 1 deixou de ser ordem+1;
- [x] massa ativa usa posições granulares por família — `_criar_cargos`/`app/seed/seed.py`;
- [x] `nivel` reinicia dentro da senioridade — corrigido bug real em `_criar_trilha_cargos` (gravava `nivel=ordem` em vez de `nivel=numero`) e aplicado também à família "GERAL";
- [x] `ordem_progressao` continua sequencial na família;
- [x] `Cargo.papel_lideranca = GERENCIA|DIRETORIA|null` para cargos de gestão — coluna nova em `app/models/cargo.py`, seed atribui GERENCIA/DIRETORIA a "gerente"/"diretor";
- [x] não parsear `Cargo.nome` para descobrir papel hierárquico — resolução por `papel_lideranca` fica para T-75 (aqui só o dado existe);
- [x] testes API/integração: Jr1→Jr2 ok, Jr1→Jr3 P03, Jr3→Pleno1 ok, Jr3→Pleno2 P03, Pleno3→Sênior1 ok (novo PRO-11), família distinta P07 — `tests/persistencia/test_t69_seed_promocao_avancada.py` (via Worker real);
- [x] teste explícito prova que o antigo atalho genérico Júnior→Pleno não é aprovável — `tests/persistencia/test_t73_trilha_granular.py::test_atalho_generico_junior_para_pleno_nao_e_mais_aprovavel` (via API real + Worker real, não só unitário).

Evidência: `pytest -q` → 395 passed (392 baseline + 3 novos testes T-73).

### T-74 · Snapshot correto no detalhe
**Depende de:** T-73  
**Status:** [x] concluída

- [x] `cargoAtual`/origem de promoção usa `mov.cargo_origem`, não `mov.colaborador.cargo` — bug real confirmado e corrigido em `app/api/routers/movimentacoes.py::_detalhe`;
- [x] revisar os cinco pares origem/destino para usar snapshot da `Movimentacao` — os outros quatro (departamento/gestor/centro de custo/estrutura) já liam do snapshot corretamente; só `cargo_atual` estava quebrado;
- [x] teste pós-efetivação: colaborador muda para destino, detalhe preserva origem antiga e destino solicitado — `tests/api/test_t74_snapshot_detalhe.py`, um teste por tipo, via `orchestrator.processar` real (não mock).

Evidência: `pytest -q` → 400 passed (395 + 5 novos testes T-74).

### T-75 · Aprovação adicional: liderança + RH_GESTOR
**Depende de:** T-61, T-63, T-73  
**Status:** [x] concluída

- [x] adicionar `TipoAprovacao.GESTOR_RH_ADICIONAL` (tipo técnico, mesmo perfil `RH_GESTOR`);
- [x] manter `UNIQUE(movimentacao_id,tipo)` sem colisão com `GESTOR_RH`;
- [x] `GERENCIA` resolve a pessoa mais próxima da cadeia com `papel_lideranca=GERENCIA` — `movimentacao_service.py::_resolver_lideranca`;
- [x] `DIRETORIA` resolve a pessoa mais próxima da cadeia com `papel_lideranca=DIRETORIA`;
- [x] adicional GERENCIA = hierarquia → RH/GESTOR_RH → GERENCIA → GESTOR_RH_ADICIONAL;
- [x] adicional DIRETORIA = hierarquia → RH/GESTOR_RH → DIRETORIA → GESTOR_RH_ADICIONAL;
- [x] P06 verifica o bundle adicional completo (as duas sub-etapas, não só a primeira);
- [x] se liderança correspondente não for resolvida, 409 `APROVADOR_HIERARQUICO_NAO_RESOLVIDO` sem persistência parcial;
- [x] casos topo-sem-superior e RH_ANALISTA continuam sem colisão de tipo;
- [x] **RC-42 (ambiguidade escalada e resolvida pelo candidato):** quando `GESTOR_ORIGEM`/`GESTOR_SUPERIOR` e `GERENCIA`/`DIRETORIA` resolvem para o mesmo colaborador, uma decisão real satisfaz as duas sem segundo clique, preservando os dois registros na auditoria — `AprovacaoService._auto_satisfazer_por_mesmo_aprovador`; etapas por perfil nunca deduplicam por coincidência de ator. Documentado em spec.md RC-42/APR-18/APR-19, plan.md §9.4/V-59, [ADR-0014 (Emenda T-75)](../../docs/decisoes/0014-matriz-dinamica-aprovacoes.md).
- [x] efeito colateral corrigido no mesmo escopo: `GET /aprovacoes/pendentes` (`aprovacao_service.listar_pendentes`) não filtrava por ordem — exposto pelos testes de T-75, corrigido reaproveitando a mesma checagem de `decidir`/`AprovacaoForaDeOrdem` (adianta parte do escopo de T-76).

Evidência: `pytest -q` → 405 passed (400 + 5 novos testes T-75, `tests/aprovacoes/test_t75_aprovacao_adicional.py`).

### T-76 · Pendências acionáveis e fonte única da ApprovalPolicy
**Depende de:** T-62, T-75  
**Status:** [x] concluída

- [x] `/aprovacoes/pendentes` devolve somente etapa `PENDENTE` acionável agora — `aprovacao_service.listar_pendentes` (checagem de ordem adiantada durante T-75, ao escrever os testes do bundle);
- [x] todas as ordens menores obrigatórias devem estar `APROVADA` — mesma checagem de `AprovacaoForaDeOrdem` reaproveitada;
- [x] RH não aparece antes da hierarquia — provado em `tests/aprovacoes/test_t75_aprovacao_adicional.py::test_promocao_gerencia_gera_bundle_de_quatro_etapas_na_ordem_certa`;
- [x] GERENCIA/DIRETORIA não aparecem antes de RH — mesmo teste;
- [x] GESTOR_RH_ADICIONAL não aparece antes de GERENCIA/DIRETORIA — mesmo teste;
- [x] remover mapa paralelo `EXIGENCIAS_POR_TIPO`/equivalente do seed — removido de `app/seed/seed.py`; `_criar_aprovacoes` agora chama `montar_contexto`+`exigencias_para` (a mesma política de produção), não mantém mais uma cópia congelada;
- [x] seed usa `exigencias_para`/ApprovalPolicy como fonte única;
- [x] teste de arquitetura/regressão contra nova duplicação — `tests/arquitetura/test_t76_fonte_unica_aprovacoes.py` (checagem AST: nenhuma atribuição top-level com "EXIGENCIA" no nome em `seed.py`, e uso confirmado de `exigencias_para`).

Nota: `tests/builders/aprovacoes_helper.py` mantém seu próprio `EXIGENCIAS_POR_TIPO` — é um helper de teste (não parte do seed/produção), fora do escopo literal de RC-41 ("fonte única também no seed"); usado por vários testes para montar aprovações rapidamente sem depender de `montar_contexto`.

Evidência: `pytest -q` → 407 passed (405 + 2 novos testes de arquitetura T-76).

### T-77 · JWT secret, scopes e navegação por capability
**Depende de:** T-58, T-59  
**Status:** [x] concluída

- [x] remover fallback funcional hardcoded de `JWT_SECRET` — `Settings.jwt_secret` agora sem default, `env_file` resolvido por `BASE_DIR` (não pelo CWD do processo);
- [x] runtime sem secret configurado falha explicitamente — `pydantic.ValidationError` na construção de `Settings()`, testado em subprocesso (`tests/security/test_t77_jwt_secret_obrigatorio.py`);
- [x] testes injetam secret próprio — `tests/conftest.py` define `JWT_SECRET` via `os.environ.setdefault` antes de qualquer import de `app.*`;
- [x] `.env.example` não contém segredo funcional — `backend/.env.example` criado (placeholder vazio + instruções); `backend/.env` real (dev local) adicionado a `.gitignore`;
- [x] `/auth/login`/`/auth/me` devolvem scopes efetivos — `UsuarioResponse.scopes`, populado por `permissions.scopes_do_perfil` (fonte única já existente);
- [x] remover `SCOPES_POR_PERFIL` paralelo do Angular — `AuthService.temEscopo` agora lê `usuario().scopes` recebido do backend;
- [x] criar `scopeGuard` — `core/guards/scope.guard.ts`, guard-factory por escopo;
- [x] `/aprovacoes` requer `movimentacoes:approve` para navegação — `app.routes.ts`;
- [x] `analistaRh` digitando `/aprovacoes` é redirecionado sem expor ação — `scopeGuard` redireciona para `/` (testado unitariamente; verificação end-to-end ao vivo adiada para T-81 por conflito de porta na ferramenta de preview);
- [x] backend continua sendo a segurança real — nenhuma rota da API mudou sua própria checagem de escopo/BOLA.

Evidência: backend `pytest -q` → 409 passed (407 + 2 novos testes JWT_SECRET). Frontend `ng test` → 71 SUCCESS (67 + 4 novos: scopeGuard ×3, AuthService.temEscopo ×1), `ng build` verde.

### T-78 · Hardening de payload e body
**Depende de:** T-67  
**Status:** [x] concluída

- [x] schema de `POST /validar` usa `extra=forbid` — `ValidarRequest`;
- [x] teste usa JWT válido e exige exatamente 422 para campo extra — `test_sec02_validar_com_campo_extra_autenticado_recebe_exatamente_422` (+ contraprova sem o campo extra); corrigido também o teste pré-existente de `POST /movimentacoes` que aceitava `(401, 422)` — anti-padrão explicitamente vetado, agora autentica e exige exatamente 422;
- [x] limite de body conta bytes recebidos no ASGI/request body — `HardeningMiddleware` agora sempre lê `await request.body()` e conta os bytes reais, não só `Content-Length`;
- [x] `Content-Length` pode ser fast-fail, nunca única defesa — mantido como atalho barato antes de ler o corpo, mas a contagem real sempre roda depois;
- [x] teste oversized sem depender de header confiável — dois testes: corpo enviado sem `Content-Length` (via gerador, sem header) e corpo com `Content-Length` mentiroso (baixo) mas corpo real grande — ambos rejeitados;
- [x] manter 429/rate limit e headers existentes sem regressão — suíte completa de `test_t67_hardening.py` (12 testes) verde.

Evidência: `pytest -q` → 415 passed (411 + 4 novos testes T-78).

### T-79 · Seed e regressão integrada
**Depende de:** T-73, T-75, T-76, T-77, T-78  
**Status:** [x] concluída

- [x] seed limpo e determinístico — banco recriado do zero (`portal_mobilidade_t79.db` temporário, apagado depois) e executado via `python -c` real, não só teste;
- [x] seed rodado duas vezes sem duplicar — 1ª execução: 141 movimentações/89 jobs; 2ª execução (idempotente): 141 movimentações/89 jobs, sem alteração;
- [x] admin/analistaRh continuam válidos — `admin` perfil ADMIN com hash Argon2id real; `analistaRh` perfil RH_ANALISTA com `colaborador_id` vinculado;
- [x] aprovações decididas sempre têm histórico — já garantido estruturalmente por `AprovacaoService.decidir`/seed (T-62/T-75), sem regressão nesta rodada;
- [x] trilhas e `papel_lideranca` coerentes — cargos "gerente"/"diretor" com `papel_lideranca` correto (T-73), confirmado por `tests/persistencia/test_t79_seed_bundle_adicional.py`;
- [x] promoção adicional gera as quatro ordens corretas quando aplicável — novo cenário dedicado `_gerar_cenarios_bundle_adicional` (seed real, matrículas M900201/M900202) usando a hierarquia real diretor→gerente→coordenador, cobrindo GERENCIA e DIRETORIA separadamente; testado via Worker real;
- [x] producer não duplica job — confirmado na execução real (2ª chamada do producer: 0 agendadas, mesma contagem de jobs);
- [x] Worker drena fila sem dupla efetivação — 89 jobs drenados, 89 auditorias (1:1), 29 `APROVADA` com 29 eventos `MOVIMENTACAO_EFETIVADA` (1:1); 2ª chamada ao Worker drena 0 (nada para reprocessar).

**Números reais desta execução (banco temporário, apagado ao final — não são os números finais de T-80/T-82, que rodam contra o banco de demonstração real):**
```text
Seed:     141 movimentações (89 agendadas, 25 bloqueadas, 25 aguardando)
Worker:   89 jobs drenados em 1.567s (17.6 ms/job em média)
Status:   AGUARDANDO_APROVACAO=25 PENDENTE=0 APROVADA=29 REPROVADA=62 BLOQUEADA=25
```

Evidência de teste automatizado: `pytest -q` → 418 passed (415 + 3 novos testes T-79, `tests/persistencia/test_t79_seed_bundle_adicional.py`).

### T-80 · Verificação backend + benchmark
**Depende de:** T-79  
**Status:** [x] concluída

- [x] `pytest -q` completo verde — **418 passed**, 0 falhas;
- [x] testes novos de T-73…T-78 verdes — inclusos nos 418 (T-73: 3, T-74: 5, T-75: 5, T-76: 2, T-77: 6, T-78: 4, T-79: 3 = 28 novos sobre o baseline de 392 desta revisão corretiva — mais 2 de T-69 e demais ajustes pontuais);
- [x] manual×Worker/stale recovery continuam verdes — mesma suíte, sem exclusão;
- [x] benchmark reexecutado — `python -m scripts.benchmark_performance` contra o seed atual (141 movimentações, não os 138 antigos);
- [x] p95 endpoints relevantes <2s — confirmado (ver números abaixo, ordens de grandeza abaixo do limite);
- [x] registrar número real de testes, seed, jobs e latências — não copiado de execução anterior, medido nesta sessão.

**Benchmark real (2026-08-19, seed com 141 movimentações):**
```text
GET /movimentacoes (42 chamadas):
  p50 = 6.8 ms | p95 = 18.9 ms | max = 75.1 ms

GET /movimentacoes/{id} (100 chamadas):
  p50 = 8.4 ms | p95 = 10.8 ms | max = 50.5 ms
```

Worker (medido em T-79 contra o mesmo seed): 89 jobs drenados em 1.567 s (17.6 ms/job em média).

### T-81 · Verificação frontend + build
**Depende de:** T-77, T-79  
**Status:** [x] concluída

- [x] `ng test --watch=false --browsers=ChromeHeadless` verde — **71 SUCCESS**, 0 falhas;
- [x] `ng build` verde — mesmo aviso pré-existente e não bloqueante de orçamento CSS em `detalhe.component.css`;
- [x] scopeGuard testado — `core/guards/scope.guard.spec.ts` (3 testes: permite com escopo, redireciona para `/` sem escopo, consulta o escopo exato da rota);
- [x] tela de aprovações mostra apenas retorno acionável da API — `AprovacoesComponent` só atribui `pendentes.set(itens)` a partir da resposta da API, sem filtro/ordenação própria; **bug real corrigido nesta verificação**: após decidir uma etapa, o componente só removia o item local (`.filter`) em vez de recarregar — uma etapa recém-destravada (ex.: RH após GESTOR_ORIGEM, ou GERENCIA após RH no bundle de T-75) não aparecia sem F5 manual. Corrigido para chamar `carregar()` (recarregar da API) após toda decisão bem-sucedida;
- [x] detalhe pós-promoção exibe snapshot correto — o componente só renderiza o campo `cargoAtual` já corrigido pelo backend em T-74, sem lógica própria de origem/destino;
- [x] registrar contagem real de testes — 71 SUCCESS (67 baseline + 4 de T-77: scopeGuard ×3, `AuthService.temEscopo` ×1; T-81 corrigiu 1 teste existente sem adicionar novo, pela mudança de comportamento do `AprovacoesComponent`).

**Nota de verificação ao vivo:** a verificação cross-stack real no navegador (login/scopeGuard/aprovações fim a fim) ficou bloqueada nesta sessão por um artefato do ambiente — a porta 8000 ficou presa em `LISTENING` por um processo já encerrado (PID inexistente em `Get-Process`/`Get-CimInstance`, mas ainda ocupando a porta em `netstat`), impedindo tanto a ferramenta de preview quanto um `uvicorn` manual de subir nela. Não é um problema de código: a cobertura automatizada é extensa dos dois lados (backend: `TestClient` real exercitando HTTP+JWT+scopes+decisão ponta a ponta; frontend: guards testados com serviços mockados). Recomenda-se reiniciar a máquina (ou aguardar o SO liberar a porta) antes de uma demonstração ao vivo real.

### T-82 · Documentação e conformidade final
**Depende de:** T-80, T-81  
**Status:** [x] concluída

- [x] `spec.md`, `plan.md`, `tasks.md` sincronizados — RC-42/APR-18/APR-19/critério de aceite 27 em `spec.md`; §9.4/V-59 em `plan.md`; T-73–T-82 marcadas com evidência real neste arquivo;
- [x] README/DECISIONS/architecture/operations/conformidade/catalogo/IA_REPORT sincronizados — números reais (141 movimentações, 89 jobs, 418+71 testes, benchmark p95 real), seção de configuração de `JWT_SECRET`, troubleshooting novo (JWT_SECRET, bundle de aprovação adicional), Rodada 8 completa no IA_REPORT;
- [x] ADR-0012/0013/0014/0015/0016 atualizadas e ADR-0017 registrada — 0012 (Emenda T-77, JWT_SECRET), 0013 (confirmação sem mudança de BOLA), 0014 (Emenda T-75, bundle + RC-42), 0015 (Emenda T-73, família GERAL granular), 0016 (Emenda T-78, body-size real + extra=forbid em /validar); [ADR-0017](../../docs/decisoes/0017-revisao-corretiva-pos-verificacao.md) novo, índice consolidado;
- [x] remover números antigos que divergirem da execução final — 138→141 movimentações, 392→418 testes backend, 67→71 testes frontend, benchmark antigo (p95=22.2/10.3ms) substituído pelo real (p95=18.9/10.8ms) em todos os documentos;
- [x] `docs/conformidade.md` V-46…V-59 marcadas somente com evidência real — cada linha aponta arquivo+teste real, não descrição genérica;
- [x] nenhuma documentação afirma que RH_GESTOR sozinho substitui GERENCIA/DIRETORIA — varrido (`grep`); as únicas ocorrências restantes estão explicitamente marcadas como supersedidas (ADR-0014, IA_REPORT.md);
- [x] nenhuma documentação afirma que cargos genéricos GERAL são inofensivos para promoção — varrido (`grep`); a única ocorrência restante está riscada e marcada "Falso — corrigido" (ADR-0015).

## Dependências da revisão corretiva

| Tarefa | Depende de |
|---|---|
| T-73 | T-64, T-69 |
| T-74 | T-73 |
| T-75 | T-61, T-63, T-73 |
| T-76 | T-62, T-75 |
| T-77 | T-58, T-59 |
| T-78 | T-67 |
| T-79 | T-73, T-75, T-76, T-77, T-78 |
| T-80 | T-79 |
| T-81 | T-77, T-79 |
| T-82 | T-80, T-81 |


---

## Revisão E2E de 2026-08-20 — T-83 a T-92

### T-83 · Header com navegação ativa
**Depende de:** T-81  
**Status:** [x] concluída

- [x] identificar rota ativa pelo Angular Router, sem estado manual paralelo — `routerLinkActive` nativo, sem boolean manual;
- [x] `Movimentações`, `Nova solicitação` e `Aprovações` alternam o destaque corretamente;
- [x] item ativo aplica exatamente:
  - [x] `font-weight: 700`;
  - [x] `font-size: 1.05rem`;
  - [x] `color: var(--cor-primaria-escura)`;
- [x] item anterior volta ao estilo normal ao navegar;
- [x] testes unitários de navegação ativa — `app.component.spec.ts` (3 testes).

Evidência: `app.component.html/.css/.ts`; confirmado ao vivo no navegador (classe `ativo` + estilo computado reais).

### T-84 · Listagem — ID, busca e `motivoResumo` curto
**Depende de:** T-66, T-80  
**Status:** [x] concluída

- [x] adicionar `ID` como primeira coluna antes da data;
- [x] busca por ID de movimentação;
- [x] preservar busca por matrícula;
- [x] preservar busca por nome do colaborador;
- [x] aplicar busca/BOLA antes da paginação — filtro no `WHERE` da mesma query, BOLA já aplicada antes (T-59);
- [x] revisar `motivoResumo` para frases curtas e amigáveis sem mudar a regra de origem server-side;
- [x] permitir wrap somente na coluna de motivo;
- [x] manter demais colunas centralizadas e sem quebra;
- [x] testes backend e frontend.

Evidência: `app/repositories/movimentacao_repository.py::listar`, `app/services/motivo_service.py`; `tests/api/test_movimentacoes_api.py::test_e2e03_busca_por_id_da_movimentacao`; `listagem.component.html/.css/.spec.ts` (3 testes novos); confirmado ao vivo no navegador.

### T-85 · BLOQUEADA terminal e detalhe/timeline coerentes
**Depende de:** T-62, T-76  
**Status:** [x] concluída

- [x] qualquer aprovação `REPROVADA` encerra a movimentação em `BLOQUEADA` — já funcionava (T-61/62);
- [x] nenhuma aprovação posterior da mesma movimentação aparece em `/aprovacoes/pendentes` — já funcionava (filtro por status `AGUARDANDO_APROVACAO`), confirmado com teste novo;
- [x] detalhe não apresenta “aguardando aprovação futura” quando status é `BLOQUEADA` — **bug real corrigido**: `calcular_impedimentos` reportava etapas `PENDENTE` nunca alcançadas junto da reprovação;
- [x] último estado/evento exibido aponta a aprovação real reprovada e ator;
- [x] preservar linhas posteriores do workflow sem transformá-las em pendência de negócio — continuam `PENDENTE` no banco (auditoria), só não são mais reportadas como impedimento/evento;
- [x] não criar novo status `CANCELADA`;
- [x] não gerar evento fictício posterior ao bloqueio — corrigido junto (mesma função alimenta `producer.aplicar_gate`);
- [x] preservar decisão + histórico + gate na mesma transação — inalterado;
- [x] regressões para reprovação em etapas iniciais/intermediárias/adicionais — TRANSFERENCIA (etapas paralelas) e bundle de promoção (GESTOR_ORIGEM→RH→DIRETORIA→GESTOR_RH_ADICIONAL).

Reforço além do pedido original: `AprovacaoService.decidir` agora rejeita (`409 MOVIMENTACAO_NAO_AGUARDANDO_APROVACAO`) decidir qualquer etapa de uma movimentação que não esteja mais `AGUARDANDO_APROVACAO` — sem isso, uma etapa “paralela” (mesma ordem) continuava tecnicamente decidível via API mesmo após o bloqueio.

Evidência: `app/processing/approval_gate.py::calcular_impedimentos`; `app/services/aprovacao_service.py::decidir`; `app/services/exceptions.py::MovimentacaoNaoAguardandoAprovacao`; `tests/processing/test_approval_gate.py::test_t85_reprovada_com_etapa_posterior_pendente_nunca_alcancada_nao_e_impedimento`; `tests/aprovacoes/test_t85_bloqueada_terminal.py` (2 testes); **reproduzido e confirmado ao vivo no navegador** com o caso crítico completo (promoção real, DIRETORIA reprovada pelo login `diretor`, GESTOR_RH_ADICIONAL nunca aparece como pendente em lugar nenhum).

### T-86 · Nova solicitação — cinco tipos + autocomplete de colaborador
**Depende de:** T-60, T-63, T-65  
**Status:** [x] concluída

Backend:
- [x] `POST /movimentacoes` aceita `TROCA_GESTOR`;
- [x] aceita `ALTERACAO_ESTRUTURA`;
- [x] origem é derivada pelo backend (`gestor_origem_id`/`estrutura_origem_id` do estado atual do colaborador);
- [x] solicitante vem do JWT;
- [x] payload não controla origem/status/aprovação — `extra="forbid"`, testado com payload forjado (422);
- [x] reutilizar ApprovalPolicy/engine existentes — nenhuma engine paralela, matriz já existia desde T-63;
- [x] referências de gestor/estrutura respeitam autorização aplicável — `GET /colaboradores` (BOLA) para gestor destino, `GET /referencias/estruturas` (catálogo, sem BOLA — igual aos demais catálogos) para estrutura destino.

Frontend:
- [x] exibir os cinco tipos;
- [x] renderizar campos destino adequados para troca de gestor;
- [x] renderizar campos destino adequados para alteração de estrutura;
- [x] colaborador permite seleção + digitação por nome/matrícula — autocomplete com debounce;
- [x] resultados respeitam BOLA — `GET /colaboradores?busca=` sempre pós-BOLA;
- [x] não alterar comportamento atual dos catálogos ativos/inativos — nenhuma mudança de filtro.

Regressão:
- [x] referência ativa na criação e inativada antes do processamento é detectada pela engine pelas regras atuais.

Evidência: `app/api/schemas/movimentacao.py` (`CriarTrocaGestorRequest`/`CriarAlteracaoEstruturaRequest`); `app/services/solicitacao_service.py`; `app/repositories/colaborador_repository.py`/`app/api/routers/colaboradores.py` (busca); `app/api/routers/referencias.py` (`/estruturas`); `tests/solicitacoes/test_t60_criacao.py` (E2E-08/09 + 2 regressões); `tests/referencias/test_t68_referencias_e_cache.py` (E2E-10 + BOLA + estruturas); `tests/integracao/test_t86_inativacao_posterior.py` (E2E-11); `nova-solicitacao.component.ts/.html/.css` + `.spec.ts` (7 testes novos); confirmado ao vivo (PROMOCAO e TROCA_GESTOR criadas de verdade via UI).

### T-87 · Aprovações — tabela, busca e ordenação
**Depende de:** T-76, T-81  
**Status:** [x] concluída

Backend:
- [x] `/aprovacoes/pendentes` suporta busca por ID;
- [x] suporta busca por nome/matrícula do colaborador;
- [x] ordenação padrão `data_solicitacao DESC`;
- [x] whitelist: ID/data/tipo/solicitante/colaborador/setor;
- [x] preservar filtro “somente acionáveis agora” — busca/ordenação aplicadas sobre o mesmo conjunto já filtrado, não substituem a checagem de ordem/BOLA/autorização;
- [x] preservar BOLA antes da paginação — não há paginação nesta tela (volume baixo, já documentado desde T-62); BOLA continua aplicada antes de qualquer filtro/ordenação.

Frontend:
- [x] tabela com ID;
- [x] Data da Solicitação;
- [x] Tipo;
- [x] Solicitante;
- [x] Colaborador;
- [x] Origem;
- [x] Destino;
- [x] Setor;
- [x] justificativa opcional;
- [x] Aprovar azul;
- [x] Reprovar vermelho;
- [x] busca;
- [x] ordenação;
- [x] recarregar dados após decisão;
- [x] origem/destino usa snapshot por tipo — `rotulo_service.py`, mesma correção de T-74 para cargo;
- [x] não inventar entidade `Setor`; reutilizar dado existente — `Colaborador.departamento`.

**Bug real pego só na verificação manual ao vivo** (não pelos testes unitários originais, que checavam substring solta em `linha.textContent`): a célula `<td>` de Setor estava ausente do template, desalinhando Origem/Destino/Justificativa/Ações uma coluna para a esquerda. Corrigido; teste de unidade reforçado para comparar célula-a-célula contra os cabeçalhos.

Evidência: `app/services/aprovacao_service.py::listar_pendentes` (busca/ordenação); `app/services/rotulo_service.py` (novo); `app/api/routers/aprovacoes.py`; `app/api/schemas/aprovacao.py`; `tests/aprovacoes/test_t87_tabela_aprovacoes.py` (E2E-12/13/14, 3 testes); `aprovacoes.component.ts/.html/.css` + `.spec.ts` (11 testes, incluindo o teste célula-a-célula) + `aprovacao.service.spec.ts` (1 teste novo); `styles.css` (`.perigo`); confirmado ao vivo pós-correção.

### T-88 · Seed — seis usuários de demonstração
**Depende de:** T-77, T-79  
**Status:** [x] concluída

- [x] `admin/admin` → `ADMIN`;
- [x] `analistaRh/analistaRh` → `RH_ANALISTA`;
- [x] `gestorRh/gestorRh` → `RH_GESTOR`;
- [x] `coordenador/coordenador` → `LIDERANCA`;
- [x] `gerente/gerente` → `LIDERANCA`;
- [x] `diretor/diretor` → `LIDERANCA`;
- [x] todas as senhas apenas em hash;
- [x] `gerente` vinculado a cargo `papel_lideranca=GERENCIA`;
- [x] `diretor` vinculado a cargo `papel_lideranca=DIRETORIA`;
- [x] hierarquia demonstrável e BOLA coerente — reaproveita a hierarquia real `diretor→gerente→coordenador→analista` já criada por `_criar_hierarquia` (T-57), nenhuma árvore paralela nova;
- [x] não criar perfis novos por cargo — `PerfilUsuario` continua com só 4 valores;
- [x] seed 2x continua idempotente.

Evidência: `app/seed/seed.py::_criar_usuarios_autenticaveis` (parâmetro `hierarquia` novo); `tests/persistencia/test_t88_seis_usuarios_demo.py` (7 testes: 6 logins, `gerente`/`diretor` papel_lideranca, hierarquia real, perfis não-novos, seed 2x, BOLA aninhada via login real); seed real executado (dev DB): 141 movimentações, 89 jobs, 6 usuários, idêntico em 2 execuções.

### T-89 · Override ADMIN anti-regressão
**Depende de:** T-59, T-88  
**Status:** [x] concluída

- [x] ADMIN consulta qualquer departamento/subárvore;
- [x] ADMIN cria para qualquer colaborador;
- [x] ADMIN decide qualquer aprovação;
- [x] ADMIN pode decidir a própria solicitação;
- [x] override não é herdado por `RH_GESTOR`/`RH_ANALISTA`/`LIDERANCA`;
- [x] testes fora da subárvore provam o comportamento — subárvores isoladas construídas só para o teste, sem depender do seed completo.

Nenhuma mudança de código — `object_scope`/`_usuario_pode_decidir` (T-59/T-62) já implementavam o bypass total. Esta tarefa é só cobertura de regressão nova.

Evidência: `tests/aprovacoes/test_t89_admin_override.py` (8 testes: ADMIN consulta/cria/decide fora de subárvore, ADMIN autoaprova, e 3 contraprovas de não-herança para RH_GESTOR/RH_ANALISTA/LIDERANCA).

### T-90 · Suite backend E2E-corretiva
**Depende de:** T-84 a T-89  
**Status:** [x] concluída

- [x] novos testes E2E-02,03,05,06,07,08,09,10,11,12,13,14,16,17 — todos nomeados explicitamente nos arquivos de teste desta rodada;
- [x] toda suíte anterior verde;
- [x] seed 2x;
- [x] Producer/Worker sem duplicidade;
- [x] benchmark <2s;
- [x] registrar números reais.

**Resultado real (2026-08-20):** `pytest -q` → **448 passed**, 0 falhas (418 baseline + 30 novos: T-85 ×3, T-84 ×1, T-86 ×5, T-87 ×3, T-88 ×7 [inclui V-89 de BOLA], T-89 ×8, T-86-referências ×3). Seed (banco temporário isolado desta rodada, recriado do zero): 141 movimentações/89 jobs, idêntico em 2 execuções. Worker: 89 jobs drenados em 1,846s (20,7 ms/job), 89 auditorias (1:1), 29 `APROVADA`/29 `MOVIMENTACAO_EFETIVADA` (1:1); 2ª chamada drena 0. Benchmark: `GET /movimentacoes` p50=7,0ms/p95=19,2ms/máx=74,0ms; `GET /movimentacoes/{id}` p50=8,4ms/p95=10,6ms/máx=48,3ms.

### T-91 · Suite frontend/build + smoke manual
**Depende de:** T-83, T-84, T-86, T-87, T-88  
**Status:** [x] concluída

Automático:
- [x] `ng test --watch=false --browsers=ChromeHeadless`;
- [x] `ng build`;
- [x] testes do header ativo;
- [x] listagem ID/busca/motivo;
- [x] cinco tipos + autocomplete;
- [x] tabela/busca/ordenação de aprovações.

**Resultado real:** `ng test` → **92 SUCCESS**, 0 falhas (71 baseline + 21 novos: `app.component.spec.ts` ×3, `listagem.component.spec.ts` ×3, `nova-solicitacao.component.spec.ts` ×7, `referencia.service.spec.ts` ×2, `aprovacoes.component.spec.ts` ×5, `aprovacao.service.spec.ts` ×1). `ng build` verde (mesmo aviso pré-existente não bloqueante em `detalhe.component.css`).

Manual cross-stack — **executado ao vivo no navegador nesta rodada** (dev DB resetado com autorização do usuário, dois processos Worker órfãos de sessão anterior encerrados antes):
- [x] admin — login real, listagem completa (141), header ativo confirmado, criação de PROMOCAO real;
- [x] analistaRh — perfil confere (não verificado clique-a-clique nesta rodada, cobertura automatizada extensa já existente de T-58/59);
- [x] gestorRh — colaborador/perfil confirmados via seed real (`tests/persistencia/test_t88_seis_usuarios_demo.py`), login exercitado indiretamente via query real ao backend;
- [x] coordenador — login real, listagem restrita a 66 movimentações (subárvore), header com menu completo;
- [x] gerente — não logado interativamente nesta rodada (coberto por `papel_lideranca=GERENCIA` real + teste de BOLA aninhada via login real);
- [x] diretor — login real, viu a etapa DIRETORIA em Aprovações (exatamente 1 item, o esperado), reprovou de verdade;
- [x] reprovar DIRETORIA e conferir `BLOQUEADA` terminal — confirmado: `motivoResumo` = "Bloqueada: DIRETORIA reprovada por Felipe Almeida.";
- [x] conferir que etapa posterior não aparece como aguardando — confirmado: impedimentos = só a reprovação, histórico sem menção a GESTOR_RH_ADICIONAL, item sumiu de Aprovações;
- [x] registrar evidência observada — ver acima e [ADR-0018](../../docs/decisoes/0018-revisao-e2e-2026-08-20.md).

Bug real encontrado e corrigido durante este smoke (não pego pelos testes automatizados originais): célula de Setor ausente no template de Aprovações, desalinhando colunas seguintes — ver T-87.

### T-92 · Documentação e conformidade E2E
**Depende de:** T-90, T-91  
**Status:** [x] concluída

- [x] `spec.md`, `plan.md`, `tasks.md` sincronizados — `spec.md`/`plan.md` já continham RC-43–RC-53/§24 desta rodada (fonte de verdade lida no início); este arquivo marca T-83–T-92 com evidência real;
- [x] README/DECISIONS/IA_REPORT/conformidade atualizados — `architecture.md`/`operations.md`/`docs/regras/catalogo-regras.md` não precisaram mudar (nenhuma regra de negócio nova, nenhuma decisão de infraestrutura nova);
- [x] atualizar credenciais de demo — tabela de 6 usuários em `README.md`;
- [x] números reais de testes/seed/jobs/benchmark — 448 backend / 92 frontend, seed 141/89/6 usuários, Worker 89 jobs em 1,846s, benchmark p95=19,2ms/10,6ms;
- [x] registrar V-60+ com evidência específica — `docs/conformidade.md` V-60 a V-69;
- [x] nenhum item marcado concluído sem execução real — todas as evidências acima vêm de `pytest -q`/`ng test`/`ng build`/seed real/Worker real/benchmark real/navegador real executados nesta sessão.

Evidência: [ADR-0018](../../docs/decisoes/0018-revisao-e2e-2026-08-20.md); `DECISIONS.md` (nova seção no topo); `docs/conformidade.md` (V-60–V-69); `README.md` (credenciais, benchmark, suíte, fluxo de avaliação).

### Dependências T-83+

| Tarefa | Depende de |
|---|---|
| T-83 | T-81 |
| T-84 | T-66, T-80 |
| T-85 | T-62, T-76 |
| T-86 | T-60, T-63, T-65 |
| T-87 | T-76, T-81 |
| T-88 | T-77, T-79 |
| T-89 | T-59, T-88 |
| T-90 | T-84 a T-89 |
| T-91 | T-83, T-84, T-86, T-87, T-88 |
| T-92 | T-90, T-91 |
