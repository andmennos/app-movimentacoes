# Relatório de uso de IA

Este projeto foi desenvolvido com assistência intensiva de IA (Claude, via Claude Code) em todas as etapas: especificação, revisão do SDD, implementação de backend e frontend, escrita de testes e desta própria documentação. Este relatório descreve honestamente onde a IA foi usada, o que foi aceito e rejeitado, quais ambiguidades foram levantadas pela IA versus decididas pelo humano, e onde a IA não foi usada.

## 1. Ferramentas e em que etapas

**Claude (Anthropic), via Claude Code CLI** foi a única ferramenta de IA usada, em três frentes:

1. **Revisão do SDD** (`spec.md`, `plan.md`, `tasks.md`) — aplicação de correções apontadas pelo humano sobre uma especificação já existente.
2. **Implementação completa** — modelos ORM, motor de validação (34 regras), API FastAPI, seed determinístico, frontend Angular, e toda a suíte de testes (unidade, integração, API, arquitetura).
3. **Documentação de fechamento** — este relatório, `DECISIONS.md`, `docs/architecture.md`, `docs/operations.md`, ADRs e catálogo de regras.

## 2. As rodadas de consolidação deste projeto

O próprio `spec.md` traz evidência de rodadas anteriores a esta sessão: §9 ("Guarda anti-regressão de AE05") existe precisamente porque, em uma versão anterior da análise, `AE05` foi especificada incorretamente como regra de ciclo — um erro identificado e corrigido antes desta sessão começar.

1. **Rodada 1 — elaboração inicial do domínio** (anterior a esta sessão). Produziu o `spec.md`/`plan.md`/`tasks.md` congelados que esta sessão recebeu como ponto de partida, incluindo decisões já corrigidas de rodadas ainda mais antigas (ex.: a remoção de "P01 — colaborador ativo" por duplicar `G02`, já documentada como decisão fechada; a reversão do erro de `AE05`).
2. **Rodada 2 — revisão do SDD nesta sessão.** O humano apontou 6 ajustes concretos antes de autorizar a implementação (detalhados na seção 3). A IA aplicou cada um, propagando a mudança por todos os documentos afetados (`spec.md`, `plan.md`, `tasks.md`) e verificando consistência cruzada (numeração de critérios de aceite, tabelas de rastreabilidade, matriz de dependências).
3. **Rodada 3 — implementação com correção contínua.** Ao implementar, a IA escreveu testes antes ou junto de cada módulo e rodou a suíte completa a cada mudança, o que expôs defeitos reais no próprio código gerado (não na especificação) — detalhados na seção 4. Nenhum desses defeitos exigiu reabrir uma decisão de domínio; todos foram bugs de implementação, corrigidos e recobertos por teste de regressão antes de prosseguir.
4. **Rodada 4 — revisão de objetivo (2026-08-16), identificada pelo candidato.** Depois da implementação da rodada 3 estar completa e verde (209 testes de backend, 21 de frontend), o candidato identificou que a solução tinha se desviado do objetivo real do case: um botão **Validar** no Angular fazia da validação uma ação manual, quando o valor central do produto é demonstrar um fluxo **automatizado**. O candidato especificou o SDD revisado (`spec.md`/`plan.md`/`tasks.md` atualizados com RC-13 a RC-15, `JobValidacao`, producer/gate/Worker) e pediu que a IA o implementasse como ajuste incremental sobre o código existente, não como reescrita. Ver seção 3.1 para o que foi removido/adicionado e seção 6 para as lições desta rodada especificamente.
5. **Rodada 5 — ajuste pontual do mesmo dia (2026-08-16): botão manual condicional + histórico ilustrativo.** Com a rodada 4 completa e verde, o candidato pediu um refinamento, não uma reversão: reintroduzir um botão de validação manual no detalhe, mas só para solicitações `PENDENTE`/`REPROVADA` (nunca `APROVADA`), fazendo "a mesma coisa que o processamento" com feedback em tempo real, funcionando mesmo com o Worker parado; e, para `APROVADA`, um histórico mostrando que a solicitação "já foi realizada, não só validada" — explicitamente como cenário imaginário, sem implementar efetivação real. Ver seção 3.2 para as decisões de interpretação e [ADR-0010](decisoes/0010-botao-validacao-manual-condicional-e-historico-ilustrativo.md) para o detalhamento técnico.

