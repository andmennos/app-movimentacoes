# plan.md — Portal de Mobilidade Organizacional

**Feature:** 001-movimentacoes  
**Depende de:** `spec.md` revisão E2E de 2026-08-20  
**Escopo:** corrigir incrementalmente a implementação existente após testes E2E; preservar T-01–T-82 e abrir T-83+ para não conformidades reproduzidas no navegador.

---

## 1. Estratégia

Não reescrever o projeto.

Antes da primeira alteração:

```text
1. executar backend tests
2. executar frontend tests/build
3. registrar baseline real
4. inspecionar se manual×Worker, stale recovery, histórico e efetivação continuam implementados
5. somente então iniciar T-57+
```

Os números históricos de testes não devem ser tratados como verdade se a execução atual divergir.

---

## 2. Arquitetura alvo

```text
Angular
├─ Login
├─ Listagem
├─ Detalhe
├─ Nova solicitação
└─ Aprovações
      │
      │ JWT Bearer
      ▼
FastAPI
├─ security/
│  ├─ authentication
│  ├─ authorization/RBAC
│  ├─ object_scope/BOLA
│  └─ rate_limit
├─ api/
├─ services/
│  ├─ solicitacao_service
│  ├─ aprovacao_service
│  ├─ movimentacao_service
│  ├─ validacao_service
│  └─ efetivacao_service
├─ processing/
│  ├─ approval_gate
│  ├─ producer
│  ├─ orchestrator
│  └─ worker
├─ validation/
├─ repositories/
└─ SQLite
```

Fluxo de escrita:

```text
JWT
 ↓
autenticação
 ↓
scope funcional
 ↓
scope do objeto
 ↓
Pydantic
 ↓
Service transacional
 ↓
Repository
```

---

## 3. Dependências técnicas

Adicionar somente o necessário:

```text
PyJWT
pwdlib[argon2]
```

Não adicionar Keycloak, MSAL/Entra runtime, Redis ou broker.

Rate limiting pode ser implementado localmente sem infraestrutura externa, pois o MVP roda em processo único. A limitação distribuída fica documentada para API Management/gateway.

---

## 4. Segurança de senha: hash, não cache

Senha não entra em cache.

```text
admin
  ↓ Argon2id/password hasher
$argon2id$...
  ↓
SQLite
```

No login:

```text
senha recebida
  ↓ verify(hash)
sucesso/falha
```

Nunca:

```text
cache["admin"] = "admin"
```

O cache de performance é outra preocupação e fica restrito a referências estáveis.

---

## 5. Persistência

### 5.1 `Usuario`

Criar:

```text
id PK
username unique/index
password_hash
perfil
colaborador_id nullable
ativo
criado_em
```

Seed cria:
- `admin/admin` → `ADMIN`;
- `analistaRh/analistaRh` → `RH_ANALISTA`;
- `gestorRh/gestorRh` → `RH_GESTOR`;
- `coordenador/coordenador` → `LIDERANCA`;
- `gerente/gerente` → `LIDERANCA`, colaborador com `papel_lideranca=GERENCIA`;
- `diretor/diretor` → `LIDERANCA`, colaborador com `papel_lideranca=DIRETORIA`.

Os vínculos organizacionais devem formar uma hierarquia demonstrável e coerente com BOLA/ApprovalPolicy.

Enums:

```text
ADMIN
RH_ANALISTA
RH_GESTOR
LIDERANCA
```

### 5.2 `SecurityLockout`

```text
id
ip unique/index
failed_attempts
window_started_at
blocked_until
updated_at
```

Operações devem ser transacionais.

### 5.3 `Movimentacao`

Adicionar:

```text
solicitante_usuario_id FK Usuario
```

Para promoção, assegurar snapshot suficiente do CC atual se necessário para auditoria sem depender do estado futuro.

### 5.4 `Cargo`

Adicionar:

```text
familia_cargo
ordem_progressao
papel_lideranca = GERENCIA | DIRETORIA | null
custo_mensal_referencia
```

Índices onde fizer sentido para seleção/filtro.

### 5.5 `CentroCusto`

Adicionar:

```text
orcamento_mensal
custo_comprometido
```

### 5.6 Auditoria/histórico

`HistoricoProcessamento`:

```text
ator_usuario_id nullable
solicitante_usuario_id nullable
```

