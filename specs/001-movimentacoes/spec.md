# spec.md — Portal de Mobilidade Organizacional

**Feature:** 001-movimentacoes  
**Status:** Revisão E2E de 2026-08-20. T-57–T-72 representam a implementação-base; T-73–T-82 representam a revisão corretiva anterior; T-83+ trata não conformidades e ajustes encontrados em testes E2E reais.  
**Escopo:** MVP local (Angular → FastAPI + Producer/Worker Python → SQLite). Preserva T-01–T-82 como histórico e abre uma revisão incremental T-83+, sem reescrever o projeto.

---

## 0. Decisões congeladas desta revisão

Esta revisão substitui qualquer decisão anterior incompatível com autenticação, criação de solicitações, aprovação pelo portal, matriz dinâmica de aprovações e novas regras de promoção.

| # | Decisão |
|---|---|
| RC-01 | O MVP continua com cinco tipos de movimentação: `TRANSFERENCIA`, `PROMOCAO`, `TROCA_GESTOR`, `MUDANCA_CENTRO_CUSTO`, `ALTERACAO_ESTRUTURA`. |
| RC-02 | `MUDANCA_CARREIRA` é evolução futura. Não é implementada nesta revisão. |
| RC-03 | O catálogo passa a possuir exatamente **37 regras executáveis**: 4 gerais + 6 transferência + 9 promoção + 6 troca de gestor + 6 centro de custo + 6 alteração de estrutura. |
| RC-04 | `AE05` continua `origem ≠ destino`; ciclo hierárquico continua exclusivo de `TG05`. |
| RC-05 | Promoção exige mesma `familia_cargo` e avanço de **exatamente uma posição na trilha ordenada de progressão** da família (`ordem_progressao_destino = ordem_progressao_atual + 1`), além de intervalo mínimo de 6 meses desde a última promoção efetivada e capacidade orçamentária do centro de custo atual. |
| RC-06 | Troca de família de cargo não é promoção neste MVP. Deve ser documentada como futura `MUDANCA_CARREIRA`. |
| RC-07 | Regra geral: o solicitante não aprova a própria solicitação. **Exceção explícita:** `ADMIN` é o único perfil autorizado a criar e aprovar a própria solicitação para fins de administração/demonstração do MVP. Para todos os demais perfis, a política de aprovações resolve substituições/remoções de etapas sem autoaprovação. |
| RC-08 | Somente `ADMIN`, `RH_ANALISTA` e `LIDERANCA` criam solicitações no MVP. `RH_GESTOR` consulta e aprova; não cria solicitações. |
| RC-09 | `RH_ANALISTA` consulta todas as movimentações e colaboradores, pode criar solicitações, mas não pode aprovar. |
| RC-10 | `RH_GESTOR` consulta todas as movimentações e decide etapas `RH`, `GESTOR_RH` e `GESTOR_RH_ADICIONAL` quando a política as atribuir ao perfil. |
| RC-11 | `LIDERANCA` pode consultar e criar solicitações somente para colaboradores de toda a sua subárvore hierárquica. |
| RC-12 | `ADMIN` é superusuário do MVP: consulta, cria e aprova qualquer objeto e é o **único perfil** que pode aprovar uma solicitação criada por ele próprio. |
| RC-13 | O seed cria seis usuários autenticáveis de demonstração: `admin/admin` (`ADMIN`), `analistaRh/analistaRh` (`RH_ANALISTA`), `gestorRh/gestorRh` (`RH_GESTOR`), `coordenador/coordenador`, `gerente/gerente` e `diretor/diretor` (os três últimos com perfil técnico `LIDERANCA`, vinculados a colaboradores/cargos coerentes com sua posição hierárquica). Senhas nunca são persistidas em texto puro; somente seus hashes são armazenados. |
| RC-14 | Autenticação local usa JWT Bearer com RBAC/scopes. Microsoft Entra ID e Keycloak são evolução documentada, não runtime do MVP. |
| RC-15 | Senhas não são cacheadas. O JWT não contém senha. O frontend não persiste senha nem token em `localStorage`; o token do MVP fica somente em memória da sessão Angular. |
| RC-16 | Toda rota protegida aplica autorização funcional e autorização em nível de objeto. Objetos fora do escopo não aparecem na listagem e, se acessados por ID direto, respondem `404` para não revelar sua existência. |
| RC-17 | A validação final só executa depois que todas as aprovações exigidas estão `APROVADA`. |
| RC-18 | O fluxo normal continua automático: aprovações concluídas → `PENDENTE` → Job → Worker → Orchestrator → Engine → efetivação. |
| RC-19 | `POST /validar` continua fallback manual somente quando o backend retorna `podeValidarManualmente=true`. |
| RC-20 | Worker e manual continuam coordenados pelo mesmo orquestrador; dupla auditoria/dupla efetivação é regressão crítica. |
| RC-21 | A timeline é persistida em `HistoricoProcessamento`; aprovação e seu evento de histórico pertencem à mesma transação. |
| RC-22 | O solicitante é persistido na movimentação e exposto no detalhe; auditorias/eventos registram solicitante e ator quando aplicável. |
| RC-23 | A listagem recebe `motivoResumo` produzido pelo backend. O Angular não interpreta regras para construir o motivo. |
| RC-24 | Estados de negócio continuam: `AGUARDANDO_APROVACAO`, `PENDENTE`, `APROVADA`, `REPROVADA`, `BLOQUEADA`. `PENDENTE` não significa aprovação pendente. |
| RC-25 | Login: 3 falhas dentro de 5 minutos bloqueiam o IP por 30 minutos. O bloqueio é persistido no SQLite e pode ser removido por CLI local de demonstração ou pelo reset completo do banco/seed. |
| RC-26 | Limite local inicial: consultas 100 req/min por IP e identidade autenticada; escritas/aprovações 30 req/min por IP e identidade. Excesso retorna `429` + `Retry-After`. |
| RC-27 | O rate limiter do FastAPI é defesa de aplicação, não proteção contra DDoS volumétrico. Evolução: Azure DDoS Protection/Front Door WAF/API Management antes da aplicação. |
| RC-28 | Meta de performance permanece <2s nos endpoints relevantes com seed. Primeiro otimizar índices, paginação, queries e payload; cache só em dados de referência estáveis. |
| RC-29 | Pode existir cache local de TTL curto para cargos, departamentos e centros de custo. Não cachear senha, aprovação, status de movimentação, timeline nem decisão BOLA por objeto. |
| RC-30 | SQLite + Worker único continuam no MVP. Redis, Celery, RabbitMQ, Kafka, Kubernetes e cloud em runtime permanecem fora do MVP. |
| RC-31 | Nenhuma nova regra ou matriz de aprovação além das descritas aqui pode ser inventada durante implementação; ambiguidade deve ser escalada ao candidato. |
| RC-32 | `Cargo.nivel` e `Cargo.ordem_progressao` têm semânticas diferentes. `nivel` reinicia dentro da senioridade (ex.: Júnior 1/2/3, Pleno 1/2/3); `ordem_progressao` é a posição sequencial global dentro da `familia_cargo` e é a única fonte de P03. |
| RC-33 | O seed e as referências de promoção não podem manter atalhos genéricos ativos que transformem `Analista Júnior → Analista Pleno` em um único passo. A massa ativa deve usar cargos granulares e trilhas coerentes. |
| RC-34 | Origem/destino mostrados no detalhe são sempre os snapshots da `Movimentacao` (`*_origem_id`/`*_destino_id`), nunca o estado atual já efetivado do `Colaborador`. |
| RC-35 | `GET /aprovacoes/pendentes` retorna somente aprovações **acionáveis agora**: `PENDENTE`, autorizadas para o ator/objeto e com todas as etapas anteriores obrigatórias já `APROVADA`. Etapas futuras não aparecem. |
| RC-36 | Quando `Cargo.aprovacao_adicional = GERENCIA|DIRETORIA`, a promoção exige **duas anuências adicionais**: a liderança hierárquica correspondente (`GERENCIA` ou `DIRETORIA`) e, depois, `RH_GESTOR`. Ambas são obrigatórias. |
| RC-37 | Para distinguir a anuência final de RH da etapa `GESTOR_RH` que pode substituir RH/hierarquia em outros cenários, introduzir o tipo técnico de aprovação `GESTOR_RH_ADICIONAL`. Ele é decidido pelo perfil `RH_GESTOR`, não adiciona regra de validação e preserva `UNIQUE(movimentacao_id,tipo)`. |
| RC-38 | A liderança correspondente de `GERENCIA`/`DIRETORIA` deve ser resolvida para uma pessoa concreta da cadeia de `gestor_id`, sem inferência por texto livre do cargo. `Cargo.papel_lideranca` (`GERENCIA|DIRETORIA|null`) é o discriminador técnico do MVP. |
| RC-39 | `JWT_SECRET` é obrigatório via ambiente/configuração em runtime e não possui fallback funcional hardcoded no repositório. Os scopes efetivos vêm do backend; o Angular não mantém uma matriz paralela por perfil. |
| RC-40 | Payloads sensíveis, inclusive `POST /validar`, usam `extra=forbid`. O limite de body é aplicado sobre os bytes realmente recebidos, não somente por `Content-Length`. |
| RC-41 | A política de aprovações permanece fonte única também no seed. Não existe `EXIGENCIAS_POR_TIPO` ou equivalente paralelo fora de `ApprovalPolicy/exigencias_para`. |
| RC-42 | Quando duas exigências de aprovação de **pessoa específica** (`aprovador_esperado_colaborador_id`) da mesma movimentação resolvem para o **mesmo colaborador**, uma única decisão real dessa pessoa satisfaz as duas — não é exigido um segundo clique do mesmo aprovador. Cada exigência continua existindo como sua própria `Aprovacao`/evento de histórico (a auditoria nunca perde a informação de que havia dois requisitos distintos, nem "funde" os dois papéis em um só registro). Etapas por **perfil** (`RH`/`GESTOR_RH`/`GESTOR_RH_ADICIONAL`) nunca são deduplicadas só por coincidência de quem decidiu — mesmo que a mesma pessoa (ex.: `ADMIN` via override) decida as duas, cada uma exige sua própria decisão explícita. Decisão via override de `ADMIN` (RC-12) não ativa a dedup para outra etapa: o `aprovador_id` gravado é o do `ADMIN`, não o da pessoa esperada, então só a identidade real registrada é usada para o casamento. |
| RC-43 | O header destaca somente o item de navegação correspondente à tela ativa. O item ativo recebe `font-weight: 700`, `font-size: 1.05rem` e `color: var(--cor-primaria-escura)`; ao navegar, o destaque sai do item anterior e passa ao atual. |
| RC-44 | A listagem de movimentações exibe `ID` como primeira coluna, antes de `DATA DA SOLICITAÇÃO`. |
| RC-45 | `motivoResumo` permanece responsabilidade do backend, mas deve ser curto e amigável. A célula de motivo pode quebrar linha; as demais colunas permanecem centralizadas e sem quebra. |
| RC-46 | A busca da listagem de movimentações aceita ID da movimentação, matrícula ou nome do colaborador. Quando o termo for um ID numérico válido, a API pode tratar como filtro por ID sem remover a busca textual existente. |
| RC-47 | `BLOQUEADA` é terminal para o workflow de aprovação. Depois que qualquer aprovação exigida é `REPROVADA`, a movimentação é encerrada como `BLOQUEADA`; aprovações posteriores deixam de representar pendência de negócio, não aparecem em `/aprovacoes/pendentes` e o detalhe/timeline não pode apresentar “aguardando aprovação” como estado/evento corrente. O último estado apresentado deve refletir a reprovação real que causou o bloqueio. |
| RC-48 | Os cinco tipos do domínio passam a ser criáveis pela UI/API: `TRANSFERENCIA`, `PROMOCAO`, `MUDANCA_CENTRO_CUSTO`, `TROCA_GESTOR` e `ALTERACAO_ESTRUTURA`. |
| RC-49 | Na Nova solicitação, o colaborador pode ser localizado por seleção e por digitação de nome/matrícula, respeitando RBAC/BOLA. A origem continua derivada pelo backend; o cliente não controla origem, solicitante, status ou aprovações. |
| RC-50 | Esta revisão **não altera** o comportamento atual dos catálogos de referência quanto a entidades ativas/inativas. O caso relevante é uma referência tornar-se inativa depois da criação da solicitação; nesse caso, a engine deve detectar a inatividade no processamento pelas regras já existentes. Não criar nova regra nem relaxar regra existente. |
| RC-51 | A tela Aprovações passa a ser uma tabela pesquisável/ordenável. Busca: colaborador ou ID da movimentação. Ordenação padrão: `data_solicitacao DESC`; campos ordenáveis: ID, data, tipo, solicitante, colaborador e setor. Colunas: ID, Data da Solicitação, Tipo, Solicitante, Colaborador, Origem, Destino e Setor; justificativa opcional e ações Aprovar/Reprovar ficam associadas à linha. |
| RC-52 | `coordenador`, `gerente` e `diretor` usam o mesmo perfil técnico `LIDERANCA`; sua capacidade concreta continua determinada por hierarquia, BOLA, `aprovador_esperado_colaborador_id` e `Cargo.papel_lideranca` quando aplicável. Não criar perfis novos `COORDENADOR`, `GERENTE` ou `DIRETOR`. |
| RC-53 | `ADMIN` preserva override master: pode consultar, criar, aprovar e reprovar qualquer movimentação do MVP, independentemente do departamento/subárvore, inclusive a própria solicitação. A exceção não deve ser propagada para outros perfis. |