## 3. Ambiguidades levantadas: decididas pelo humano vs. pela IA

### Decididas pelo humano (rodada 2, antes de qualquer código)

O humano revisou o SDD já elaborado e identificou seis pontos que precisavam de correção antes da implementação começar — todos registrados como decisões explícitas, aplicadas pela IA:

1. `Cargo.nivel_aprovacao_necessaria` (`GESTOR|RH|GERENCIA|DIRETORIA`) → renomear para `aprovacao_adicional` (`GERENCIA|DIRETORIA|null`), eliminando os valores redundantes com `P04`/`P05` (ver ADR-0003).
2. `TROCA_GESTOR.gestor_origem_id` deixa de ser nullable — "colaborador sem gestor atual" sai de escopo para este tipo (ver ADR-0008).
3. Formalizar, por tipo, de onde vem o aprovador esperado de `GESTOR_ORIGEM`/`GESTOR_DESTINO` (spec §5.3.1), em vez de deixar a implementação decidir durante o desenvolvimento (ver ADR-0008).
4. Remover `SYS01`: exceção não tratada deixa de virar inconsistência de negócio (reprovação) e passa a propagar como HTTP 500, sem alterar a movimentação (ver ADR-0007).
5. Adicionar entregáveis faltantes no fechamento do case: `DECISIONS.md`, `docs/architecture.md`, `docs/operations.md`.
6. Remover o teste estático de inspeção de `estrutura_pai_id` (`CA-027`/`CN-A03`) do conjunto de testes obrigatórios de `AE05`, por testar implementação em vez de comportamento — mantendo apenas os dois testes comportamentais (destino ancestral/descendente).

Em todos os seis casos, a IA implementou exatamente o que foi pedido e propagou a mudança pelos documentos correlatos; nenhum foi uma sugestão da IA aceita pelo humano — foram instruções do humano executadas pela IA.

### 3.1 Decidido pelo humano (rodada 4 — correção de objetivo)

O candidato, não a IA, identificou o desvio de objetivo (botão manual vs. fluxo automático) e especificou a correção por completo antes de pedir a implementação — incluindo o desenho do fluxo (`Gate de aprovação → Producer → JobValidacao → Worker → ValidacaoService → auditoria`), os campos mínimos de `JobValidacao`, a divisão de responsabilidades em `app/processing/`, e a decisão explícita de manter `POST /validar` funcional como adaptador técnico. A IA não sugeriu nada disso — recebeu o SDD já revisado como fonte de verdade e implementou:

- Removeu do Angular: botão "Validar movimentação", o método `validar()` do `MovimentacaoService` e do `DetalheComponent`, o signal `validando`, e os testes que esperavam clique no botão.
- Adicionou: modelo e repositório de `JobValidacao`; `app/processing/{approval_gate,producer,worker}.py`; mensagens de estado no frontend que distinguem "aguardando aprovação/processamento" de "bloqueada por reprovação" sem sugerir nenhuma ação manual — uma leitura própria do requisito "sem sugerir ação manual", já que o SDD descrevia o *o quê* (estados distinguíveis) mas não o texto exato de cada mensagem.
- Reaproveitou, sem duplicar: `app.validation.aprovacoes.tipos_exigidos`/`integra` como única fonte das exigências de aprovação também dentro do gate — decisão explícita do SDD ("não crie um segundo mapa de aprovações"), verificada nesta implementação construindo o gate sobre o mesmo `ValidationContext` que a engine usa, em vez de reimplementar a leitura das linhas de `Aprovacao`.