`ValidacaoAuditoria`:

```text
solicitante_usuario_id
ator_usuario_id nullable
```

Preservar append-only.

---

## 6. Autenticação

### 6.1 Configuração

Adicionar settings:

```text
JWT_SECRET=<obrigatório via ambiente; sem default funcional>
JWT_ALGORITHM=HS256
JWT_EXPIRE_MINUTES=30

LOGIN_FAILURE_WINDOW_SECONDS=300
LOGIN_MAX_FAILURES=3
LOGIN_BLOCK_SECONDS=1800

RATE_LIMIT_READ_PER_MINUTE=100
RATE_LIMIT_WRITE_PER_MINUTE=30
```

Não commitar segredo real.

### 6.2 `security/passwords.py`

Responsabilidade:

```text
hash_password
verify_password
```

Nenhuma outra camada conhece detalhes do algoritmo.

### 6.3 `security/jwt.py`

```text
create_access_token
decode_and_validate_token
```

Claims mínimas:

```text
sub
perfil
scopes
exp
```

### 6.4 Dependências FastAPI

```text
get_current_user
require_scope(...)
```

`get_current_user` também confirma usuário ativo no banco.

### 6.5 Login

Fluxo:

```text
POST /auth/login
 ↓
IP está bloqueado?
 ├─ sim → 429
 └─ não
      ↓
buscar usuário
      ↓
verificar hash
 ├─ falha → incrementar janela/lockout
 └─ sucesso → limpar falhas aplicáveis → emitir JWT
```

Usar resposta de credencial inválida genérica.

### 6.6 Reset para banca

Criar módulo CLI:

```bash
python -m app.security.reset_lockouts
```

Ele remove/zera `SecurityLockout` e nada mais.

---

## 7. RBAC e BOLA

### 7.1 `security/permissions.py`

Mapeamento único:

```text
ADMIN
RH_ANALISTA
RH_GESTOR
LIDERANCA
```

para scopes.

Exceção explícita de segregação de funções:

```text
ADMIN pode aprovar solicitação criada pelo próprio ADMIN.
Nenhum outro perfil pode autoaprovar.
```

Esse mapa é estático em código; não precisa de cache de rede/banco.

### 7.2 `security/object_scope.py`

Funções:

```text
pode_visualizar_colaborador(usuario, colaborador)
pode_criar_para_colaborador(usuario, colaborador)
pode_visualizar_movimentacao(usuario, movimentacao)
pode_decidir_aprovacao(usuario, aprovacao)
```

Para liderança, usar toda a subárvore.

Evitar N+1: não percorrer a hierarquia com uma query por nível em cada item da listagem. Para SQLite/MVP, carregar conjunto de IDs da subárvore uma vez por request ou usar consulta hierárquica adequada.

### 7.3 Repository recebe escopo

`movimentacao_repository.listar(...)` recebe filtro de IDs/escopo já autorizado e aplica antes de `count`/pagina.

`buscar_por_id` protegido deve incorporar/validar escopo antes de montar DTO.

Fora do escopo:

```text
404
```

não `403`.

---

## 8. Criação de solicitações

### 8.1 Schemas

Usar union discriminada por `tipo`.

Entrada não aceita:

```text
solicitante
origem
status
aprovações
resultado
```

Esses campos são derivados pelo backend.

Configurar schemas sensíveis com `extra="forbid"`.

### 8.2 `SolicitacaoService`

Fluxo:

```text
1. conferir scope create
2. carregar colaborador e destino
3. derivar origem atual
4. criar Movimentacao
5. chamar ApprovalPolicy
6. criar Aprovacao(s)
7. criar SOLICITACAO_RECEBIDA
8. avaliar gate
9. commit
```

Se qualquer passo falhar, rollback.

### 8.3 Endpoints auxiliares

Criar endpoints de referência autenticados para:

```text
colaboradores
cargos
departamentos
centros de custo
```

Colaboradores respeitam BOLA.

---

## 9. ApprovalPolicy dinâmica

Evoluir a fonte única atual para uma função determinística, reutilizável pelo:

```text
SolicitacaoService
ApprovalGate
AprovacaoService
ValidationContext/integridade
tests
```

Não criar mapas paralelos.

### 9.1 Dados de saída

Cada exigência pode conter:

