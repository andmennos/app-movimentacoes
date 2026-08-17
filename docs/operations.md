# Operação e sustentação — Portal de Mobilidade Organizacional

Este documento descreve como operar e investigar o sistema. No MVP local, nada aqui depende de infraestrutura externa (RC-11) — os logs são os do próprio `uvicorn`/console, e a auditoria já persistida no banco é a principal fonte de evidência para investigação. Para o cenário de produção evoluído, ver `docs/architecture.md` §2.1 (observabilidade dedicada).

## 1. Métricas relevantes

Nenhuma delas é coletada automaticamente no MVP (sem componente de observabilidade — RC-11); esta seção define **o que** medir e **de onde** extrair, tanto manualmente hoje quanto como especificação para um coletor futuro (ex.: um exportador Prometheus sobre estas mesmas consultas).

| Métrica | Como obter hoje | Por que importa |
|---|---|---|
| Distribuição de resultados de validação | `SELECT resultado, COUNT(*) FROM validacao_auditoria GROUP BY resultado` | Sinaliza se a taxa de reprovação está subindo (dado ruim entrando no sistema) ou se aprovações estão represadas |
| Tempo de resposta dos 3 endpoints | Log de acesso do `uvicorn` (latência por requisição) | RNF-01 exige < 2s; regressão de performance aparece aqui primeiro |
| Volume de validações por período | `SELECT date(data_hora), COUNT(*) FROM validacao_auditoria GROUP BY 1` | Capacidade — compara com o volume projetado (~5.000/dia, `spec.md` RNF-02) |
| Códigos de inconsistência mais frequentes | `SELECT codigo_regra, COUNT(*) FROM inconsistencia_auditoria GROUP BY 1 ORDER BY 2 DESC` | Aponta qual regra está pegando mais dado ruim — útil para priorizar correção de dado na origem, não do motor |
| Revalidações por movimentação | `SELECT movimentacao_id, COUNT(*) FROM validacao_auditoria GROUP BY 1 HAVING COUNT(*) > 3` | Movimentação revalidada muitas vezes sem sair de `REPROVADA`/`AGUARDANDO_APROVACAO` pode indicar dado cadastral quebrado, não corrigível pelo fluxo normal |
| Taxa de erro 500 | Log de acesso do `uvicorn`, contagem de respostas 5xx | Único caminho onde uma exceção de código chega ao usuário (ADR-0007) — qualquer ocorrência é bug, não variação esperada |

### 1.1 Métricas da fila e do Worker

O gatilho normal do produto é automático (producer + `JobValidacao` + Worker — ADR-0009). Estas métricas cobrem esse caminho, que não existe em `POST /validar`.

| Métrica | Como obter hoje | Por que importa |
|---|---|---|
| Tamanho da fila (backlog) | `SELECT COUNT(*) FROM job_validacao WHERE status = 'PENDENTE'` | Cresce se o Worker parar ou não acompanhar o ritmo de agendamento |
| Idade do job pendente mais antigo | `SELECT MIN(criado_em) FROM job_validacao WHERE status = 'PENDENTE'` | Indica há quanto tempo uma movimentação apta está esperando ser processada |
| Jobs processados por período | `SELECT date(finalizado_em), COUNT(*) FROM job_validacao WHERE status = 'CONCLUIDO' GROUP BY 1` | Throughput real do Worker — compara com o volume agendado pelo producer |
| Jobs em erro terminal | `SELECT COUNT(*) FROM job_validacao WHERE status = 'ERRO'` | Cada um esgotou `LIMITE_TENTATIVAS` (`app/processing/worker.py`) — exige investigação manual, não se autorresolve |
| Tentativas médias por job concluído | `SELECT AVG(tentativas) FROM job_validacao WHERE status = 'CONCLUIDO'` | Próximo de 1 é saudável; subindo, indica falhas técnicas intermitentes |
| Tempo típico de consumo de um job | `finalizado_em - iniciado_em` por job `CONCLUIDO` | Ver medição de referência em `README.md` §"Desempenho" — no MVP, da ordem de milissegundos por job (mesma engine de `POST /validar`, sem I/O extra) |

## 2. Logs necessários

O MVP roda com o log padrão do `uvicorn` (acesso + erros de aplicação no stdout). Para operação real, os seguintes eventos merecem log estruturado (nível e campos sugeridos):

| Evento | Nível | Campos |
|---|---|---|
| `POST /validar` concluído | INFO | `movimentacaoId`, `resultado`, `totalInconsistencias`, `duracaoMs` |
| Exceção não tratada durante validação | ERROR | `movimentacaoId`, tipo da exceção, stack trace |
| `OrdenacaoInvalida` / `PayloadInvalido` (400/422) | WARNING | rota, parâmetro/campo inválido |
| Início/fim do seed | INFO | quantidade de entidades criadas por tabela |
| Job consumido com sucesso | INFO | `job_id`, `movimentacao_id` (já emitido por `app/processing/worker.py::processar_um_job`) |
| Job com falha técnica | ERROR | `job_id`, `movimentacao_id`, `tentativas`, `erro` (mensagem técnica truncada, sem dado sensível — já emitido pelo Worker) |
| Producer executado | INFO | quantidade agendada / bloqueada / aguardando / anômala (já emitido por `app/seed/seed.py` ao final do seed; o mesmo padrão vale para uma execução standalone do producer) |