### 3.2 Decidido pelo humano, com interpretação da IA dentro do espaço deixado em aberto (rodada 5)

O candidato especificou as quatro condições do ajuste (seção 2, item 5) em linguagem de negócio, sem descer a nível de campo/status. A IA precisou resolver duas ambiguidades concretas para implementar:

- **O que significa "pendentes, bloqueadas e anômalas" no sistema atual.** O frontend só distingue dois status (`PENDENTE`, `REPROVADA`) — "anômala" não tem campo próprio e hoje se manifesta como `PENDENTE` sem `ultimaValidacao` (aprovação ausente/não íntegra é indistinguível de aprovação simplesmente pendente no dado exposto pela API). A IA optou por decidir a visibilidade do botão por **`status` do domínio** (`PENDENTE` ou `REPROVADA`), e não por `ultimaValidacao === null`, porque a segunda opção esconderia o botão depois de um único clique manual mesmo que a situação de negócio não tivesse mudado (validar manualmente uma pendência ainda aberta retorna `AGUARDANDO_APROVACAO`, que povoa `ultimaValidacao`, mas a solicitação continua pendente). Documentada em [ADR-0010](decisoes/0010-botao-validacao-manual-condicional-e-historico-ilustrativo.md).
- **Como construir o "histórico" sem reabrir RC-07/RC-08 (auditoria não tem endpoint próprio; só a última validação é exposta) nem implementar a efetivação real que o pedido explicitamente proibiu.** A IA optou por montar a linha do tempo inteiramente no cliente, a partir de campos já retornados por `GET /movimentacoes/{id}` (nenhuma consulta nova, nenhum endpoint novo), e por marcar a última entrada ("efetivação nos sistemas corporativos") como fixa e visivelmente rotulada como cenário ilustrativo — em vez de, por exemplo, inventar um novo endpoint de "log de processamento" que pareceria uma feature real.

### Decisões de implementação tomadas pela IA (rodada 3), dentro do espaço já delimitado pela spec

A spec congelada deixava algumas decisões de baixo nível para a implementação. A IA resolveu-as com justificativa explícita, documentada em ADR quando relevante:

- **De onde vem `cargoAtual` na API de detalhe.** A spec mostra um campo `cargoAtual` no exemplo de resposta de `PROMOCAO`, mas não diz explicitamente se ele reflete `movimentacao.cargo_origem_id` (o valor registrado no momento da solicitação) ou `colaborador.cargo_id` (o cargo atual "ao vivo"). A IA optou por `colaborador.cargo_id`, pela mesma fonte que a regra `P03` usa (a nota da spec anota `Colaborador.cargo_id` como "base de P03") — mantendo exibição e regra de negócio consistentes com a mesma fonte de verdade. `movimentacao.cargo_origem_id` permanece no schema como campo de registro, sem exposição direta na API.
- **Granularidade das consultas SQL do `ValidationContext`.** A spec exige "carga única, sem N+1", mas não define se isso significa literalmente 1 `SELECT`. A IA interpretou como "número fixo e pequeno de consultas, nenhuma delas repetida por linha de dado" — implementado como no máximo ~4 consultas (a movimentação com todos os relacionamentos via `JOIN`, aprovações, verificação de conflito de `G04`, e o grafo de gestores só para `TROCA_GESTOR`) — e verificou isso com um teste de contagem de queries, não apenas inspeção visual.
- **Estrutura de diretórios de teste além das listadas em `plan.md`.** O plano lista `tests/{validation,engine,api,auditoria,integracao,arquitetura}/`, mas não previa onde testar repositórios/configuração de banco. A IA acrescentou `tests/persistencia/`, por analogia com as demais.

## 4. O que foi aceito e o que foi corrigido

### Aceito sem alteração

