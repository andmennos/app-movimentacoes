# ADR-0001 — `ALTERACAO_ESTRUTURA` move um colaborador, não reparenta a árvore; `AE05` é só `origem ≠ destino`

**Status:** Aceita e congelada (`spec.md` RC-02, RC-03, §9).

## Contexto

Em versões anteriores da análise deste projeto, `ALTERACAO_ESTRUTURA` foi interpretada como o reparentamento de nós da árvore organizacional (`EstruturaOrganizacional.estrutura_pai_id`), e `AE05` chegou a ser especificada como uma regra de detecção de ciclo hierárquico sobre essa árvore — por analogia com `TG05` (troca de gestor).

Essa interpretação está errada para o domínio deste desafio: o campo `EstruturaOrganizacional.estrutura_pai_id` existe para representar a hierarquia organizacional (ex.: relatórios, indicadores futuros), mas o **evento de negócio** `ALTERACAO_ESTRUTURA` é a movimentação de uma **pessoa** entre estruturas — análogo a uma transferência de departamento, só que no nível de estrutura. Mover um colaborador de uma estrutura para outra nunca cria um ciclo na árvore, porque colaboradores não são nós da árvore.

## Decisão

- `ALTERACAO_ESTRUTURA` é a movimentação de um colaborador entre estruturas organizacionais. Não é o reparentamento de nós.
- `AE05` é exclusivamente `estrutura_origem_id == estrutura_destino_id`. Nenhuma regra de ciclo organizacional existe em `ALTERACAO_ESTRUTURA`, sob nenhum código.
- Ciclo hierárquico é regra real **exclusivamente** em `TG05` (troca de gestor), onde faz sentido: um gestor pode, de fato, entrar na cadeia de comando de quem o nomeou.
- O módulo `validation/estrutura.py` não lê `estrutura_pai_id` em nenhum ponto — nem para AE05, nem para qualquer outra regra.
- Uma extensão futura documentada (`AEX02`) cobre eventual validação hierárquica sobre a árvore, mas não é implementada no MVP.

Ver `specs/001-movimentacoes/spec.md` §9 ("Guarda anti-regressão de AE05") para as afirmações normativas completas, os critérios de aceite dedicados (CA-025, CA-026, CA-028) e os cenários de teste (CN-A01, CN-A02, CN-A04) que sustentam esta decisão.

## Consequências

- **Positivas:** o motor de validação de `ALTERACAO_ESTRUTURA` fica simples e simétrico às demais movimentações de origem/destino (T, CC) — sem necessidade de carregar ou percorrer a árvore, sem risco de laço infinito, sem acoplamento entre duas regras de domínios diferentes (mobilidade de pessoa vs. topologia organizacional).
- **Negativa:** se o negócio um dia precisar impedir reparentamentos que criem ciclo na árvore em si, isso é um problema diferente — endereçado pela extensão `AEX02`, não por `AE05`.
- **Risco monitorado:** por já ter sido especificada incorretamente uma vez, esta decisão tem proteção reforçada — dois testes comportamentais dedicados (`test_ae_destino_ancestral_valida`, `test_ae_destino_descendente_valida`) que falham imediatamente se alguém reintroduzir verificação de ciclo em `AE05`.