---

## 1. Fluxo do produto

```text
Login
  ↓ JWT
Usuário autenticado
  ↓ RBAC + escopo do objeto
Criar solicitação
  ↓
ApprovalPolicy gera aprovações exigidas
  ↓
AGUARDANDO_APROVACAO
  ├─ alguma aprovação REPROVADA → BLOQUEADA
  └─ todas APROVADA             → PENDENTE
                                      ↓
                                  Producer
                                      ↓
                                JobValidacao
                                      ↓
                                    Worker
                                      ↓
                             ProcessingOrchestrator
                                      ↓
                               ValidationEngine
                           ┌──────────┴──────────┐
                           ↓                     ↓
                    inconsistências          sem falhas
                           ↓                     ↓
                      REPROVADA            efetivação local
                                                ↓
                                             APROVADA
```

### 1.1 Estados visíveis

| Status | Significado |
|---|---|
| `AGUARDANDO_APROVACAO` | ao menos uma aprovação exigida ainda está pendente |
| `PENDENTE` | todas as aprovações terminaram e o processamento final ainda não concluiu |
| `APROVADA` | engine passou e a alteração foi efetivada no SQLite |
| `REPROVADA` | engine executou e encontrou inconsistências |
| `BLOQUEADA` | uma aprovação exigida foi reprovada |

