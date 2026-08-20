# Catálogo de regras — Portal de Mobilidade Organizacional

**37 regras executáveis no MVP** (revisão de 2026-08-19 — spec.md RC-03). Nenhuma regra pode ser adicionada, removida ou renumerada sem nova decisão registrada (`specs/001-movimentacoes/spec.md` §0).

## Convenções

- **Código** é contrato público: aparece na API (`inconsistencias[].codigo`) e na auditoria persistida. Um código, uma vez publicado, **nunca é reciclado** — mesmo que a regra seja revista, um código antigo não é reatribuído a uma regra diferente.
- **Pré-condição** define quando a regra **não avalia** (retorna lista vazia de inconsistências), evitando cascata de erros redundantes. Por exemplo, se o departamento de destino não existe (`T03`), não faz sentido perguntar se ele está ativo (`T04`) — a regra simplesmente não roda.
- **Severidade** tem valor único no MVP: `ERRO`. O campo permanece no contrato da API para permitir evolução futura (ex.: `AVISO`) sem quebrar clientes.
- **Ordem de execução:** regras gerais primeiro, depois as específicas do tipo, sempre na ordem em que aparecem neste catálogo. Essa ordem é determinística e testada (INV-05).
- O motor **não para na primeira inconsistência** — todas as regras aplicáveis são executadas e todas as falhas são reportadas de uma vez (INV-02).

---

## Gerais — G (4 regras)

Aplicam-se a **todos** os tipos de movimentação, sempre antes das regras específicas.

| Código | Regra | Pré-condição | Falha quando | Mensagem |
|---|---|---|---|---|
| G01 | Colaborador existe | — | `colaborador` é nulo | Colaborador não encontrado |
| G02 | Colaborador está ativo | G01 passou | `colaborador.ativo = false` | Colaborador não está ativo |
| G03 | Tipo de movimentação é válido | — | `tipo` não pertence ao enum | Tipo de movimentação inválido |
| G04 | Sem movimentação conflitante | G01 passou | existe outra movimentação do **mesmo tipo**, mesmo colaborador, `status ∈ {AGUARDANDO_APROVACAO, PENDENTE}` (estado aberto — spec.md §7.1), id diferente | Existe outra movimentação do mesmo tipo em aberto para este colaborador |

Existência e atividade de departamento, cargo, centro de custo, estrutura e gestor **não pertencem às gerais** — vivem nas regras específicas de cada tipo, porque cada tipo lê entidades diferentes.

---

## Transferência — T (6 regras)

| Código | Regra | Pré-condição | Falha quando | Mensagem |
|---|---|---|---|---|
| T01 | Departamento de origem existe | — | `departamento_origem` nulo | Departamento de origem não encontrado |
| T02 | Departamento de origem ativo | T01 passou | `.ativo = false` | Departamento de origem não está ativo |
| T03 | Departamento de destino existe | — | `departamento_destino` nulo | Departamento de destino não encontrado |
| T04 | Departamento de destino ativo | T03 passou | `.ativo = false` | Departamento de destino não está ativo |
| T05 | Origem ≠ destino | T01 e T03 passaram | ids iguais | Departamento de origem e destino são iguais |
| T06 | Aprovações exigidas registradas e íntegras | — | falta linha exigida (`GESTOR_ORIGEM`/`GESTOR_DESTINO`) ou linha não íntegra | Aprovação {tipo} ausente / aprovador inválido |

`GESTOR_ORIGEM` deriva de `departamento_origem.gestor_id`; `GESTOR_DESTINO`, de `departamento_destino.gestor_id`.

---

## Promoção — P (9 regras)

> `P01 — colaborador ativo` **não existe** neste catálogo. Foi removido por duplicar `G02` (decisão registrada em ADR — ver `docs/decisoes/`). `P01` aqui é "cargo de destino existe". `P03/P07/P08/P09` foram acrescentadas/reescritas na revisão de 2026-08-19 (ver [ADR-0015](../decisoes/0015-promocao-familia-nivel-intervalo-orcamento.md)). `P06` foi ampliada na revisão corretiva de 2026-08-19 (T-75) — bundle de duas anuências, não mais uma só (ver abaixo e [ADR-0014, Emenda T-75](../decisoes/0014-matriz-dinamica-aprovacoes.md)).