A maior parte do código gerado — modelos ORM, as 34 regras de validação, engine, schemas Pydantic, componentes Angular, e (na rodada 4) o gate/producer/Worker — passou direto pela suíte de testes sem precisar de correção após a primeira escrita. Ao final da rodada 3: 209 testes de backend, 21 de frontend. Ao final da rodada 4 (processamento automático): 237 testes de backend, 24 de frontend. Ao final da rodada 5 (botão condicional + histórico ilustrativo, sem mudança de backend): **237 testes de backend, 29 de frontend**.

### Corrigido após ser gerado pela própria IA (bugs reais, encontrados por teste e por verificação manual)

1. **Seed: mutação de estado compartilhado corrompia aprovadores de cenários "limpos".** A primeira versão do gerador de seed marcava `colaborador.ativo = False` diretamente em objetos do "pool" de colaboradores para construir cenários de defeito — mas esses mesmos objetos podiam ser sorteados depois como *aprovador* de uma movimentação totalmente diferente, contaminando um cenário que deveria ser "aprovada" com um aprovador inativo. **Isso não foi pego pelos testes automatizados** (eles usam builders isolados, não o script de seed completo) — foi encontrado ao rodar a aplicação real de ponta a ponta e notar, pelo Swagger, que uma movimentação marcada como "aprovada" no gerador vinha reprovada. Corrigido sorteando colaboradores já inativos do pool correto em vez de mutar objetos compartilhados; adicionado teste de seed que valida a distribuição de resultados.
2. **`cargoAtual` aparecia em movimentações que não são `PROMOCAO`.** A rota de detalhe resolvia `cargoAtual` a partir de `colaborador.cargo` incondicionalmente, em vez de apenas quando `tipo == PROMOCAO` — visível ao abrir, no navegador, o detalhe de uma `TRANSFERENCIA` e ver um campo "Cargo atual → destino" que não deveria existir para esse tipo (violação de "campos de origem/destino exibidos conforme o tipo"). Encontrado por inspeção visual no navegador, não pelos testes automatizados (que não verificavam a ausência do campo para tipos não aplicáveis até esse ponto). Corrigido com um teste de regressão dedicado (`test_campos_de_cargo_aparecem_apenas_em_promocao`).
3. **`use_alter=True` em FKs do SQLite quebrava `DROP TABLE` nos testes.** Uma tentativa de silenciar um aviso do SQLAlchemy sobre dependência circular de FK (`colaborador` ↔ `departamento`/`centro_custo`) usando `use_alter=True` causou falha real (`FOREIGN KEY constraint failed`) ao derrubar o schema em teste — porque SQLite não suporta `ALTER TABLE ADD CONSTRAINT`. Revertido; o aviso original era inofensivo (SQLite ainda encontra uma ordem de `DROP` válida) e a fixture de teste passou a descartar o banco em memória inteiro em vez de tentar `DROP TABLE` um a um.
4. **Alias `as` em `@else if` do Angular não era reconhecido pelo compilador de template.** `@else if (movimentacao(); as mov)` falhava em `ng build` com "Property 'mov' does not exist". Corrigido reestruturando para `@else if (movimentacao()) { @let mov = movimentacao()!; ... }`.

Em todos os quatro casos, a causa raiz foi diagnosticada (não só o sintoma corrigido), e um teste ou verificação manual documentada foi adicionado para evitar regressão.

### Corrigido na rodada 4 (processamento automático)

5. **Seed: cenário "múltiplas inconsistências" de `TROCA_GESTOR` sempre caía em `ANOMALO`, nunca em `APTA`.** Ao rodar o seed real e inspecionar a distribuição de resultados do producer, o número de movimentações `ANOMALO` (14 de 126) era mais alto do que a taxa esperada de ~30% do sub-modo "integridade quebrada". Investigação: o cenário de `TROCA_GESTOR` que testa "TG02+TG03 simultâneos" usa deliberadamente um `gestor_destino` inativo — mas `GESTOR_DESTINO`, para este tipo, deriva exatamente de `gestor_destino_id` (spec §5.3.1), então o próprio responsável esperado da aprovação também fica inválido, e o gate classifica isso como `ANOMALO` em vez de `APTA`, **em 5 de 5 execuções**, não em ~30%. Não era um bug — é o comportamento correto do gate reagindo a um dado deliberadamente quebrado (spec §5.4 já previa esse cenário) — mas a causa não era óbvia até rastrear a derivação do responsável esperado. Documentado com comentário no código-fonte do seed em vez de "corrigido", porque não havia nada de errado para corrigir; a investigação em si é o valor registrado aqui.