```text
tipo
aprovador_esperado_colaborador_id nullable
perfil_esperado nullable
ordem
```

Assim o sistema diferencia aprovação por pessoa específica e aprovação por perfil.

### 9.2 Autoaprovação

Regra para perfis comuns:

```text
se aprovador esperado == solicitante.colaborador_id
→ aplicar substituição/remoção definida na spec
```

Exceção:

```text
perfil == ADMIN
→ pode decidir aprovação da própria solicitação
```

Não transformar isso em autoaprovação automática: o `ADMIN` ainda precisa executar explicitamente a ação Aprovar/Reprovar pela API/UI.

### 9.3 Promoção sequencial

Persistir `ordem` nas aprovações ou derivá-la deterministicamente.

Sem adicional:

```text
1 hierarquia → 2 RH/GESTOR_RH
```

Com `aprovacao_adicional`:

```text
1 hierarquia
→ 2 RH/GESTOR_RH
→ 3 GERENCIA ou DIRETORIA (pessoa concreta da cadeia, resolvida por Cargo.papel_lideranca)
→ 4 GESTOR_RH_ADICIONAL (perfil RH_GESTOR)
```

`GESTOR_RH_ADICIONAL` é um tipo técnico distinto de `GESTOR_RH`, para permitir que ambos existam na mesma movimentação preservando `UNIQUE(movimentacao_id,tipo)`. Não adiciona regra da engine.

`AprovacaoService.decidir` verifica que todas as etapas anteriores obrigatórias estão `APROVADA`. `GET /aprovacoes/pendentes` aplica a mesma regra e só devolve etapas acionáveis agora.

### 9.4 Dedup de aprovador (RC-42)

Decisão do candidato na revisão corretiva (T-75): quando duas exigências de **pessoa específica** (`aprovador_esperado_colaborador_id`) da mesma movimentação resolvem para o **mesmo colaborador** — ex.: `GESTOR_ORIGEM` e `GERENCIA` ambos resolvendo para o mesmo gestor direto —, a decisão real dessa pessoa em uma delas satisfaz a outra automaticamente, sem exigir um segundo clique.

Implementação (`AprovacaoService._auto_satisfazer_por_mesmo_aprovador`, chamada ao final de `decidir`, antes da reavaliação do gate):

```text
loop até estabilizar:
  para cada exigência ainda PENDENTE, pessoa-específica, com etapas
  anteriores já APROVADA:
    se já existe, nesta movimentação, uma Aprovacao APROVADA com
    aprovador_id == aprovador_esperado_colaborador_id desta exigência
    (em qualquer OUTRO tipo):
      marca esta exigência como APROVADA, mesmo aprovador_id
      registra HistoricoProcessamento explícito ("satisfeita
      automaticamente — mesmo aprovador de <tipo original>")
```

Regras:

- só se aplica a exigências de pessoa específica; etapas por **perfil** (`RH`/`GESTOR_RH`/`GESTOR_RH_ADICIONAL`) nunca deduplicam por coincidência de ator, mesmo quando a mesma pessoa (ex.: `ADMIN` via override) decide as duas;
- o casamento é pelo `aprovador_id` **já persistido**, não pelo `aprovador_esperado_colaborador_id` "no papel" — uma decisão via override de `ADMIN` grava `aprovador_id = ADMIN`, então não ativa a dedup para uma etapa que esperava outra pessoa;
- cada exigência auto-satisfeita continua como sua própria `Aprovacao` — nunca é removida/fundida; a auditoria sempre mostra os dois papéis atendidos;
- roda em loop até estabilizar, porque satisfazer uma etapa pode destravar a ordem (RC-35) da próxima.

---

## 10. Aprovação transacional e bug de histórico

Criar/centralizar:

```text
AprovacaoService.decidir(...)
```

Única entrada de alteração de aprovação.

Fluxo:

```text
load movement
authorize BOLA
load required approval
authorize actor
validate order
update approval
append approval event
re-evaluate gate
update movement status
ensure job if all approved
commit once
```

Teste de falha:

```text
forçar erro ao criar historico
→ rollback
→ aprovação continua PENDENTE
```

Seed deve usar helper de geração de histórico coerente ou gerar Aprovacao + evento na mesma função de montagem.

---

## 11. Promoção — novas regras