| Código | Regra | Pré-condição | Falha quando | Mensagem |
|---|---|---|---|---|
| P01 | Cargo de destino existe | — | `cargo_destino` nulo | Cargo de destino não encontrado |
| P02 | Cargo de destino ativo | P01 passou | `.ativo = false` | Cargo de destino não está ativo |
| P03 | Cargo de destino é o próximo passo exato da trilha | P01 passou e `cargo_atual` conhecido | `cargo_destino.ordem_progressao != cargo_atual.ordem_progressao + 1` | Cargo de destino não é o próximo passo da trilha de progressão |
| P04 | Aprovação hierárquica registrada e íntegra | — | falta a etapa hierárquica exigida (`GESTOR_ORIGEM`/`GESTOR_SUPERIOR`/`GESTOR_RH`, conforme a matriz dinâmica) ou não íntegra | Aprovação hierárquica ausente / aprovador inválido |
| P05 | Aprovação de RH registrada e íntegra | — | falta a etapa de RH exigida (`RH`/`GESTOR_RH`) ou não íntegra | Aprovação de RH ausente / aprovador inválido |
| P06 | Aprovações adicionais registradas e íntegras quando aplicável | P01 passou | `cargo_destino.aprovacao_adicional` não é `null` e a etapa `GERENCIA`/`DIRETORIA` (pessoa concreta) **ou** a etapa `GESTOR_RH_ADICIONAL` (perfil `RH_GESTOR`) falta ou não é íntegra | Aprovação de {GERENCIA\|DIRETORIA\|GESTOR_RH_ADICIONAL} ausente / aprovador inválido |
| P07 | Cargo de destino pertence à mesma família de carreira | P01 passou e `cargo_atual` conhecido | `cargo_destino.familia_cargo != cargo_atual.familia_cargo` | Cargo de destino pertence a outra família de carreira |
| P08 | Intervalo mínimo de 6 meses-calendário desde a última promoção efetivada | P01 passou | `data_solicitacao < data_ultima_promocao_efetivada + 6 meses-calendário` | Intervalo mínimo de 6 meses desde a última promoção ainda não decorrido |
| P09 | Centro de custo atual suporta o aumento de custo | P01 passou | `max(custo_destino - custo_atual, 0) > (orcamento_mensal - custo_comprometido)` do centro de custo atual | Centro de custo não possui saldo orçamentário suficiente |

`cargo_atual` é o cargo atual do colaborador (`colaborador.cargo_id`) — base de `P03`/`P07`/`P09`. `ordem_progressao` é a posição sequencial do cargo dentro da família — **não** é o número no nome do cargo (que reinicia entre senioridades: Júnior 1/2/3 → Pleno 1/2/3 → Sênior 1..., `ordem_progressao` 1 a 7). Exemplo obrigatório: Júnior 1→Júnior 2 permitido; Júnior 1→Júnior 3 bloqueado; Júnior 3→Pleno 1 permitido (posições consecutivas apesar do número reiniciar); Júnior 3→Pleno 2 bloqueado (pula uma posição). `GESTOR_ORIGEM`/`GESTOR_SUPERIOR`/`GESTOR_RH` derivam da política dinâmica de aprovação ([ADR-0014](../decisoes/0014-matriz-dinamica-aprovacoes.md)), não de um tipo fixo — `P04`/`P05` verificam qual etapa efetivamente foi exigida para esta solicitação específica.

**Correção real de massa (T-73):** até a revisão corretiva de 2026-08-19, a família genérica "GERAL" usada pelo restante do seed permitia `Analista Júnior → Analista Pleno` como um único passo válido (ordem_progressao 1→2 sem níveis intermediários) — um problema de **dados**, não de regra (`P03` sempre esteve correta). Corrigido tornando a família granular (Júnior 1/2/3 → Pleno 1/2/3 → ...), igual ao exemplo obrigatório acima. Ver `tests/persistencia/test_t73_trilha_granular.py`.

