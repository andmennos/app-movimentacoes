# ADR-0008 — Origem do aprovador esperado formalizada por tipo (`spec.md` §5.3.1); `TROCA_GESTOR` exige `gestor_origem_id`

**Status:** Aceita.

## Contexto

A condição 3 de integridade de uma aprovação (`spec.md` §5.3) exige que "o responsável esperado" para `GESTOR_ORIGEM`/`GESTOR_DESTINO` exista e esteja ativo. Uma versão anterior da spec descrevia essa derivação de forma genérica ("o responsável derivado da entidade — `Departamento.gestor_id`, `CentroCusto.responsavel_id`"), o que cobre bem `TRANSFERENCIA`, `MUDANCA_CENTRO_CUSTO` e `ALTERACAO_ESTRUTURA`, mas deixava `PROMOCAO` e `TROCA_GESTOR` interpretáveis durante a implementação — nenhuma dessas duas tem `Departamento`/`CentroCusto` envolvido.

Ao mesmo tempo, `TROCA_GESTOR.gestor_origem_id` era nullable no modelo, para acomodar "colaborador sem gestor atual" — mas a spec simultaneamente exigia `GESTOR_ORIGEM` e `GESTOR_DESTINO` como aprovações obrigatórias para esse tipo (§5.2), criando uma exceção sem tratamento definido: de onde viria o aprovador `GESTOR_ORIGEM` esperado se o colaborador não tem gestor atual?

## Decisão

1. **Formalizar, por tipo, de onde vem cada aprovador esperado** (`spec.md` §5.3.1 — tabela congelada, implementada em `movimentacao_service._resolver_responsaveis`):

   | Tipo | `GESTOR_ORIGEM` | `GESTOR_DESTINO` |
   |---|---|---|
   | `TRANSFERENCIA` | `departamento_origem.gestor_id` | `departamento_destino.gestor_id` |
   | `PROMOCAO` | `colaborador.gestor_id` | — |
   | `TROCA_GESTOR` | `movimentacao.gestor_origem_id` | `movimentacao.gestor_destino_id` |
   | `MUDANCA_CENTRO_CUSTO` | — | `centro_custo_destino.responsavel_id` |
   | `ALTERACAO_ESTRUTURA` | `colaborador.gestor_id` | — |

2. **Tornar `gestor_origem_id` obrigatório em `TROCA_GESTOR`**, removendo a exceção "sem gestor atual". Colaborador sem gestor atual fica fora do escopo do MVP para este tipo de movimentação — não existe fluxo de troca de gestor para esse caso.

## Por que `TROCA_GESTOR` deriva de campos da própria movimentação, não de `colaborador.gestor_id`

Diferente de `PROMOCAO`/`ALTERACAO_ESTRUTURA` (que não têm campos de gestor dedicados e por isso usam o atributo geral do colaborador), `TROCA_GESTOR` tem `gestor_origem_id`/`gestor_destino_id` como campos próprios, especificamente para registrar quem é o gestor sendo substituído e quem é o novo gestor **nesta movimentação**. Usar esses campos (em vez de `colaborador.gestor_id`) evita depender de o atributo geral do colaborador estar sincronizado com o que a movimentação registrou, e é consistente com o padrão de todos os outros tipos (origem/destino sempre resolvidos a partir dos campos da própria `Movimentacao").

## Consequências

- **Positiva:** a resolução do aprovador esperado deixou de ser uma decisão de implementação — está congelada na spec e coberta por teste dedicado (`tests/integracao/test_context_builder.py`), eliminando o risco de cada desenvolvedor "inventar" uma derivação diferente.
- **Positiva:** a obrigatoriedade de `gestor_origem_id` elimina um caso especial que não tinha regra de negócio definida (a spec exigia a aprovação, mas não dizia como resolvê-la sem o campo).
- **Escopo reduzido, documentado:** colaboradores sem gestor atual (ex.: o topo da hierarquia) simplesmente não podem ser alvo de `TROCA_GESTOR` no MVP. Isso é uma limitação aceita, não um bug — `Colaborador.gestor_id` continua nullable como atributo geral.