---

## 2. Usuários, autenticação e perfis

### 2.1 Entidade `Usuario`

Campos mínimos:

```text
id
username                 unique/index
password_hash
perfil                    ADMIN | RH_ANALISTA | RH_GESTOR | LIDERANCA
colaborador_id            nullable FK Colaborador
ativo
criado_em
```

O seed cria exatamente seis usuários autenticáveis de demonstração:

```text
admin / admin             → ADMIN
analistaRh / analistaRh   → RH_ANALISTA
gestorRh / gestorRh       → RH_GESTOR
coordenador / coordenador → LIDERANCA
gerente / gerente         → LIDERANCA
diretor / diretor         → LIDERANCA
```

Os usuários de liderança devem estar vinculados a colaboradores ativos em uma hierarquia coerente que permita demonstrar escopo por subárvore e aprovações de `GERENCIA`/`DIRETORIA`. O colaborador associado a `gerente` deve ocupar cargo com `papel_lideranca=GERENCIA`; o de `diretor`, cargo com `papel_lideranca=DIRETORIA`. `analistaRh` permanece vinculado a colaborador ativo de RH e `gestorRh` a colaborador elegível para as etapas de `RH_GESTOR`.

`password_hash` deve ser calculado com algoritmo adequado para senha. O valor `admin` não pode existir em coluna de senha em texto puro.

### 2.2 Login

Endpoint:

```http
POST /auth/login
```

Entrada:

```json
{
  "username": "admin",
  "password": "admin"
}
```

Saída:

```json
{
  "accessToken": "...",
  "tokenType": "bearer",
  "expiresIn": 1800,
  "usuario": {
    "id": 1,
    "username": "admin",
    "perfil": "ADMIN"
  }
}
```

O token:

- expira em 30 minutos;
- não contém senha;
- contém identificação do usuário, perfil e scopes necessários;
- é assinado com segredo obtido por configuração/ambiente;
- não usa segredo hardcoded de exemplo no repositório.

### 2.3 Perfis e capacidades

| Perfil | Consulta | Cria solicitação | Aprova |
|---|---|---|---|
| `ADMIN` | tudo | tudo | qualquer aprovação do MVP |
| `RH_ANALISTA` | todas as movimentações/colaboradores | sim | não |
| `RH_GESTOR` | todas as movimentações/colaboradores | não | aprova etapas `RH`/`GESTOR_RH` e demais quando explicitamente elegível |
| `LIDERANCA` | sua subárvore hierárquica | colaboradores da sua subárvore | apenas aprovações atribuídas a ele |

Scopes sugeridos:

```text
movimentacoes:read
movimentacoes:create
movimentacoes:approve
movimentacoes:validate
colaboradores:read
```

O perfil define os scopes. O backend ainda precisa conferir o objeto concreto.

---

## 3. BOLA / autorização em nível de objeto

### 3.1 Listagem

O escopo deve ser aplicado na query, antes da paginação:

- `ADMIN`: sem filtro de escopo;
- `RH_ANALISTA`: sem filtro de escopo organizacional;
- `RH_GESTOR`: sem filtro de escopo organizacional;
- `LIDERANCA`: somente movimentações cujo colaborador pertence à sua subárvore hierárquica.

Um líder não recebe linhas fora do escopo. O frontend não precisa esconder depois de receber: a API já não devolve.

### 3.2 Acesso por ID

Para:

```http
GET /movimentacoes/{id}
POST /movimentacoes/{id}/aprovacoes/{tipo}/decidir
POST /validar
```

o backend verifica o objeto antes da ação.

Se o objeto existir mas estiver fora do escopo do usuário:

```http
404 MOVIMENTACAO_NAO_ENCONTRADA
```

A resposta não revela que existe uma movimentação inacessível.

### 3.3 Colaboradores disponíveis para solicitação

- `ADMIN`, `RH_ANALISTA`, `RH_GESTOR`: podem consultar todos os colaboradores necessários à sua capacidade de leitura;
- `LIDERANCA`: endpoint de seleção retorna apenas sua subárvore;
- colaborador comum não possui perfil autenticável nesta entrega.

---

## 4. Criação de solicitações

### 4.1 Tipos criáveis pelo portal nesta revisão

A UI/API cria os cinco tipos do domínio:

```text
TRANSFERENCIA
PROMOCAO
MUDANCA_CENTRO_CUSTO
TROCA_GESTOR
ALTERACAO_ESTRUTURA
```

A criação continua passando pelo mesmo `SolicitacaoService`, `ApprovalPolicy`, histórico e gate. Não criar caminho paralelo para os dois tipos adicionados à UI.

### 4.2 Endpoint

```http
POST /movimentacoes
Authorization: Bearer <token>
```

Payload discriminado por `tipo`.

#### Transferência

Cliente envia:

```json
{
  "tipo": "TRANSFERENCIA",
  "colaboradorId": 10,
  "departamentoDestinoId": 5
}
```

Backend deriva:

```text
solicitante_usuario_id
departamento_origem_id = colaborador.departamento_id
```

#### Promoção

```json
{
  "tipo": "PROMOCAO",
  "colaboradorId": 10,
  "cargoDestinoId": 7
}
```

Backend deriva:

```text
cargo_origem_id = colaborador.cargo_id
centro_custo_origem_id = colaborador.centro_custo_id
solicitante_usuario_id = usuário do JWT
```

#### Mudança de centro de custo

```json
{
  "tipo": "MUDANCA_CENTRO_CUSTO",
  "colaboradorId": 10,
  "centroCustoDestinoId": 8
}
```

Backend deriva:

```text
centro_custo_origem_id = colaborador.centro_custo_id
solicitante_usuario_id
```

#### Troca de gestor

```json
{
  "tipo": "TROCA_GESTOR",
  "colaboradorId": 10,
  "gestorDestinoId": 20
}
```

Backend deriva a origem a partir do gestor atual real do colaborador e preserva a integridade já definida em `TG06`.

#### Alteração de estrutura

```json
{
  "tipo": "ALTERACAO_ESTRUTURA",
  "colaboradorId": 10,
  "estruturaDestinoId": 5
}
```

Backend deriva a estrutura de origem a partir do estado atual do colaborador/relacionamento já existente no domínio. Se a implementação atual não possuir uma fonte única inequívoca para a estrutura atual do colaborador, **parar e perguntar ao candidato em vez de inventar um campo ou regra**.


O cliente não pode escolher valores de origem nem o solicitante.

### 4.3 Criação transacional

Uma criação bem-sucedida persiste, na mesma transação:

```text
Movimentacao
+ aprovações exigidas calculadas pela política
+ HistoricoProcessamento(SOLICITACAO_RECEBIDA)
```