**P06 — denominação obrigatória:** *Política de aprovação de promoção baseada no cargo de destino*. Não usar "mecanismo de aprovação superior" em código, comentários ou documentação. Aplica-se **somente** a `PROMOCAO` — nenhum outro tipo consulta `aprovacao_adicional`. Desde a revisão corretiva (T-75), `aprovacao_adicional` exige **duas** anuências, não uma: `GERENCIA`/`DIRETORIA` (pessoa concreta, resolvida subindo `gestor_id` até achar alguém cujo cargo atual tem `Cargo.papel_lideranca` igual ao exigido — nunca por parse de `Cargo.nome`) e, depois, `GESTOR_RH_ADICIONAL` (perfil `RH_GESTOR`, tipo técnico distinto de `GESTOR_RH` para não colidir com uma substituição anterior da mesma movimentação — `UNIQUE(movimentacao_id, tipo)`). Ver [ADR-0014, Emenda T-75](../decisoes/0014-matriz-dinamica-aprovacoes.md).

**P09 — unidade monetária:** `custo_mensal_referencia` (`Cargo`) e `orcamento_mensal`/`custo_comprometido` (`CentroCusto`) são inteiros em **centavos** — nunca `float` (evita erro de arredondamento na comparação exata e no acúmulo de custo comprometido ao longo de múltiplas promoções).

Troca de **família** de cargo não é promoção neste MVP — fora de escopo, documentada como evolução futura (`MUDANCA_CARREIRA`).

### Extensões documentadas — não implementadas no MVP

Estas políticas são **fictícias, criadas exclusivamente para demonstrar extensibilidade do motor**. Não são regra deste desafio, não são política real de nenhuma organização e não representam exigência legal. Não implementar.

| Código | Extensão | Natureza |
|---|---|---|
| PX01 | Tempo mínimo de empresa | Política organizacional fictícia e configurável |
| PX02 | Tempo mínimo no cargo | Política organizacional fictícia e configurável |
| PX03 | Avaliação de desempenho mínima | Política organizacional fictícia e configurável |
| PX04 | Faixa salarial compatível | Política organizacional fictícia e configurável |
| PX05 | Posição / headcount disponível | Política organizacional fictícia e configurável |

---

## Troca de gestor — TG (6 regras)

| Código | Regra | Pré-condição | Falha quando | Mensagem |
|---|---|---|---|---|
| TG01 | Novo gestor existe | — | `gestor_destino` nulo | Novo gestor não encontrado |
| TG02 | Novo gestor está ativo | TG01 passou | `.ativo = false` | Novo gestor não está ativo |
| TG03 | Novo gestor possui função compatível | TG01 passou | `gestor_destino.cargo.permite_gestao = false` ou cargo nulo | Novo gestor não possui cargo com função de gestão |
| TG04 | Colaborador ≠ seu próprio gestor | G01 e TG01 passaram | `gestor_destino.id == colaborador.id` | Colaborador não pode ser seu próprio gestor |
| TG05 | Alteração não cria ciclo hierárquico | G01 e TG01 passaram | percorrendo `gestor_id` a partir de `gestor_destino`, alcança-se `colaborador.id` | A alteração criaria um ciclo hierárquico |
| TG06 | Aprovações exigidas registradas e íntegras, e `GESTOR_ORIGEM` corresponde ao gestor atual real | — | falta linha exigida, não íntegra, **ou** `gestor_origem_id` não coincide com `colaborador.gestor_id` | Aprovação {tipo} ausente / aprovador inválido; ou "GESTOR_ORIGEM não corresponde ao gestor atual real do colaborador" |

`GESTOR_ORIGEM` e `GESTOR_DESTINO` derivam dos campos próprios da movimentação (`gestor_origem_id`/`gestor_destino_id`), não de `colaborador.gestor_id` — mas `TG06` (revisão de 2026-08-19, T-65) confirma que `gestor_origem_id` de fato reflete o gestor atual real do colaborador, para pegar uma inversão dos dois campos (origem/destino trocados). `TG05` continua exclusivamente ciclo hierárquico — nunca usada para mascarar um aprovador invertido.

**TG05 — algoritmo obrigatório** (implementado em `validation/troca_gestor.py`):

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