### 11.1 ValidationContext

Adicionar refs simples:

```text
familia_cargo_atual
familia_cargo_destino
ordem_progressao_atual
ordem_progressao_destino
data_ultima_promocao_efetivada
orcamento_mensal_cc
custo_comprometido_cc
custo_cargo_atual
custo_cargo_destino
```

As queries ocorrem antes da engine.

### 11.2 P03

Alterar de “qualquer nível superior” para **próximo passo exato da trilha**:

```text
destino.ordem_progressao == atual.ordem_progressao + 1
```

Não usar apenas `nivel`, porque a numeração reinicia entre senioridades. Exemplo:

```text
Júnior 1 (ordem 1)
→ Júnior 2 (ordem 2)
→ Júnior 3 (ordem 3)
→ Pleno 1  (ordem 4)
→ Pleno 2  (ordem 5)
→ Pleno 3  (ordem 6)
→ Sênior 1 (ordem 7)
```

Assim `Júnior 3 → Pleno 1` é permitido, mas `Júnior 1 → Pleno 1` e `Júnior 3 → Pleno 2` são saltos e devem falhar P03. `nivel` deve reiniciar dentro da senioridade (`Pleno 1.nivel = 1`), enquanto `ordem_progressao` continua global na família (`Pleno 1.ordem_progressao = 4`). O seed não pode manter cargos ativos genéricos que transformem `Analista Júnior → Analista Pleno` em ordens consecutivas.

### 11.3 P07

```text
familia destino == familia atual
```

Mudança de carreira fica fora do MVP.

### 11.4 P08

```text
data_solicitacao >= ultima_promocao_efetivada + 6 meses calendário
```

Se nunca houve promoção efetivada, passa.

### 11.5 P09

```text
delta = max(custo_destino - custo_atual, 0)
saldo = orcamento_mensal - custo_comprometido

delta <= saldo
```

### 11.6 Efetivação

Dentro da mesma transação:

```text
colaborador.cargo_id = destino
centro_custo.custo_comprometido += delta
```

---

## 12. Troca de gestor

Corrigir/garantir resolução:

```text
GESTOR_ORIGEM = movimentacao.gestor_origem
GESTOR_DESTINO = movimentacao.gestor_destino
```

Criar teste anti-regressão com nomes/IDs invertidos.

TG05 continua apenas:

```text
novo gestor não cria ciclo
```

TG06 cobre integridade do aprovador.

---

## 13. Motivo resumido

Criar uma única função/service:

```text
montar_motivo_resumo(movimentacao, aprovacao_context, ultima_validacao, historico_relevante)
```

Não executar uma query nova por linha.

Estratégias:

- incluir agregados necessários na query da página;
- ou fazer consulta em lote para os IDs da página;
- nunca N+1.

O texto deve ser curto, sanitizado e derivado do estado real.

---

## 14. Rate limiting

### 14.1 Login

Lockout persistente é separado do rate limiter geral.

### 14.2 Geral

Middleware/dependency local:

```text
read: 100/min
write: 30/min
```

Chave:

```text
IP + user_id quando autenticado
IP quando anônimo
```

Usar relógio monotônico para janela em memória; login lockout continua persistido.

Retorno:

```http
429
Retry-After
```

### 14.3 Limitação

Documentar explicitamente:

```text
não é DDoS protection
não é distribuído
reinício limpa apenas rate-limit geral em memória
lockout de login continua no SQLite
```

Produção usa gateway/WAF/DDoS edge.

---

## 15. Input/API hardening

Adicionar middleware/handlers para:

- limite de body em escrita sobre os bytes efetivamente recebidos; `Content-Length` é apenas fast-fail opcional;
- JSON esperado;
- Pydantic `extra=forbid`, inclusive no schema de `POST /validar`;
- campos string com tamanho máximo;
- enum para decisões/tipos;
- sort whitelist já existente;
- mensagens 500 genéricas;
- `Cache-Control: no-store` em login/respostas sensíveis;
- headers de segurança;
- logs que removem `Authorization` e senha.

Não implementar “sanitização” por regex genérica que altere nomes legítimos. Validar contrato, limitar tamanho, parametrizar SQL e escapar na camada de apresentação.

---

## 16. Cache

### 16.1 Antes do cache

Medir:

```text
GET /movimentacoes
GET /movimentacoes/{id}
GET /colaboradores
referências
```

O requisito é tempo <2s, não “ter cache”.

### 16.2 Permitido

Cache local TTL curto somente para:

```text
lista de cargos
lista de departamentos
lista de centros de custo
```

Sugestão inicial: 60s, configurável.

### 16.3 Proibido

```text
senha/password_hash
JWT
aprovação
movimentação/status
timeline
BOLA por objeto
resultado de autorização
```

---

## 17. Frontend

### 17.1 Auth

Criar:

```text
core/auth/
login/
auth.service
auth.guard
scope.guard
auth.interceptor
```

Token somente em memória. Scopes efetivos são recebidos do backend no login/`/auth/me`; remover qualquer `SCOPES_POR_PERFIL` paralelo no Angular. `scopeGuard` controla apenas navegação/UX (ex.: `/aprovacoes` requer `movimentacoes:approve`); o backend continua reautorizando tudo.

Ao recarregar totalmente a página, novo login é aceitável no MVP.

### 17.2 Solicitação

Feature:

```text
features/movimentacoes/solicitacao/
```

Form baseado nos cinco tipos do domínio, sem duplicar regra de negócio no Angular:

```text
TRANSFERENCIA
PROMOCAO
MUDANCA_CENTRO_CUSTO
TROCA_GESTOR
ALTERACAO_ESTRUTURA
```

O colaborador usa autocomplete/typeahead por nome/matrícula com seleção de uma entidade retornada pela API. O backend continua derivando origem e solicitante.

### 17.3 Aprovação

Criar:

```text
features/aprovacoes/
```

Lista só pendências devolvidas pela API.

### 17.4 Listagem

Adicionar `motivoResumo`.

Não montar a mensagem a partir de enums no TypeScript.

### 17.5 Detalhe

Adicionar solicitante e preservar timeline real.

---

## 18. Performance

Manter:

- índices existentes;
- índices novos em `Usuario.username`, `SecurityLockout.ip`, `Movimentacao.solicitante_usuario_id`;
- paginação max 100;
- ordenação estável;
- BOLA na query;
- queries em lote de motivos;
- eager loading apenas do necessário.

Medir p50/p95 em script simples e registrar no README/operations.

5.000 movimentações/dia ≈ baixo throughput médio; o objetivo da fila continua desacoplamento e absorção de rajadas.

---

## 19. Testes

### Backend

Adicionar suites:

```text
tests/security/
tests/authorization/
tests/solicitacoes/
tests/aprovacoes/
```

Cobrir todos os cenários AUTH/REQ/APR/PRO/TG-APR/MOT da spec.

### Frontend

Cobrir:

- login sucesso/erro/bloqueio;
- guard;
- interceptor;
- menus por scopes;
- form de solicitação;
- aprovação;
- motivoResumo;
- solicitante;
- 401/404/429;
- ausência de lógica de autorização decisória no Angular.

### Regressão

Rodar toda suíte antiga. T-47–T-56 não podem regredir.

---

## 20. Seed

Atualizar seed em ordem segura:

```text
estrutura/cargos granulares/CC/colaboradores
→ papel_lideranca explícito nos cargos de gestão
→ usuario admin com hash
→ movimentações com solicitante
→ aprovações
→ histórico coerente
→ producer
```

Criar cenários para novas regras e workflow.

`admin/admin` e `analistaRh/analistaRh` são credenciais locais de demonstração.

---

## 21. Documentação

Atualizar:

```text
README.md
DECISIONS.md
docs/IA_REPORT.md
docs/architecture.md
docs/operations.md
docs/conformidade.md
docs/decisoes/
docs/regras/catalogo-regras.md
```

Adicionar ADRs:

```text
ADR-0012 autenticação local JWT/RBAC com evolução Entra/Keycloak
ADR-0013 BOLA e escopo hierárquico
ADR-0014 matriz dinâmica de aprovações/no-self-approval
ADR-0015 promoção: família, nível, intervalo e orçamento
ADR-0016 hardening/rate-limit local e proteção DDoS em edge
```

---

## 22. Verificações de conformidade