Status inicial:

```text
AGUARDANDO_APROVACAO
```

Se a política resultar sem aprovação humana pendente por algum caso especial, reavaliar gate e permitir `PENDENTE` + job.

---

## 5. Política única de aprovações

A fonte única deixa de ser um mapa estático simples e passa a ser uma função pura/determinística:

```text
exigencias_para(movimentacao, solicitante, contexto_organizacional)
```

Nenhum Router, Producer, Worker ou componente Angular mantém cópia da matriz.

### 5.1 Regra geral e exceção administrativa

```text
Perfis comuns:
solicitante não aprova a própria solicitação

ADMIN:
pode aprovar a própria solicitação
```

A exceção de `ADMIN` é deliberada e exclusiva do MVP de demonstração. Não deve ser aplicada a `RH_ANALISTA`, `RH_GESTOR` ou `LIDERANCA`.

Quando o solicitante ocupar uma posição que normalmente aprovaria, a etapa é removida ou substituída conforme a matriz abaixo.

### 5.2 Tipos de aprovação

```text
GESTOR_ORIGEM
GESTOR_DESTINO
GESTOR_SUPERIOR
RH
GESTOR_RH
GESTOR_RH_ADICIONAL
GERENCIA
DIRETORIA
```

### 5.3 Transferência

Base:

```text
GESTOR_ORIGEM + GESTOR_DESTINO + RH
```

Se solicitante = `GESTOR_ORIGEM`:

```text
GESTOR_DESTINO + RH
```

Se solicitante = `GESTOR_DESTINO`:

```text
GESTOR_ORIGEM + RH
```

Se solicitante = `RH_ANALISTA`:

```text
GESTOR_ORIGEM + GESTOR_DESTINO + GESTOR_RH
```

Se uma etapa de gestor corresponder ao próprio solicitante em qualquer outro caso, essa etapa não é autoaprovada.

### 5.4 Promoção

Primeira etapa hierárquica:

- normalmente é o gestor atual do colaborador;
- se esse gestor for o solicitante, a primeira aprovação passa para o superior imediato do solicitante (`GESTOR_SUPERIOR`);
- se esse solicitante não possuir superior hierárquico, uma etapa `GESTOR_RH` decidida pelo perfil `RH_GESTOR` substitui a aprovação hierárquica e **não existe uma segunda etapa RH normal**;
- se o solicitante for `RH_ANALISTA`, a primeira etapa continua com o gestor atual do colaborador e a etapa RH normal vira `GESTOR_RH`.

Fluxo sem política adicional do cargo destino:

```text
1. aprovação hierárquica
   ↓ obrigatoriamente APROVADA
2. RH ou GESTOR_RH
   ↓
Gate apto
```

Fluxo quando `cargo_destino.aprovacao_adicional = GERENCIA|DIRETORIA`:

```text
1. aprovação hierárquica
   ↓
2. RH ou GESTOR_RH
   ↓
3. GERENCIA ou DIRETORIA
   → decidida pela liderança correspondente da cadeia hierárquica
   ↓
4. GESTOR_RH_ADICIONAL
   → decidida por RH_GESTOR
   ↓
Gate apto
```

`GERENCIA`/`DIRETORIA` e `GESTOR_RH_ADICIONAL` são duas anuências adicionais distintas e ambas são obrigatórias. `GESTOR_RH_ADICIONAL` é um discriminador técnico para não colidir com `GESTOR_RH` usado em substituições anteriores da mesma movimentação.

**Dedup de aprovador (RC-42).** A liderança de `GERENCIA`/`DIRETORIA` é resolvida subindo a cadeia de `gestor_id` a partir do gestor do colaborador — o mesmo ponto de partida da etapa hierárquica (`GESTOR_ORIGEM`/`GESTOR_SUPERIOR`). Quando o colaborador reporta diretamente à liderança exigida (ex.: `GESTOR_ORIGEM` e `GERENCIA` resolvem para a mesma pessoa), a decisão real dessa pessoa em uma das duas etapas satisfaz a outra automaticamente — RC-42 se aplica aqui como no restante do fluxo de aprovações (não é uma regra exclusiva de promoção).

A liderança correspondente é a pessoa mais próxima na cadeia de `gestor_id` cujo `cargo.papel_lideranca` corresponda ao tipo exigido. Não parsear `Cargo.nome`. Se a política adicional exigir um papel que não possa ser resolvido para uma pessoa concreta, a criação/ativação do workflow deve falhar de forma explícita e sem persistência parcial (`409 APROVADOR_HIERARQUICO_NAO_RESOLVIDO`).

Uma etapa posterior não pode ser decidida nem aparecer em `GET /aprovacoes/pendentes` enquanto a anterior obrigatória não estiver aprovada.

Logo estes estados não podem ser produzidos pelas APIs do sistema:

```text
gestor = REPROVADA
RH     = APROVADA

RH = PENDENTE
GERENCIA = disponível na tela
```

### 5.5 Mudança de centro de custo

Base:

```text
GESTOR_DESTINO + RH
```

Se o responsável/gestor destino for o solicitante:

```text
RH
```

Se solicitante = `RH_ANALISTA`:

```text
GESTOR_DESTINO + GESTOR_RH
```

### 5.6 Troca de gestor

Base:

```text
GESTOR_ORIGEM + GESTOR_DESTINO + RH
```

Solicitante não aprova sua própria etapa.

Se solicitante = `RH_ANALISTA`:

```text
GESTOR_ORIGEM + GESTOR_DESTINO + GESTOR_RH
```

Integridade obrigatória:

```text
GESTOR_ORIGEM  → gestor atual real
GESTOR_DESTINO → novo gestor proposto
```

Nunca inverter os dois.

### 5.7 Alteração de estrutura

Base:

```text
GESTOR_ORIGEM + RH
```

Se gestor origem for solicitante:

```text
RH
```

Se solicitante = `RH_ANALISTA`:

```text
GESTOR_ORIGEM + GESTOR_RH
```

### 5.8 Perfil que pode decidir

- `RH_ANALISTA`: nunca decide aprovação;
- `LIDERANCA`: somente se for o aprovador esperado daquela etapa e nunca quando for o solicitante;
- `RH_GESTOR`: decide `RH`, `GESTOR_RH` e `GESTOR_RH_ADICIONAL`; não cria solicitações no MVP;
- `ADMIN`: override administrativo controlado; pode decidir qualquer aprovação, inclusive de solicitação criada pelo próprio `ADMIN`.

---

## 6. API de aprovações

### 6.1 Consulta de pendências

```http
GET /aprovacoes/pendentes
```

Retorna somente aprovações que o usuário autenticado pode decidir **neste instante**. Além de RBAC/BOLA, a consulta aplica a ordem: uma etapa `PENDENTE` só é retornada quando todas as etapas de ordem inferior já estão `APROVADA`.

Movimentações `BLOQUEADA` nunca retornam aprovações acionáveis, mesmo que existam linhas posteriores de `Aprovacao` tecnicamente `PENDENTE` no registro original do workflow.

### 6.2 Decisão

```http
POST /movimentacoes/{movimentacaoId}/aprovacoes/{tipo}/decidir
```

Payload:

```json
{
  "decisao": "APROVADA",
  "justificativa": "..."
}
```