### Rejeitado

Nenhuma sugestão de IA foi rejeitada pelo humano durante a rodada 2 (revisão do SDD) — os seis pontos da seção 3 já eram instruções do humano, não sugestões da IA para aprovar ou recusar. Na rodada 3 (implementação), não houve intervenção humana ponto a ponto — a IA implementou de forma autônoma seguindo o SDD já aprovado, então "rejeição humana" não se aplica a essa rodada da mesma forma; o mecanismo de correção foi a suíte de testes e a verificação manual, descritas acima.

## 5. Onde a IA não foi usada, e por quê

- **Nenhum dado real de pessoa ou organização** entrou no seed — todos os nomes vêm de uma lista fictícia gerada previamente (`backend/app/seed/dados/nomes.json`), não de nenhuma fonte real, cumprindo a restrição de RC (spec §12).
- **Nenhuma dependência de serviço de IA em tempo de execução** — o motor de validação é determinístico, implementado como funções Python puras; não há chamada a modelo de linguagem em nenhum caminho de produção (RC-11: "IA no produto" está explicitamente fora de escopo).
- **Decisões de domínio permaneceram com o humano.** Onde a spec já continha uma decisão congelada (RC-01 a RC-12), a IA implementou-a literalmente, sem questionar ou "melhorar" — inclusive quando uma alternativa poderia parecer tecnicamente superior (`spec.md` §0 é explícito sobre isso: contrariar uma decisão congelada está errado "independentemente de parecer tecnicamente superior").

## 6. Limitações e lições aprendidas

- **A IA não identifica desvios de objetivo de negócio sozinha.** A rodada 3 produziu uma implementação internamente consistente e totalmente testada — mas alinhada a um objetivo (validação sob demanda) que já não era o objetivo real do case. A IA não questionou essa premissa em nenhum momento da rodada 3; foi o candidato, reobservando o resultado contra o enunciado original do case, quem identificou o desvio. Lição: testes verdes e cobertura completa provam que o código faz o que foi especificado — não provam que o que foi especificado é o que deveria ter sido pedido.
- **Bugs de integração aparecem quando o sistema roda de ponta a ponta, não antes.** Dos cinco defeitos reais registrados neste relatório (itens 1–5 da seção 4), nenhum foi pego por um teste de unidade isolado — todos exigiram rodar o seed real, servir a API de verdade e, em três casos, abrir o navegador. Builders e fixtures isolados (usados nos testes de unidade) tendem a já vir "corretos por construção", escondendo exatamente a classe de bug que só aparece quando muitos dados gerados de formas diferentes interagem entre si.
- **Pedir para a IA implementar um SDD já revisado, em vez de co-desenhar a revisão, produziu uma sessão mais previsível.** A rodada 4 recebeu a spec já corrigida e um plano de arquivos já nomeado (`approval_gate.py`, `producer.py`, `worker.py`) — a IA não precisou inferir a decomposição correta, só implementá-la e testá-la. Isso reduziu o espaço de ambiguidade a decisões de baixo nível (ver seção 3.1), que são mais fáceis de revisar em retrospecto do que decisões de arquitetura.
- **Limitação conhecida e não resolvida:** o MVP não versiona o `ValidationContext` usado em cada validação passada (`docs/operations.md` §5) — investigar por que uma validação antiga produziu um resultado específico exige que os dados referenciados não tenham mudado desde então. Aceito conscientemente para o escopo do MVP, não corrigido nesta rodada.