```text
V-23  37 regras executáveis
V-24  P03 exatamente +1 em `ordem_progressao` dentro da família
V-25  P07 mesma família
V-26  P08 6 meses
V-27  P09 orçamento CC
V-28  admin/admin e analistaRh/analistaRh autenticam, senhas hash
V-29  JWT expira e rotas exigem auth
V-30  RH_ANALISTA lê/cria e não aprova
V-31  liderança vê só subárvore
V-32  objeto fora de escopo não aparece e ID direto = 404
V-33  solicitante derivado do JWT
V-34  no-self-approval
V-35  promoção sequencial
V-36  RH_GESTOR substitui topo sem superior e não duplica RH
V-37  aprovação + histórico atômicos
V-38  TG origem/destino não invertidos
V-39  motivoResumo vem do backend
V-40  lockout 3/5min por 30min
V-41  reset_lockouts funciona
V-42  rate limit local 100/30
V-43  cache nunca contém senha/JWT/aprovação/BOLA
V-44  endpoints relevantes <2s
V-45  T-47–T-56 continuam verdes
```


---

## 23. Revisão corretiva pós-verificação integrada (T-73+)

A verificação de ponta a ponta posterior à T-72 encontrou divergências que a suíte verde anterior não cobria. Esta seção é normativa para a correção incremental.

### 23.1 Trilha de promoção e massa de dados

- remover/remapear cargos ativos genéricos que permitam `Analista Júnior → Analista Pleno` como um passo;
- manter `nivel` reiniciando por senioridade e `ordem_progressao` sequencial por família;
- `GET /referencias/cargos` deve oferecer ao fluxo de promoção apenas massa coerente com a trilha ativa;
- adicionar integração API/Worker para os casos Jr1→Jr2, Jr1→Jr3, Jr3→Pleno1, Jr3→Pleno2 e Pleno3→Sênior1.

### 23.2 Snapshot do detalhe

O DTO de detalhe usa exclusivamente as FKs snapshot da `Movimentacao` para origem/destino. Nunca usar `mov.colaborador.cargo` como origem depois da efetivação. Aplicar o mesmo princípio aos cinco tipos.

### 23.3 Workflow adicional de promoção

Adicionar `TipoAprovacao.GESTOR_RH_ADICIONAL`, decidido por `RH_GESTOR`.

```text
sem adicional:
1 hierarquia → 2 RH/GESTOR_RH

com GERENCIA:
1 hierarquia → 2 RH/GESTOR_RH → 3 GERENCIA → 4 GESTOR_RH_ADICIONAL

com DIRETORIA:
1 hierarquia → 2 RH/GESTOR_RH → 3 DIRETORIA → 4 GESTOR_RH_ADICIONAL
```

`GERENCIA`/`DIRETORIA` apontam para uma pessoa concreta da cadeia, resolvida pelo `Cargo.papel_lideranca`. Não inferir por `Cargo.nome`.

Se o papel necessário não existir na cadeia, rejeitar a criação/ativação do workflow com `409 APROVADOR_HIERARQUICO_NAO_RESOLVIDO`, sem persistência parcial.

### 23.4 Pendências acionáveis

`GET /aprovacoes/pendentes` filtra por estado, autorização/BOLA **e ordem**. Etapa posterior pendente não é retornada antes de todas as ordens inferiores obrigatórias estarem aprovadas.

### 23.5 Fonte única da política

Eliminar qualquer `EXIGENCIAS_POR_TIPO` duplicado no seed. Seed e testes chamam `exigencias_para`/ApprovalPolicy com contexto apropriado.

### 23.6 Segurança corretiva

- `JWT_SECRET` obrigatório via ambiente, sem fallback funcional no repositório;
- backend devolve scopes efetivos; Angular usa scopes recebidos;
- `scopeGuard` para rotas com capability específica;
- `/validar` com `extra=forbid`, teste autenticado exigindo 422;
- body-size middleware limita bytes reais mesmo sem `Content-Length` confiável.

### 23.7 Verificações adicionais