ou:

```json
{
  "decisao": "REPROVADA",
  "justificativa": "..."
}
```

Backend deve:

1. autenticar;
2. localizar a movimentação dentro do escopo;
3. localizar a aprovação exigida;
4. confirmar que o ator pode decidir aquela aprovação;
5. confirmar a ordem do workflow, quando sequencial;
6. impedir dupla decisão;
7. persistir decisão;
8. persistir evento de histórico;
9. reavaliar o gate;
10. atualizar status;
11. se todas aprovadas, assegurar JobValidacao;
12. fazer **um único commit**.

Se a gravação do histórico falhar, a aprovação não pode permanecer alterada.

---

## 7. Auditoria e histórico

### 7.1 Solicitante

`Movimentacao` adiciona:

```text
solicitante_usuario_id FK Usuario
```

Detalhe exibe:

```json
"solicitante": {
  "id": 5,
  "username": "admin",
  "perfil": "ADMIN"
}
```

### 7.2 `HistoricoProcessamento`

Adicionar:

```text
ator_usuario_id nullable
solicitante_usuario_id nullable
```

Eventos de aprovação devem sempre existir quando `Aprovacao.estado != PENDENTE` e `data_decisao != null`.

Exemplo:

```text
APROVACAO_CONCLUIDA
Aprovação GESTOR_ORIGEM aprovada por Isabela Henriques.
```

### 7.3 `ValidacaoAuditoria`

Além de `origem_execucao`, registrar:

```text
solicitante_usuario_id
ator_usuario_id nullable
```

No automático, `ator_usuario_id` pode ser nulo/SISTEMA; o solicitante permanece rastreável.

### 7.4 Reparo do bug intermitente

É inválido existir:

```text
Aprovacao.estado = APROVADA/REPROVADA
Aprovacao.data_decisao != null
sem evento de aprovação correspondente
```

Toda API que decide aprovação usa um único `AprovacaoService`.

O seed também deve gerar histórico consistente com suas aprovações já decididas.

---

## 7.5 Snapshot histórico no detalhe

O detalhe da solicitação representa o que foi pedido no momento da criação. Para cada tipo, origem/destino são lidos das FKs da própria `Movimentacao`:

```text
TRANSFERENCIA          → departamento_origem / departamento_destino
PROMOCAO               → cargo_origem / cargo_destino
TROCA_GESTOR           → gestor_origem / gestor_destino
MUDANCA_CENTRO_CUSTO   → centro_custo_origem / centro_custo_destino
ALTERACAO_ESTRUTURA    → estrutura_origem / estrutura_destino
```

Após uma efetivação, o estado atual do `Colaborador` pode coincidir com o destino. Isso **não** autoriza substituir a origem do DTO pelo estado atual. Exemplo obrigatório: após `Júnior 3 → Pleno 1` efetivada, o detalhe continua mostrando origem `Júnior 3` e destino `Pleno 1`.

---

## 8. Listagem e `motivoResumo`

`GET /movimentacoes` adiciona:

```text
solicitante
motivoResumo
```

`motivoResumo` é calculado no backend a partir do estado real, última validação, aprovações e/ou último evento relevante. Não é string fixa por status e não é montado no Angular.

Exemplos válidos:

```text
APROVADA
→ MOVIMENTACAO_EFETIVADA

REPROVADA
→ Validação reprovada com 3 inconsistência(s).

AGUARDANDO_APROVACAO
→ Aguardando aprovação GESTOR_DESTINO.

AGUARDANDO_APROVACAO com mais de uma
→ Aguardando 2 aprovações: GESTOR_DESTINO, RH.

BLOQUEADA
→ Aprovação GESTOR_ORIGEM reprovada por Alice Uchoa.

PENDENTE
→ Processamento pendente.
```

Se houver um evento técnico relevante durante `PENDENTE`, o resumo pode refletir o estado atual de processamento de forma curta e sanitizada.

Não colocar stack trace, payload ou detalhe sensível na listagem.

### 8.1 Contrato visual da listagem E2E

Ordem mínima de colunas:

```text
ID
DATA DA SOLICITAÇÃO
...
MOTIVO
```

`ID` é a primeira coluna. A busca aceita `id`, matrícula e nome do colaborador.

Apenas a célula de `motivoResumo` pode usar quebra de linha e altura de linha maior. As demais células continuam centralizadas e `white-space: nowrap` (ou equivalente), sem quebra.

Exemplos de copy curta, sempre produzida pelo backend a partir do estado real:

```text
APROVADA   → Movimentação efetivada.
REPROVADA  → Validação encontrou 3 inconsistências.
AGUARDANDO → Aguardando aprovação: GESTOR_DESTINO.
BLOQUEADA  → Bloqueada: DIRETORIA reprovada por <nome>.
PENDENTE   → Aguardando processamento.
```

As frases são UX, não novas regras de negócio.

---

## 9. Domínio adicional

### 9.1 `Cargo`

Adicionar:

```text
familia_cargo
ordem_progressao
papel_lideranca = GERENCIA | DIRETORIA | null
custo_mensal_referencia
```

`familia_cargo` agrupa cargos pertencentes à mesma trilha de carreira.

`ordem_progressao` representa a posição sequencial daquele cargo dentro da família e é a fonte de verdade para impedir saltos. `nivel` representa o nível **dentro da senioridade** e reinicia quando a senioridade muda. Por isso o número exibido no nome do cargo (`Júnior 1`, `Pleno 1` etc.) **não pode ser comparado isoladamente**.

Exemplo obrigatório de uma família:

```text
Analista Júnior nível 1  → ordem_progressao 1
Analista Júnior nível 2  → ordem_progressao 2
Analista Júnior nível 3  → ordem_progressao 3
Analista Pleno nível 1   → ordem_progressao 4
Analista Pleno nível 2   → ordem_progressao 5
Analista Pleno nível 3   → ordem_progressao 6
Analista Sênior nível 1  → ordem_progressao 7
...
```

A mesma modelagem vale para outras famílias/cargos, sem exigir que todas usem os rótulos Júnior/Pleno/Sênior. O seed não deve criar uma família genérica ativa que encurte a trilha (por exemplo `Analista Júnior` ordem 1 → `Analista Pleno` ordem 2). Cargos ativos usados em promoção devem representar posições granulares reais da trilha.

`papel_lideranca` não define progressão; identifica a função hierárquica usada para resolver uma aprovação adicional de `GERENCIA`/`DIRETORIA` sem parsear `Cargo.nome`.

### 9.2 `CentroCusto`

Adicionar:

```text
orcamento_mensal
custo_comprometido
```

Saldo:

```text
saldo_disponivel = orcamento_mensal - custo_comprometido
```

### 9.3 Histórico da última promoção

O contexto de validação deve receber a data da última `PROMOCAO` com status `APROVADA` e efetivação concluída para o colaborador.

A regra usa **6 meses-calendário**, não simplesmente “qualquer número arbitrário de dias”.

---

## 10. Catálogo de regras — 37 executáveis

### 10.1 Gerais — G (4)

Mantêm-se:

```text
G01 colaborador existe
G02 colaborador ativo
G03 tipo válido
G04 sem movimentação conflitante aberta
```