No MVP, o traceback completo de uma exceção 500 aparece no console do `uvicorn` (não é suprimido pelo handler de erro — o handler só controla a **resposta HTTP**, nunca o log do processo). O Worker usa o logger `app.processing.worker`, com `job_id` e `movimentacao_id` em toda linha relevante — suficiente para correlacionar um job específico ao seu resultado sem precisar consultar o banco primeiro.

## 3. Alertas desejados (produção)

Nenhum alerta está configurado no MVP (sem componente de alerting — RC-11). Especificação para quando houver observabilidade dedicada:

| Alerta | Condição | Severidade |
|---|---|---|
| Taxa de 500 acima do normal | > 0 respostas 500 em uma janela de 5 min (deveria ser sempre zero) | Crítica — indica bug em produção |
| Latência acima do SLA | p95 de `POST /validar` > 2s por 10 min | Alta — viola RNF-01 |
| Queda abrupta no volume de validações | volume diário < 20% da média móvel de 7 dias | Média — pode indicar integração quebrada rio acima |
| Taxa de reprovação anômala | % de `REPROVADA` sobe mais de 2x a média móvel | Média — pode indicar dado ruim entrando em massa (ex.: import corrompido) |
| Backlog da fila crescendo | tamanho da fila `PENDENTE` sobe de forma sustentada por > 10 min | Crítica — indica Worker parado ou mais lento que o ritmo de agendamento |
| Job em `ERRO` | qualquer `job_validacao.status = 'ERRO'` (deveria ser raro) | Alta — esgotou as tentativas automáticas; exige investigação manual |
| Ausência de consumo | nenhum job `CONCLUIDO` nos últimos N minutos **enquanto há jobs `PENDENTE`** | Crítica — sintoma mais direto de Worker parado (ver troubleshooting) |

## 4. Troubleshooting

### "Recebi 500 ERRO_INTERNO ao validar uma movimentação"

1. Confirmar que não é um 404/422 disfarçado — o contrato de erro sempre inclui `erro.codigo`; só `ERRO_INTERNO` cai neste fluxo.
2. Olhar o console do `uvicorn` (ou o log de erro, em produção) no momento da chamada — o traceback completo está lá (ver §2).
3. Confirmar que nenhuma escrita parcial ocorreu: `SELECT * FROM validacao_auditoria WHERE movimentacao_id = ?` não deve ter um registro novo para esta tentativa, e `Movimentacao.status`/`resultado_ultima_validacao` devem estar inalterados (ADR-0007, INV-04) — se houver escrita parcial, é uma regressão grave na transação, não um bug de regra.
4. Reproduzir localmente com o mesmo `movimentacaoId` contra um banco com os mesmos dados (o seed é determinístico — `RNG_SEED` fixo — então o mesmo `movimentacaoId` sempre tem o mesmo estado após `python -m app.seed.seed`).

### "Uma movimentação que eu esperava `APROVADA` voltou `REPROVADA`"

1. Ler `inconsistencias[]` na resposta de `POST /validar` (ou `ultimaValidacao.inconsistencias` em `GET /movimentacoes/{id}`) — todo código ali pertence ao catálogo de 34 (`docs/regras/catalogo-regras.md`); a mensagem já indica a causa.
2. Se o código for `T06`/`P04`/`P05`/`P06`/`TG06`/`CC06`/`AE06` (aprovação), verificar as três condições de integridade (`spec.md` §5.3): a linha existe? se decidida, o aprovador está ativo? o responsável esperado (`spec.md` §5.3.1) existe e está ativo?
3. Se o código for de existência/atividade de entidade (ex.: `T04`, `P02`), verificar diretamente a entidade referenciada no banco.

### "Preciso saber por que uma movimentação ficou `AGUARDANDO_APROVACAO`"

Não é um defeito — é o fluxo humano de aprovação incompleto (`spec.md` §7.3). Consultar `Aprovacao` filtrando por `movimentacao_id`: a(s) linha(s) com `estado = PENDENTE` são exatamente o que falta decidir.

### "O seed não roda / diz que já rodou, mas eu esperava dados novos"

O seed é idempotente por design (`spec.md` §12): ele verifica a existência da matrícula marcadora (`M000001`) e, se encontrada, não faz nada. Para recriar os dados do zero em desenvolvimento, apague o arquivo do banco (`backend/portal_mobilidade.db*`) e rode `python -m app.seed.seed` novamente — nunca edite o seed para pular a checagem de idempotência em produção. Mesmo quando o seed em si é um no-op, ele ainda executa o producer ao final (`app/seed/seed.py::seed`), então rodá-lo de novo é uma forma segura de garantir que solicitações aptas sejam agendadas.