```text
V-46  seed/referências não permitem atalho genérico Júnior→Pleno
V-47  nivel reinicia por senioridade; ordem_progressao é sequencial
V-48  detalhe pós-efetivação preserva snapshot origem/destino
V-49  pendentes mostra apenas etapa acionável agora
V-50  adicional GERENCIA exige liderança GERENCIA + GESTOR_RH_ADICIONAL
V-51  adicional DIRETORIA exige liderança DIRETORIA + GESTOR_RH_ADICIONAL
V-52  papel_lideranca resolve pessoa concreta sem parse de nome
V-53  seed não contém matriz paralela de aprovações
V-54  JWT_SECRET não possui default funcional hardcoded
V-55  scopes do Angular vêm do backend e /aprovacoes usa scopeGuard
V-56  /validar com campo extra autenticado retorna exatamente 422
V-57  body acima do limite é rejeitado sem depender de Content-Length
V-58  backend/frontend/build/seed/worker/benchmark reexecutados e documentação atualizada com números reais
V-59  dedup de aprovador (RC-42): mesma pessoa em duas exigências de pessoa específica satisfaz as duas com uma decisão; auditoria preserva os dois registros; etapas por perfil nunca deduplicam por coincidência de ator
```


---

## 24. Revisão E2E de 2026-08-20 — T-83+

Esta seção é normativa para a próxima implementação incremental.

### 24.1 T-83 — estado ativo do header

Angular:

```text
header/nav
→ derivar item ativo do Router
→ aplicar classe de ativo em um único item correspondente
```

CSS obrigatório:

```css
font-weight: 700;
font-size: 1.05rem;
color: var(--cor-primaria-escura);
```

Preferir mecanismo nativo do Router (`routerLinkActive` ou equivalente simples). Não manter booleans manuais divergentes da URL.

### 24.2 T-84 — listagem: ID, busca e motivo curto

Backend:

```text
GET /movimentacoes
search = termo textual existente
+ suportar ID quando termo for numérico
```

A busca continua cobrindo nome/matrícula. Aplicar filtro antes da paginação e preservar BOLA.

Frontend:

```text
ID = primeira coluna
motivoResumo = única coluna com wrap
demais colunas = centralizadas e nowrap
```

`motivoResumo` continua server-driven. Revisar copy para frases curtas; não mover regra de estado para TypeScript.

### 24.3 T-85 — BLOQUEADA é terminal

Corrigir precedência de apresentação/serviço:

```text
qualquer Aprovacao REPROVADA
→ movimentacao.status = BLOQUEADA
→ workflow de aprovação encerrado
→ /aprovacoes/pendentes não retorna nenhuma etapa daquela movimentação
→ detalhe não apresenta uma etapa posterior PENDENTE como estado atual
```

Não criar `TipoEstadoAprovacao.CANCELADA` nem novo status de movimentação.

As linhas futuras podem permanecer `PENDENTE` internamente para preservar o workflow calculado, mas ficam inacionáveis e não representam pendência de negócio.

Timeline/detalhe:

- a decisão `REPROVADA` deve continuar persistida em `HistoricoProcessamento`;
- o último estado apresentado deve ser a causa real, por exemplo `Aprovação DIRETORIA reprovada por <ator>.`;
- não gerar evento fictício de “aguardando GESTOR_RH_ADICIONAL” depois de bloqueio;
- preservar atomicidade da decisão + histórico + gate.

### 24.4 T-86 — cinco tipos criáveis + colaborador pesquisável

Evoluir a union discriminada do `POST /movimentacoes` e o formulário Angular para:

```text
TRANSFERENCIA
PROMOCAO
MUDANCA_CENTRO_CUSTO
TROCA_GESTOR
ALTERACAO_ESTRUTURA
```

Payloads novos mínimos:

```text
TROCA_GESTOR:
  colaboradorId
  gestorDestinoId

ALTERACAO_ESTRUTURA:
  colaboradorId
  estruturaDestinoId
```

Origem e solicitante continuam derivados no backend.

Reusar as regras e ApprovalPolicy já existentes. Não criar engine paralela.

Colaborador:

```text
digita nome/matrícula
→ API devolve opções autorizadas
→ usuário seleciona colaborador
```

Aplicar debounce simples se necessário, sem cachear BOLA/autorização.

Se a origem da estrutura atual não estiver inequívoca no modelo vigente, parar e perguntar antes de introduzir campo/regra.

### 24.5 Catálogos ativos/inativos — nenhuma alteração funcional

Não alterar filtro/listagem atual de cargos, departamentos, CCs, estruturas ou gestores apenas por esta revisão.

Cenário a provar:

```text
solicitação criada quando referência estava ativa
→ referência torna-se inativa
→ processamento posterior
→ regra já existente detecta inatividade
```