### 10.2 Transferência — T (6)

Mantêm-se T01–T06, mas T06 passa a validar a matriz dinâmica desta revisão.

### 10.3 Promoção — P (9)

| Código | Regra | Falha quando |
|---|---|---|
| P01 | Cargo destino existe | destino inexistente |
| P02 | Cargo destino ativo | destino inativo |
| P03 | Próximo passo exato da trilha | `cargo_destino.ordem_progressao != cargo_atual.ordem_progressao + 1` |
| P04 | Aprovação hierárquica íntegra | etapa hierárquica exigida ausente/inválida |
| P05 | Aprovação RH/GESTOR_RH íntegra | etapa RH exigida ausente/inválida |
| P06 | Aprovações adicionais íntegras quando aplicáveis | com `cargo_destino.aprovacao_adicional != null`, falta/não é íntegra a etapa `GERENCIA`/`DIRETORIA` **ou** a etapa `GESTOR_RH_ADICIONAL` |
| P07 | Mesma família de cargo | `familia_cargo` destino != atual |
| P08 | Intervalo mínimo entre promoções | última promoção efetivada ocorreu há menos de 6 meses |
| P09 | Centro de custo suporta o aumento | aumento de custo > saldo disponível |

Mensagens devem explicar a causa sem expor dados sensíveis.

Pré-condições devem evitar cascatas redundantes. Exemplo: P03/P07/P09 não avaliam se cargo destino não existe.

### 10.4 Troca de gestor — TG (6)

Mantêm-se TG01–TG06.

TG06 deve validar a matriz dinâmica e a identidade correta:

```text
GESTOR_ORIGEM = gestor atual
GESTOR_DESTINO = novo gestor
```

TG05 continua sendo apenas ciclo hierárquico; não usar TG05 para mascarar erro de aprovador invertido.

### 10.5 Centro de custo — CC (6)

Mantêm-se CC01–CC06, com CC06 validando a nova matriz dinâmica.

### 10.6 Alteração de estrutura — AE (6)

Mantêm-se AE01–AE06. `AE05 = origem ≠ destino`.

### 10.7 Totalização

```text
Gerais                 4
Transferência          6
Promoção               9
Troca de gestor        6
Centro de custo        6
Alteração estrutura    6
TOTAL                  37
```

---

## 11. Validação e efetivação

A engine continua pura, sem I/O.

`ValidationContext` deve receber pré-carregado:

```text
solicitante
cargo atual/destino
familia_cargo
ordem_progressao atual/destino
data ultima promoção efetivada
centro de custo atual
orcamento/custo comprometido
aprovações exigidas
grafo hierárquico necessário
demais refs já existentes
```

### 11.1 Efetivação de promoção

Após engine sem inconsistências:

```text
delta = cargo_destino.custo_mensal_referencia - cargo_atual.custo_mensal_referencia
colaborador.cargo_id = cargo_destino_id
centro_custo.custo_comprometido += max(delta, 0)
```

Tudo na mesma transação de conclusão.

---

## 12. Segurança de aplicação

### 12.1 Senha

- nunca persistir senha em texto puro;
- usar hash de senha adaptativo;
- comparar senha recebida com hash;
- não cachear senha;
- não escrever senha em log;
- respostas de login inválido não revelam se username existe.

### 12.2 JWT

- Bearer;
- expiração 30 min;
- `JWT_SECRET` obrigatório via ambiente/configuração, sem fallback funcional hardcoded;
- validar assinatura, expiração e usuário ativo em rota protegida;
- Angular adiciona token por interceptor;
- token apenas em memória no MVP.

### 12.3 Brute force

Tabela/estado persistido:

```text
SecurityLockout
ip
failed_attempts
window_started_at
blocked_until
```

Regras:

```text
3 falhas em janela de 5 minutos
→ bloquear IP por 30 minutos
```

Durante bloqueio:

```http
429 Too Many Requests
Retry-After: <segundos>
```

Sucesso de login limpa contador aplicável.

CLI local obrigatória:

```bash
python -m app.security.reset_lockouts
```

O comando limpa apenas lockouts, não usuários/movimentações.

Apagar `portal_mobilidade.db` + seed também reinicia lockouts, mas não é o único mecanismo.

### 12.4 Rate limiting geral

MVP local, processo único:

```text
GET/consultas:
100 req/min por IP + identidade

POST de criação/aprovação/validação:
30 req/min por IP + identidade
```

Não confiar em `X-Forwarded-For` arbitrário no modo local. Usar IP efetivo da conexão; em produção, cabe ao proxy confiável fornecer a origem.

### 12.5 Hardening adicional

- Pydantic com enums, limites e `extra="forbid"` nos payloads sensíveis, incluindo `POST /validar`;
- ORM parametrizado;
- whitelist de ordenação;
- CORS restrito à origem local configurada;
- respostas 500 sem stack trace;
- logs sem senha/JWT;
- limite de tamanho para payloads de API de escrita aplicado aos bytes efetivamente recebidos (checagem de `Content-Length` pode existir só como fast-fail);
- headers de segurança adequados;
- autorização reexecutada em toda operação de escrita;
- nenhum segredo no frontend.

### 12.6 DDoS

O MVP não declara proteção contra ataque volumétrico de 1 milhão req/s.

Evolução arquitetural:

```text
Internet
→ Azure DDoS Protection / proteção de rede
→ Azure Front Door + WAF
→ Azure API Management (rate limit/quota)
→ FastAPI
```

O rate limiter local continua sendo segunda camada.

---

## 13. Performance e cache

Meta:

```text
p95 dos endpoints principais < 2 segundos com seed local
```

Ordem de otimização:

1. índices;
2. paginação server-side;
3. filtro BOLA aplicado na query;
4. payload resumido na listagem;
5. eager loading controlado;
6. eliminar N+1;
7. consultas específicas para `motivoResumo`;
8. processamento pesado fora do request quando aplicável;
9. medir;
10. somente então cachear referência estável.

Cache local opcional/permitido:

```text
cargos
departamentos
centros de custo
```

TTL curto e invalidação simples quando houver escrita nesses catálogos.

Não cachear:

```text
senhas
JWT
aprovações
status de movimentação
timeline
resultado BOLA por objeto
decisão de autorização
```

---

## 14. Frontend

### 14.1 Login

Nova rota/tela:

```text
/login
```

Campos:

```text
Usuário
Senha
Entrar
```

Credenciais de demo:

```text
admin / admin
analistaRh / analistaRh
```

Sem exibir senha em texto, sem persistir credencial.

Rotas protegidas usam `authGuard`; rotas com capacidade específica usam `scopeGuard` alimentado pelos scopes devolvidos por `/auth/login`/`/auth/me`. O Angular não mantém `SCOPES_POR_PERFIL` próprio. Chamadas usam interceptor Bearer.

### 14.2 Navegação

Após login, menu conforme scopes:

```text
Movimentações
Nova solicitação
Aprovações
```

`Aprovações` só aparece para perfil com `movimentacoes:approve`.

### 14.3 Nova solicitação

Tela com:

```text
Tipo
Colaborador
Destino específico do tipo
Enviar
```

Tipos disponíveis:

```text
Transferência
Promoção
Mudança de centro de custo
```

Opções de colaboradores respeitam o escopo devolvido pela API.