### "Uma movimentação apta não está sendo validada — o Worker parou?"

1. Verificar o backlog: `SELECT COUNT(*) FROM job_validacao WHERE status = 'PENDENTE'`. Se > 0 e crescendo, o Worker não está consumindo.
2. Confirmar que o processo `python -m app.processing.worker` está de fato rodando (é um processo separado do `uvicorn` — subir a API não sobe o Worker).
3. Olhar o log do Worker: a última linha `job_validacao_concluido`/`job_validacao_falhou` indica quando ele processou algo pela última vez.
4. Se o Worker caiu no meio de um job, esse job específico pode ter ficado preso em `PROCESSANDO` (o MVP não tem um mecanismo de "job travado" — limitação conhecida, ver R7/R8 em `spec.md` §14). Diagnóstico: `SELECT * FROM job_validacao WHERE status = 'PROCESSANDO' AND iniciado_em < <limite razoável>`. Correção manual no MVP: reiniciar o Worker; para produção, a evolução para SQS resolve isso nativamente (visibility timeout).
5. Reiniciar: `python -m app.processing.worker`. Ele retoma do job pendente mais antigo automaticamente — não é preciso reexecutar o seed nem o producer.

### "Um job ficou em `ERRO`"

1. `SELECT * FROM job_validacao WHERE status = 'ERRO'` — o campo `ultimo_erro` traz a última mensagem técnica (tipo da exceção + texto, truncados, sem dado sensível).
2. Confirmar que `Movimentacao.status`/`resultado_ultima_validacao` da movimentação associada permanecem inalterados (nenhum resultado parcial foi persistido — ADR-0007/INV-04 valem também no caminho do Worker).
3. Investigar a causa raiz a partir de `ultimo_erro` e do log correlato (`job_id` no log do Worker).
4. Depois de corrigido o problema de fundo (ex.: dado corrompido, bug), não há reagendamento automático de um job `ERRO` no MVP — é preciso reprocessar manualmente (ex.: script ad-hoc chamando `validacao_service.validar` para o `movimentacao_id`, ou criar um novo `JobValidacao` para ele). Não é um caminho coberto por endpoint no MVP.

### "Erros de contenção/lock no SQLite (`database is locked`)"

O MVP roda com `journal_mode=WAL` e um único Worker consumidor, o que já minimiza esse risco (WAL permite leitores concorrentes com um escritor). Se ainda assim ocorrer:

1. Confirmar que não há mais de um processo Worker rodando simultaneamente (o MVP não coordena múltiplos consumers — plan.md §7.5). `Get-Process python` (Windows) ou `ps aux | grep worker` para checar.
2. Confirmar que nenhum outro processo (ex.: uma sessão de `sqlite3` CLI aberta, um IDE com o arquivo `.db` aberto para inspeção) mantém uma transação de escrita pendente sobre o mesmo arquivo.
3. Isso é, por definição, o primeiro gatilho de evolução para PostgreSQL/RDS (`docs/architecture.md` §2.1) — se a contenção for recorrente mesmo com um único Worker, o volume já superou o que SQLite comporta bem.

## 5. Investigação de incidentes

A auditoria (`ValidacaoAuditoria` + `InconsistenciaAuditoria`) é append-only (RC-07, INV-08) e é a fonte primária de evidência: nenhuma investigação depende de logs voláteis para reconstruir "o que o motor decidiu e quando".

Roteiro padrão:

1. **Delimitar a janela temporal** do incidente reportado.
2. **Consultar `validacao_auditoria`** na janela: `SELECT * FROM validacao_auditoria WHERE data_hora BETWEEN ? AND ? ORDER BY data_hora`. Cada linha é uma execução real do motor — `versao_motor` identifica qual versão do código a produziu, útil se houve deploy no meio da janela.
3. **Para cada execução suspeita, puxar as inconsistências**: `SELECT * FROM inconsistencia_auditoria WHERE validacao_id = ?` — o conjunto exato de códigos e mensagens retornado ao usuário naquele momento, imutável.
4. **Cruzar com o estado atual da movimentação** (`Movimentacao.status`, `resultado_ultima_validacao`) para confirmar se uma revalidação posterior já mudou o quadro.
5. **Se o incidente for "resultado errado" (não uma exceção):** reconstruir o `ValidationContext` daquele momento é o passo mais caro, porque o contexto não é persistido — apenas o resultado. Vale registrar a limitação: para reproduzir exatamente o que o motor viu, é necessário que os dados referenciados (departamento, cargo, aprovações) não tenham mudado desde a validação auditada. Isso é uma lacuna conhecida (ver `docs/architecture.md` §2.1, "Versionamento de regras" como gatilho relacionado — versionar o *contexto*, não só o motor, é uma evolução possível se investigação de incidente exigir reprodução exata).
6. **Se o incidente for uma exceção (500):** a auditoria não terá registro (por design — ADR-0007); a evidência está exclusivamente no log de erro do processo (§2) e no traceback ali contido.