O conjunto de visitados e o limite de profundidade protegem contra ciclo já presente nos dados. Sem eles, laço infinito. `TG05` é a **única** regra de ciclo hierárquico no catálogo — ver nota sobre `AE05` abaixo.

---

## Mudança de centro de custo — CC (6 regras)

| Código | Regra | Pré-condição | Falha quando | Mensagem |
|---|---|---|---|---|
| CC01 | Centro de custo de origem existe | — | nulo | Centro de custo de origem não encontrado |
| CC02 | Centro de custo de origem ativo | CC01 passou | `.ativo = false` | Centro de custo de origem não está ativo |
| CC03 | Centro de custo de destino existe | — | nulo | Centro de custo de destino não encontrado |
| CC04 | Centro de custo de destino ativo | CC03 passou | `.ativo = false` | Centro de custo de destino não está ativo |
| CC05 | Origem ≠ destino | CC01 e CC03 passaram | ids iguais | Centro de custo de origem e destino são iguais |
| CC06 | Aprovação do responsável pelo destino registrada e íntegra | — | falta `GESTOR_DESTINO` ou não íntegra | Aprovação do responsável pelo centro de custo ausente / inválida |

`GESTOR_DESTINO` deriva de `centro_custo_destino.responsavel_id`.

---

## Alteração de estrutura — AE (6 regras)

> **Guarda anti-regressão.** `ALTERACAO_ESTRUTURA` move um **colaborador** entre estruturas organizacionais — não é o reparentamento de nós da árvore. Mover um colaborador entre nós **não pode** criar ciclo (um colaborador não é ancestral nem descendente de uma estrutura). Por isso `AE05` é, e sempre foi, `origem ≠ destino` — ponto final. `AE05` **já foi especificado como regra de ciclo** em versões anteriores da análise deste projeto; a decisão foi revertida e documentada em ADR (`docs/decisoes/`) e não deve ser reintroduzida por inércia. Ciclo hierárquico é regra real **exclusivamente** em `TG05`.

| Código | Regra | Pré-condição | Falha quando | Mensagem |
|---|---|---|---|---|
| AE01 | Estrutura de origem existe | — | nulo | Estrutura de origem não encontrada |
| AE02 | Estrutura de origem ativa | AE01 passou | `.ativo = false` | Estrutura de origem não está ativa |
| AE03 | Estrutura de destino existe | — | nulo | Estrutura de destino não encontrada |
| AE04 | Estrutura de destino ativa | AE03 passou | `.ativo = false` | Estrutura de destino não está ativa |
| AE05 | **Origem ≠ destino** | AE01 e AE03 passaram | ids iguais | Estrutura de origem e destino são iguais |
| AE06 | Aprovações exigidas registradas e íntegras | — | falta `GESTOR_ORIGEM` ou não íntegra | Aprovação do gestor ausente / aprovador inválido |

`GESTOR_ORIGEM` deriva de `colaborador.gestor_id` (o gestor atual da pessoa, análogo a `PROMOCAO`). O módulo `validation/estrutura.py` **não referencia `estrutura_pai_id` em nenhum ponto** — verificado por revisão de código (não por teste automatizado dedicado; ver `docs/decisoes/` sobre por que o teste estático foi removido do conjunto de testes obrigatórios).

### Extensão documentada — não implementada no MVP

| Código | Extensão | Natureza |
|---|---|---|
| AEX02 | Validação hierárquica sobre a árvore de `EstruturaOrganizacional` | Extensão futura, gatilho: se validações hierárquicas sobre a árvore forem requeridas pelo negócio |

---

## Totalização

| Família | Regras |
|---|---|
| Gerais (G) | 4 |
| Transferência (T) | 6 |
| Promoção (P) | 9 |
| Troca de gestor (TG) | 6 |
| Centro de custo (CC) | 6 |
| Alteração de estrutura (AE) | 6 |
| **Total** | **37** |

Sem exceção não tratada, o conjunto de códigos emitidos por uma execução é sempre um subconjunto destes 37. Uma exceção não tratada durante a validação **não gera código de inconsistência** — não existe `SYS01` neste catálogo. Ela propaga, aborta a transação e resulta em HTTP 500 (`ERRO_INTERNO`); ver `docs/decisoes/` e `docs/operations.md`.