Isso valida as regras atuais sem expor deliberadamente itens descontinuados no formulário.

### 24.6 T-87 — Aprovações como tabela pesquisável/ordenável

Backend deve evoluir `GET /aprovacoes/pendentes` com filtros/paginação/ordenação necessários sem quebrar a propriedade “somente acionáveis agora”.

Busca:

```text
ID da movimentação
nome/matrícula do colaborador
```

Padrão:

```text
sort=data_solicitacao
direction=desc
```

Whitelist de sort:

```text
id
data_solicitacao
tipo
solicitante
colaborador
setor
```

Frontend tabela:

```text
ID
Data da Solicitação
Tipo
Solicitante
Colaborador
Origem
Destino
Setor
```

Por linha, manter justificativa opcional e ações:

```text
Aprovar  → botão azul existente
Reprovar → botão vermelho
```

`Origem/Destino` são snapshots/rótulos por tipo.

Para `Setor`, reutilizar o campo/relacionamento já existente. Se não houver fonte inequívoca, parar e perguntar — não criar entidade `Setor`.

Após decisão, recarregar a página/lista do backend para que a próxima etapa recém-destravada apareça corretamente.

### 24.7 T-88 — usuários de demonstração

Seed autenticável:

```text
admin/admin
analistaRh/analistaRh
gestorRh/gestorRh
coordenador/coordenador
gerente/gerente
diretor/diretor
```

Perfis:

```text
admin       ADMIN
analistaRh  RH_ANALISTA
gestorRh    RH_GESTOR
coordenador LIDERANCA
gerente     LIDERANCA
diretor     LIDERANCA
```

Não criar enum de perfil por cargo.

Vínculos:

```text
coordenador → hierarquia demonstrável
gerente     → Cargo.papel_lideranca=GERENCIA
diretor     → Cargo.papel_lideranca=DIRETORIA
```

`ADMIN` continua bypass de BOLA/approval actor no MVP conforme RC-12/RC-53.

### 24.8 T-89 — testes backend

Adicionar regressões para:

```text
busca GET /movimentacoes por ID
BLOQUEADA terminal depois de reprovação em cada posição relevante
BLOQUEADA nunca retorna /aprovacoes/pendentes
timeline final de BLOQUEADA aponta a reprovação real
POST TROCA_GESTOR
POST ALTERACAO_ESTRUTURA
origens derivadas e payload não forja origem
busca/ordenação/paginação de /aprovacoes/pendentes
seis usuários autenticáveis
BOLA de coordenador/gerente/diretor
ADMIN fora da subárvore continua com acesso total
inativação posterior de referência é detectada pela engine
```

Toda a suíte anterior permanece obrigatória.

### 24.9 T-90 — testes frontend/build

Adicionar testes para:

```text
nav ativo troca com a rota
ID como primeira coluna
busca envia ID/nome/matrícula
motivo usa wrap sem alterar demais colunas
cinco opções em Nova solicitação
autocomplete de colaborador
tabela de aprovações
busca e ordenação de aprovações
recarrega após decidir
login dos novos perfis via contrato/mock
```

Executar:

```bash
ng test --watch=false --browsers=ChromeHeadless
ng build
```

### 24.10 T-91 — smoke E2E manual

Após testes verdes, executar no navegador real:

```text
admin → cria e decide fora de qualquer subárvore
analistaRh → cria e não aprova
gestorRh → aprova etapas RH atribuídas
coordenador → vê/atua apenas na subárvore
gerente → demonstra GERENCIA quando atribuído
diretor → reprova DIRETORIA e movimentação termina BLOQUEADA
```

Verificar visualmente:

```text
header ativo
ID/listagem
motivo
busca por ID
cinco tipos
autocomplete
tabela de aprovações
BLOQUEADA sem falsa pendência posterior
```

### 24.11 T-92 — documentação/conformidade

Somente depois da evidência real:

- atualizar números de testes;
- atualizar seed/jobs se mudarem;
- registrar os seis usuários de demo;
- atualizar IA_REPORT/DECISIONS/ADRs se a implementação exigir decisão técnica nova;
- registrar V-60+ com arquivo/teste/evidência específica;
- não marcar tarefa concluída com base apenas em código escrito.
