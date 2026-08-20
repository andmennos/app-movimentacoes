# DECISIONS.md — Decisões técnicas e trade-offs

Este documento resume as decisões mais importantes da solução. O histórico detalhado continua disponível em [`docs/decisoes/`](docs/decisoes/).

## 1. Monólito modular no MVP

**Decisão:** Angular + FastAPI + SQLite, organizados em módulos claros, sem microsserviços em runtime local.

**Por quê:** o volume do case não justifica custo operacional distribuído e o domínio é coeso.

**Alternativas avaliadas:** microsserviços por tipo de movimentação, Kubernetes, brokers externos.

**Trade-off:** menor escalabilidade horizontal imediata em troca de simplicidade, velocidade de entrega e consistência transacional.

**Evolução:** manter o domínio e substituir infraestrutura por RDS/SQS/ECS quando houver necessidade real.

---

## 2. Engine de validação pura e determinística

**Decisão:** as 37 regras ficam em `validation/`, sem I/O, ORM ou framework.

**Por quê:** regras de negócio precisam ser testáveis e previsíveis.

**Alternativas:** regras acopladas aos services/repositories; rule engine/DSL configurável.

**Trade-off:** alterações de regra exigem código/deploy, mas permanecem versionáveis, revisáveis e cobertas por teste.

**Evolução:** versionar formalmente regras/contexto se auditoria histórica exigir reprodução exata.

---

## 3. Processamento assíncrono como fluxo principal

**Decisão:** aprovação concluída gera `JobValidacao`; Worker processa pelo mesmo `ProcessingOrchestrator` usado pelo fallback manual.

**Por quê:** desacopla interação do usuário do processamento e evita duas implementações da mesma regra.

**Alternativas:** validar apenas por botão; executar toda validação dentro da decisão de aprovação.

**Trade-off:** adiciona estado de fila e necessidade de Worker.

**Evolução:** `JobValidacao` → Amazon SQS; Worker → consumers ECS/Fargate.

---

## 4. Cinco estados de negócio

```text
AGUARDANDO_APROVACAO
BLOQUEADA
PENDENTE
APROVADA
REPROVADA
```

**Decisão:** aprovação reprovada e validação reprovada são conceitos diferentes.

```text
BLOQUEADA
= workflow humano encerrado por reprovação

REPROVADA
= engine executou e encontrou inconsistências
```

**Trade-off:** mais estados, porém sem ambiguidade na UI, auditoria e operação.

---

## 5. Movimentação inválida nunca é efetivada

**Decisão:** gate impede engine antes das aprovações; engine impede efetivação quando há inconsistências.

**Por quê:** aprovação e validade são barreiras independentes.

**Garantia técnica:** efetivação e conclusão da auditoria ocorrem transacionalmente. Falha técnica gera rollback e não é convertida em resultado de negócio falso.

---

## 6. Política de aprovação centralizada

**Decisão:** uma única `ApprovalPolicy/exigencias_para(...)` resolve tipos, ator/perfil e ordem.

**Por quê:** impedir mapas divergentes entre criação, gate, seed e engine.

**Alternativa:** matriz estática duplicada por camada.

**Trade-off:** policy central fica mais rica, mas reduz inconsistência sistêmica.

### Autoaprovação

Regra geral: solicitante não aprova a própria solicitação.

Exceção controlada: `ADMIN` é o usuário coringa de demonstração e pode decidir qualquer etapa, inclusive a própria solicitação.

### Etapas adicionais de promoção

Quando necessário:

```text
hierarquia
→ RH/GESTOR_RH
→ GERENCIA ou DIRETORIA
→ GESTOR_RH_ADICIONAL
```

`GERENCIA`/`DIRETORIA` resolvem uma pessoa concreta da hierarquia por `Cargo.papel_lideranca`.

Quando dois requisitos de pessoa específica convergem para o mesmo colaborador, uma única ação real pode satisfazer ambos, preservando dois registros auditáveis.

---

## 7. RBAC + BOLA no backend

**Decisão:** autorização funcional por perfil e autorização por objeto em toda rota sensível.

