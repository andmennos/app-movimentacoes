# Prompt — Ajuste do Portal de Mobilidade para processamento automático

Você está trabalhando em uma aplicação **já funcional** do case “Portal de Mobilidade Organizacional”. Não reimplemente o projeto do zero. Leia primeiro `spec.md`, `plan.md` e `tasks.md` revisados e trate esses três arquivos como fonte de verdade.

## Correção de objetivo

A implementação atual se desviou do objetivo de negócio ao colocar um botão **Validar** no frontend.

O frontend exigido pelo case deve funcionar como **consulta/relatório do processamento**, com:
- listagem de movimentações;
- busca por colaborador;
- filtro por status;
- ordenação;
- paginação;
- detalhe;
- aprovações;
- última validação;
- inconsistências encontradas.

O Angular **não deve disparar validação manual**.

A validação deve ser iniciada automaticamente no backend quando uma movimentação estiver apta após as aprovações.

## Fluxo normal obrigatório

Implemente o fluxo:

```text
Solicitação de movimentação
        ↓
Movimentação + aprovações
        ↓
Gate de aprovação
   ├─ aprovação PENDENTE
   │      → Movimentacao=PENDENTE
   │      → não criar job
   │      → não executar engine
   │
   ├─ aprovação REPROVADA
   │      → Movimentacao=REPROVADA
   │      → não criar job
   │      → não executar validação automática
   │
   └─ todas as aprovações exigidas APROVADA
          ↓
      Producer local
          ↓
      JobValidacao
          ↓
      Worker Python
          ↓
      ValidacaoService
          ↓
      ValidationEngine
          ↓
      todas as inconsistências
          ↓
      auditoria append-only
          ↓
      APROVADA ou REPROVADA
```

Somente `APROVADA` fica apta a seguir para processamento posterior. A efetivação em sistemas corporativos continua fora do MVP.

## Decisões que NÃO devem ser reabertas

1. Manter exatamente as **34 regras executáveis** existentes.
2. Não adicionar, remover ou renumerar regras.
3. `AE05` continua sendo `origem != destino`.
4. Ciclo hierárquico continua exclusivamente em `TG05`.
5. Não mover regra de negócio para Angular.
6. Regras continuam puras e sem I/O.
7. Auditoria continua append-only.
8. Apenas a última validação é exposta no detalhe.
9. Manter FastAPI + Angular + SQLite.
10. Não adicionar RabbitMQ, Kafka, Redis, Celery, Docker obrigatório, Kubernetes ou AWS em runtime.

## Fila local

Criar uma fila persistente simples no SQLite por meio de `JobValidacao`.

Campos mínimos:
- `id`
- `movimentacao_id`
- `status`: `PENDENTE | PROCESSANDO | CONCLUIDO | ERRO`
- `tentativas`
- `criado_em`
- `iniciado_em`
- `finalizado_em`
- `ultimo_erro`

No fluxo automático do MVP, o producer deve ser idempotente: reexecutá-lo não pode criar job duplicado para a mesma movimentação.

Não transforme `Movimentacao.status` em status técnico de job. São conceitos diferentes.

## Producer / gate

Criar uma camada de processamento, por exemplo:

```text
app/processing/
  approval_gate.py
  producer.py
  worker.py
```

O producer deve reutilizar a **mesma fonte de verdade** que já define as aprovações exigidas por tipo. Não crie um segundo mapa de aprovações.

Comportamento:
- qualquer aprovação exigida `PENDENTE` → não agenda;
- qualquer aprovação exigida `REPROVADA` → bloqueia a movimentação como `REPROVADA`, sem job;
- todas exigidas `APROVADA` → cria `JobValidacao=PENDENTE`;
- casos anômalos de integridade continuam cobertos pelas regras já existentes e pelos testes.

## Worker

Criar um processo Python independente, executável por comando semelhante a:

```bash
python -m app.processing.worker
```

Use o comando que fizer sentido para a estrutura real do projeto e documente-o no README.

O Worker deve:
1. buscar job pendente;
2. marcar `PROCESSANDO`;
3. incrementar tentativa;
4. chamar **o mesmo `ValidacaoService` já utilizado pelo endpoint `POST /validar`**;
5. nunca copiar/reimplementar as 34 regras;
6. em sucesso, marcar `CONCLUIDO`;
7. em falha técnica, garantir rollback da movimentação/auditoria e registrar tentativa/erro no job;
8. operar com um único consumer no MVP.

