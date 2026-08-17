# ADR-0004 — `Movimentacao.status` e `resultado_ultima_validacao` são campos distintos, com semânticas diferentes

**Status:** Aceita.

## Contexto

Toda movimentação precisa expor "onde ela está" (para listagem/filtro) e "o que a última validação encontrou" (para o detalhe). Era tentador colapsar isso em um único campo — afinal, o resultado da validação normalmente determina o status. Mas os dois conceitos respondem perguntas diferentes:

- `status` responde: **a movimentação está pronta para seguir adiante?** (`PENDENTE` = não; `APROVADA`/`REPROVADA` = sim, para um lado ou para o outro).
- `resultado_ultima_validacao` responde: **o que a última execução do motor encontrou?** (`APROVADA`, `REPROVADA`, ou `AGUARDANDO_APROVACAO` — havia inconsistência? havia aprovação pendente?).

O ponto crítico: `resultado_ultima_validacao` pode ser `AGUARDANDO_APROVACAO` — um resultado que **não existe** no domínio de `status`. Uma movimentação sem nenhum defeito de dados, mas com uma aprovação humana ainda pendente, tem `status = PENDENTE` (não terminou) e `resultado_ultima_validacao = AGUARDANDO_APROVACAO` (a validação rodou e não achou problema, só falta aprovação).

## Decisão

Manter os dois campos separados, com a seguinte tabela de derivação (`plan.md` §5.4, implementada em `validacao_service.py`):

| `resultado_ultima_validacao` | `Movimentacao.status` |
|---|---|
| `REPROVADA` | `REPROVADA` |
| `AGUARDANDO_APROVACAO` | `PENDENTE` |
| `APROVADA` | `APROVADA` |

Além disso, `resultado_ultima_validacao = null` tem significado próprio: **nunca validada** — diferente de `PENDENTE`, que pode significar tanto "nunca validada" quanto "validada e aguardando aprovação humana" (RC-09). É por isso que o endpoint de detalhe expõe `ultimaValidacao: null` separadamente do `status`, em vez de o cliente inferir "nunca validada" a partir de `status = PENDENTE`.

## Consequências

- **Positiva:** o frontend consegue distinguir, sem ambiguidade, três estados que a UI precisa tratar de forma diferente: nunca validada, validada e aguardando aprovação, e validada com defeito — sem inferir nada a partir de combinações de campos.
- **Positiva:** a auditoria (`ValidacaoAuditoria.resultado`) usa o mesmo enum de três valores que `resultado_ultima_validacao`, mantendo os dois em sincronia por construção (`validacao_service.validar` grava os dois a partir do mesmo valor calculado por `resolver_resultado`).
- **Custo aceito:** dois campos para manter sincronizados, em vez de um. O custo é baixo porque só um caminho de código (`validacao_service.validar`) escreve em ambos, sempre na mesma transação.