`LIDERANCA` enxerga somente sua subárvore. Objeto fora do escopo retorna `404`, evitando revelar existência.

**Alternativa:** esconder somente no Angular.

**Trade-off:** consultas precisam incorporar o escopo antes da paginação, mas segurança não depende da UI.

---

## 8. Autenticação local JWT para demonstração

**Decisão:** JWT Bearer, hash Argon2id, token em memória, segredo obrigatório por ambiente.

**Por quê:** permite demonstrar autenticação/RBAC localmente sem depender de infraestrutura corporativa.

**Alternativas:** Keycloak/Entra/Cognito no runtime do MVP.

**Trade-off:** login local não é solução corporativa de produção.

**Evolução:** federação com IdP corporativo, mantendo RBAC/BOLA da aplicação.

---

## 9. Auditoria append-only

**Decisão:** validações e inconsistências são preservadas em tabelas próprias; workflow usa `HistoricoProcessamento`.

**Por quê:** investigação não pode depender de estado atual nem apenas de logs.

**Trade-off:** crescimento de armazenamento, aceitável para rastreabilidade.

**Risco conhecido:** o `ValidationContext` histórico completo não é versionado; reproduzir exatamente uma validação antiga depende dos dados referenciados ainda estarem disponíveis/coerentes.

---

## 10. SQLite no MVP, PostgreSQL na evolução

**Decisão:** SQLite/WAL no ambiente local.

**Por quê:** zero infraestrutura externa, seed reproduzível e execução simples para a banca.

**Trade-off:** escritor/concurrency limitados e Worker único.

**Evolução:** RDS PostgreSQL Multi-AZ quando existirem múltiplas instâncias/escritores.

---

## 11. Segurança em camadas

Implementado no MVP:

- senha com Argon2id;
- `JWT_SECRET` fora do código;
- RBAC;
- BOLA;
- lockout de força bruta;
- rate limiting local;
- body-size limit;
- `extra=forbid`;
- CORS restrito;
- headers de segurança;
- logs sem senha/JWT.

**Trade-off:** rate limiter é local ao processo e não é proteção volumétrica.

**Evolução:** WAF/Shield/API Gateway + gestão centralizada de segredos e identidade.

---

## 12. Performance: medir antes de cachear

**Decisão:** otimizar consulta, paginação e N+1 antes de introduzir cache.

Benchmark final:

```text
GET /movimentacoes       p95 = 19,2 ms
GET /movimentacoes/{id}  p95 = 10,6 ms
```

Cache é permitido apenas para referências estáveis. Aprovação, status, timeline e decisões BOLA não são cacheadas.

---

## 13. Testes e E2E como parte do desenho

**Decisão:** testes automatizados + smoke real fazem parte do critério de fechamento.

Resultado final:

```text
448 backend
92 frontend
build verde
seed/Worker verificados
```

A revisão E2E encontrou problemas que a suíte automatizada anterior não detectava; os casos corrigidos viraram regressões automatizadas.

---

## 14. Riscos conhecidos

| Risco | Situação | Evolução/Mitigação |
|---|---|---|
| SQLite / Writer único | Aceito no MVP | RDS PostgreSQL |
| Worker único | Aceito no MVP | SQS + consumers escaláveis |
| Rate limiter local | Não distribuído | API Gateway/WAF |
| Login local | Apenas demonstração | IdP corporativo |
| Sem observabilidade gerenciada | Logs/auditoria locais | CloudWatch + OpenTelemetry |
| Contexto histórico não versionado integralmente | Reprodução antiga limitada | Snapshot/versionamento de contexto |
| Sem Docker/CI/CD | Não implementados no case | Containerização e pipeline como próxima evolução |

---

## 15. Evoluções futuras recomendadas

Ordem sugerida:

```text
1. Containerização
2. RDS PostgreSQL
3. SQS + DLQ
4. ECS/Fargate auto scaling
5. Transactional Outbox + EventBridge
6. CloudWatch + OpenTelemetry
7. IdP corporativo/federação
8. CI/CD + IaC
9. Serviços de integração e analytics
```

Microsserviços devem ser extraídos por necessidade de escala/ownership, não por tipo de movimentação.