### 14.4 Aprovações

Tela lista somente aprovações que o usuário pode decidir.

Ação:

```text
Aprovar
Reprovar
Justificativa opcional no MVP. Nenhuma obrigatoriedade adicional deve ser criada sem requisito explícito.
```

O frontend não calcula a ordem nem quem deve aprovar.

### 14.5 Listagem

Adicionar coluna:

```text
Motivo
```

Renderizar `motivoResumo` recebido da API, com truncamento visual/ellipsis quando necessário e `title`/tooltip apenas com o mesmo texto sanitizado.

### 14.6 Detalhe

Adicionar:

```text
Solicitante
```

Manter aprovações, impedimentos, validação e histórico.

Nenhum texto narrativo/rodapé reintroduzido.


### 14.6 Header — item ativo

Nos links do header (`Movimentações`, `Nova solicitação`, `Aprovações`), aplicar ao item ativo:

```css
font-weight: 700;
font-size: 1.05rem;
color: var(--cor-primaria-escura);
```

Somente um item correspondente à tela de menu fica ativo por vez. Ao trocar de rota, o estilo anterior volta ao normal. Não alterar o título `Portal de Mobilidade Organizacional`.

### 14.7 Nova solicitação — busca de colaborador

O campo de colaborador deve permitir selecionar e digitar nome/matrícula. O conjunto de resultados vem do backend já respeitando BOLA. O Angular não amplia escopo localmente.

### 14.8 Aprovações — tabela E2E

A tela deixa de ser uma lista de cards difícil de localizar e passa a apresentar tabela com:

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

Abaixo/associado à linha permanecem:

```text
Justificativa opcional
Aprovar  (azul)
Reprovar (vermelho)
```

Busca:

```text
ID da movimentação
nome/matrícula do colaborador
```

Ordenação padrão:

```text
data_solicitacao DESC
```

Ordenáveis:

```text
ID
Data da Solicitação
Tipo
Solicitante
Colaborador
Setor
```

`Origem` e `Destino` são rótulos dinâmicos conforme o tipo, usando os snapshots da movimentação. Para `Setor`, reutilizar o campo/relacionamento já existente que representa o setor/departamento do colaborador; **não criar uma nova entidade ou regra apenas para preencher a coluna**. Se o código atual não possuir uma origem inequívoca para esse dado, parar e perguntar ao candidato.

---

## 15. Contratos de API novos/alterados

```http
POST /auth/login
GET  /auth/me

GET  /colaboradores
GET  /referencias/cargos
GET  /referencias/departamentos
GET  /referencias/centros-custo
GET  /referencias/gestores              (ou endpoint já existente equivalente)
GET  /referencias/estruturas            (ou endpoint já existente equivalente)

GET  /movimentacoes
POST /movimentacoes
GET  /movimentacoes/{id}

GET  /aprovacoes/pendentes
POST /movimentacoes/{id}/aprovacoes/{tipo}/decidir

POST /validar
```

Todas as rotas, exceto login e documentação explicitamente permitida, exigem autenticação.

---

## 16. Cenários obrigatórios

### 16.1 Auth/RBAC/BOLA

```text
AUTH-01 admin/admin autentica e recebe JWT ADMIN
AUTH-02 analistaRh/analistaRh autentica e recebe JWT RH_ANALISTA
AUTH-03 senha errada não autentica
AUTH-04 terceira falha na janela bloqueia IP por 30 min
AUTH-05 IP bloqueado recebe 429
AUTH-06 reset_lockouts remove bloqueio
AUTH-07 token expirado/inválido recebe 401
AUTH-08 rota protegida sem token recebe 401
AUTH-09 RH_ANALISTA lê tudo e cria, mas aprovação retorna 403
AUTH-10 liderança não recebe objeto fora da subárvore na listagem
AUTH-11 ID direto fora da subárvore retorna 404
```

### 16.2 Criação

```text
REQ-01 liderança cria transferência para subordinado da subárvore
REQ-02 liderança não cria para objeto fora do escopo
REQ-03 RH_ANALISTA cria para qualquer colaborador
REQ-04 backend deriva origem e solicitante; payload não os controla
REQ-05 criação persiste SOLICITACAO_RECEBIDA
```

### 16.3 Aprovações

```text
APR-01 perfil comum nunca autoaprova
APR-02 ADMIN pode aprovar a própria solicitação
APR-03 transferência solicitada por gestor origem exige destino + RH
APR-04 transferência solicitada por gestor destino exige origem + RH
APR-05 RH_ANALISTA solicitante substitui RH por GESTOR_RH
APR-06 promoção não permite RH antes da aprovação hierárquica
APR-07 gestor solicitante de promoção é substituído pelo superior
APR-08 solicitante topo sem superior usa RH_GESTOR e não exige outra etapa RH
APR-09 decisão de aprovação + histórico + gate + job são atômicos
APR-10 aprovação já decidida não pode ser decidida de novo
APR-11 seed nunca possui aprovação decidida sem evento correspondente
APR-12 /aprovacoes/pendentes não devolve RH antes da etapa hierárquica aprovada
APR-13 com adicional GERENCIA: liderança de GERENCIA aprova antes de GESTOR_RH_ADICIONAL
APR-14 com adicional DIRETORIA: liderança de DIRETORIA aprova antes de GESTOR_RH_ADICIONAL
APR-15 GESTOR_RH_ADICIONAL é obrigatório quando há adicional, mesmo se outra etapa GESTOR_RH já existiu
APR-16 liderança GERENCIA/DIRETORIA é resolvida por papel_lideranca, não por nome livre
APR-17 política do seed é a mesma ApprovalPolicy, sem mapa paralelo
APR-18 mesma pessoa resolvida em duas exigências de pessoa específica: uma decisão satisfaz as duas, auditoria preserva os dois registros (RC-42)
APR-19 etapas por perfil (RH/GESTOR_RH/GESTOR_RH_ADICIONAL) nunca deduplicam por coincidência de ator
```

### 16.4 Promoção

```text
PRO-01 Analista Júnior 1 → Analista Júnior 2 pode passar pelas regras de cargo
PRO-02 Analista Júnior 1 → Analista Júnior 3 reprova P03
PRO-03 Analista Júnior 3 → Analista Pleno 1 pode passar P03 porque são posições consecutivas da trilha
PRO-04 Analista Júnior 3 → Analista Pleno 2 reprova P03 por pular uma posição
PRO-05 cargo atual → mesmo cargo reprova P03
PRO-06 família OPERACOES → TECNOLOGIA reprova P07
PRO-07 promoção efetivada há < 6 meses reprova P08
PRO-08 promoção efetivada há >= 6 meses não reprova P08
PRO-09 saldo do CC insuficiente reprova P09
PRO-10 saldo suficiente não reprova P09
PRO-11 efetivação atualiza cargo e custo comprometido atomicamente
PRO-12 seed/referências não permitem atalho genérico Analista Júnior → Analista Pleno como passo único
PRO-13 `nivel` reinicia por senioridade e `ordem_progressao` permanece sequencial
```

### 16.5 Troca de gestor