## `POST /validar`

**Não remova o endpoint.**

O case pede explicitamente `POST /validar`. Ele deve permanecer:
- disponível no Swagger;
- coberto por testes;
- como adaptador síncrono técnico para o mesmo caso de uso de validação.

Porém:
- o Angular não deve chamá-lo;
- ele não é o gatilho normal do produto.

Preserve o contrato existente sempre que possível.

## Seed

O seed deve passar a representar **solicitações fictícias recebidas**, não movimentações validadas manualmente no portal.

Deve criar:
- os cinco tipos de movimentação;
- aprovações `PENDENTE`;
- aprovações `APROVADA`;
- aprovações `REPROVADA`;
- casos válidos;
- defeito único;
- múltiplas inconsistências;
- pelo menos 100 movimentações;
- todos os cenários já necessários às 34 regras.

Ao final do seed, execute o producer:
- pendentes ficam sem job;
- rejeitadas ficam bloqueadas;
- aprovadas recebem um job.

Seed + producer devem continuar idempotentes.

## Frontend

Remover:
- botão Validar;
- loading/error específicos do comando de validação;
- chamada Angular a `POST /validar`;
- testes que esperam clique em validar.

Manter/melhorar:
- listagem;
- busca;
- filtros;
- ordenação;
- paginação;
- detalhe;
- aprovações;
- status;
- última validação;
- inconsistências;
- estados de aguardando aprovação/processamento.

O frontend deve deixar evidente que está mostrando o **resultado de um processamento de backend**.

## Performance

Preservar:
- respostas HTTP < 2 segundos;
- suporte ao requisito de até 5.000 movimentações/dia;
- paginação e índices;
- carga única do `ValidationContext`.

Não usar a afirmação “1,7 req/s no pico” sem hipótese documentada. 5.000/dia representam aproximadamente 0,058 movimentação/s na média.

A fila local deve ser tratada como desacoplamento e amortecimento de rajadas, não como justificativa para arquitetura distribuída prematura.

## Evolução arquitetural

Atualize a documentação para mostrar a substituição futura:

```text
MVP
Producer → JobValidacao/SQLite → Worker Python

Futuro
Sistemas → API/Integração → EventBridge/SQS → Consumers → RDS/PostgreSQL
```

Considere:
- SQS como evolução natural da fila;
- ECS/Fargate ou Lambda para consumers conforme perfil de execução;
- CloudWatch para logs/métricas/alertas;
- DLQ/retry gerenciados;
- PostgreSQL/RDS quando houver múltiplos escritores;
- eventos/outbox se outros sistemas precisarem reagir ao resultado.

Não implemente AWS agora.

## Testes obrigatórios da revisão

Além dos testes atuais, cobrir:
- todas aprovações aprovadas → job criado;
- aprovação pendente → sem job e sem engine;
- aprovação rejeitada → sem job;
- producer idempotente;
- Worker processa job válido → APROVADA + auditoria;
- Worker processa job inválido → REPROVADA + todas inconsistências + auditoria;
- falha técnica → sem auditoria/status parcial;
- frontend não chama `POST /validar`;
- `POST /validar` continua funcional no Swagger/API;
- suíte atual das 34 regras continua verde.

## Execução

Siga as tarefas revisadas. Faça alterações incrementais sobre o código existente.

Antes de concluir:
1. instalar apenas dependências realmente necessárias — preferencialmente nenhuma nova;
2. recriar/atualizar banco local;
3. rodar seed;
4. iniciar Worker;
5. validar que os jobs são consumidos automaticamente;
6. rodar testes backend;
7. rodar testes frontend;
8. rodar build Angular;
9. testar os 3 endpoints;
10. verificar resposta <2s;
11. revisar README, DECISIONS, architecture, operations e IA_REPORT;
12. executar V-01 a V-20.

## Relatório final

Ao terminar, informe:
- arquivos alterados;
- tarefas concluídas;
- comando do seed;
- comando do Worker;
- total de testes backend/frontend;
- resultado do build;
- demonstração dos estados PENDENTE/APROVADA/REPROVADA;
- confirmação de que Angular não chama `POST /validar`;
- confirmação de que as 34 regras não foram alteradas;
- limitações e riscos residuais.

Não declare DONE enquanto houver falha de teste, build, seed, Worker ou divergência com `spec.md`.