```text
TG-APR-01 Wesley atual / Larissa destino:
GESTOR_ORIGEM esperado = Wesley
GESTOR_DESTINO esperado = Larissa

TG-APR-02 inversão falha integridade/TG06
TG-APR-03 TG05 continua cobrindo ciclo hierárquico, não identidade do aprovador
```

### 16.6 Listagem/motivo

```text
MOT-01 APROVADA usa resumo do evento/estado de efetivação
MOT-02 REPROVADA resume quantidade real de inconsistências
MOT-03 AGUARDANDO lista aprovação(ões) realmente pendente(s)
MOT-04 BLOQUEADA identifica aprovação e ator real
MOT-05 PENDENTE não é confundida com AGUARDANDO_APROVACAO
```

### 16.7 Snapshot e hardening corretivo

```text
SNAP-01 promoção efetivada preserva cargo origem/destino no detalhe
SNAP-02 os cinco tipos usam snapshot da Movimentacao, não estado atual do Colaborador
SEC-01 startup/runtime sem JWT_SECRET configurado falha de forma explícita/segura
SEC-02 /validar autenticado com campo extra retorna exatamente 422
SEC-03 body acima do limite é rejeitado mesmo sem Content-Length confiável
SEC-04 scopes do frontend vêm do backend e /aprovacoes exige movimentacoes:approve no scopeGuard
```

### 16.9 Revisão E2E — T-83+

```text
E2E-01 header move o destaque ativo entre Movimentações/Nova solicitação/Aprovações
E2E-02 listagem exibe ID como primeira coluna
E2E-03 busca de movimentações encontra por ID, matrícula e nome
E2E-04 motivo curto pode quebrar linha sem quebrar colunas anteriores
E2E-05 reprovação de qualquer etapa torna movimentação BLOQUEADA terminal
E2E-06 detalhe de BLOQUEADA mostra a aprovação reprovada como causa final, nunca "aguardando" etapa posterior
E2E-07 BLOQUEADA não aparece em /aprovacoes/pendentes
E2E-08 UI/API criam TROCA_GESTOR
E2E-09 UI/API criam ALTERACAO_ESTRUTURA
E2E-10 colaborador pode ser localizado por digitação de nome/matrícula
E2E-11 catálogo de referências mantém comportamento atual; inativação posterior é detectada pela engine
E2E-12 aprovações suportam busca por colaborador e ID
E2E-13 aprovações ordenam por whitelist e padrão data DESC
E2E-14 tabela de aprovações exibe ID/data/tipo/solicitante/colaborador/origem/destino/setor
E2E-15 justificativa permanece opcional e botões mantêm ações/cores esperadas
E2E-16 os seis logins de demonstração autenticam com seus perfis/vínculos esperados
E2E-17 ADMIN continua coringa fora de qualquer departamento/subárvore
```

### 16.8 Regressões existentes

Continuam obrigatórias:

- manual × Worker não duplica;
- stale recovery;
- cinco status;
- AE05;
- TG05;
- histórico real;
- efetivação local;
- erro técnico não vira reprovação;
- paginação determinística.

---

## 17. Seed

O seed continua fictício, determinístico e idempotente.

Além dos cenários existentes, criar:

- usuário `admin` com hash da senha `admin`;
- usuário `analistaRh` com hash da senha `analistaRh`;
- usuário `gestorRh` com hash da senha `gestorRh` e perfil `RH_GESTOR`;
- usuários `coordenador`, `gerente` e `diretor` com senha igual ao login e perfil técnico `LIDERANCA`, vinculados a uma cadeia hierárquica coerente;
- famílias de cargo coerentes;
- cargos ativos granulares: `nivel` reinicia por senioridade e `ordem_progressao` é sequencial; nenhuma trilha genérica encurta Júnior→Pleno;
- `custo_mensal_referencia`;
- centros de custo com orçamento/saldo suficiente e insuficiente;
- histórico de promoção recente e antiga;
- cenários de matriz de aprovação, incluindo GERENCIA/DIRETORIA + GESTOR_RH_ADICIONAL e `papel_lideranca`;
- histórico de todas as aprovações já decididas;
- solicitante em todas as movimentações.

Rodar o seed duas vezes não duplica usuários, movimentações, aprovações, jobs nem histórico.

---

## 18. Fora de escopo

- cadastro/edição de usuários pela UI;
- Microsoft Entra ID/Keycloak em runtime;
- refresh token;
- recuperação de senha;
- MFA;
- `MUDANCA_CARREIRA`;
- WAF/DDoS Protection/API Management em runtime local;
- broker externo;
- teste de DDoS real;
- Redis;
- autenticação corporativa real.

---

## 19. Critérios de aceite finais

A entrega só é considerada concluída quando:

1. login funciona com `admin/admin` e `analistaRh/analistaRh`, com ambas as senhas hashadas;
2. RBAC e BOLA são aplicados no backend;
3. liderança não recebe objetos fora da subárvore;
4. RH_ANALISTA cria e consulta, mas não aprova;
5. criação de transferência/promoção/CC funciona;
6. solicitante aparece no detalhe e auditoria;
7. aprovação via UI/API funciona com matriz dinâmica;
8. aprovação e histórico são atomicamente consistentes;
9. promoção aplica P03/P07/P08/P09 corretamente;
10. troca de gestor não inverte aprovadores;
11. `motivoResumo` vem da API;
12. brute-force lockout e reset CLI funcionam;
13. rate limiting local retorna 429;
14. testes de segurança/negócio/regressão passam;
15. endpoints relevantes permanecem <2s com seed;
16. cache, se usado, fica restrito a dados de referência;
17. documentação explica que DDoS volumétrico é tratado antes da aplicação em produção;
18. nenhuma regressão de T-47–T-56 é introduzida;
19. detalhe pós-efetivação preserva os snapshots de origem/destino;
20. `GET /aprovacoes/pendentes` expõe somente etapas acionáveis na ordem corrente;
21. política adicional exige liderança correspondente + `GESTOR_RH_ADICIONAL`;
22. seed/referências não permitem promoção genérica Júnior→Pleno em um salto;
23. `JWT_SECRET` não possui fallback hardcoded;
24. scopes de UX vêm do backend e `/aprovacoes` usa `scopeGuard`;
25. `/validar` rejeita campo extra com 422 autenticado e body limit independe de `Content-Length`;
26. não existe mapa paralelo de aprovações no seed;
27. quando duas exigências de pessoa específica resolvem para o mesmo colaborador, uma decisão real satisfaz as duas sem exigir segundo clique, preservando os dois registros na auditoria (RC-42); etapas por perfil nunca deduplicam por coincidência de ator.
28. os cinco tipos podem ser criados pela UI/API;
29. `BLOQUEADA` é terminal e o detalhe não anuncia aprovação futura pendente;
30. a listagem exibe ID, busca também por ID e apresenta motivo curto;
31. o header evidencia corretamente a rota ativa;
32. a tela Aprovações oferece busca, ordenação e tabela conforme RC-51;
33. os seis usuários de demonstração autenticam e exercem somente suas capacidades, exceto `ADMIN`, que mantém override master;
34. a busca de colaborador na Nova solicitação aceita digitação de nome/matrícula respeitando BOLA;
35. nenhum comportamento de catálogo ativo/inativo é alterado por esta revisão; inativação posterior continua sendo responsabilidade das regras já existentes.
