# ADR-0006 — Remoção de "P01 — colaborador ativo" por duplicar `G02`

**Status:** Aceita (decisão PA-01 = B).

## Contexto

Toda movimentação tem um colaborador, e toda movimentação exige que esse colaborador esteja ativo — isso já é garantido pela regra geral `G02` (`Colaborador está ativo`), que roda para os 5 tipos antes de qualquer regra específica. Em uma versão anterior do catálogo de `PROMOCAO`, havia uma regra específica adicional, também chamada "colaborador ativo", ocupando o código `P01`.

Essa regra específica é estritamente redundante: `G02` já cobre o mesmo caso, na mesma execução, antes de `P01` ser avaliada. Mantê-la como regra separada significaria (a) dois códigos possíveis para o mesmo defeito de dado, dependendo de qual regra "chegou primeiro", o que quebra o contrato de "código é contrato público, não reciclado" se um dia um dos dois for removido; ou (b) uma inconsistência duplicada na resposta (`G02` e `P01` no mesmo `inconsistencias[]`), que não agrega informação e obriga o cliente a tratar dois códigos como se fossem um.

## Decisão

Remover a regra específica de `PROMOCAO`. O código `P01` é **reatribuído** — não para "colaborador ativo", mas para "cargo de destino existe" (a primeira regra específica de fato necessária para `PROMOCAO`, que não tem equivalente em `G`).

> Nota sobre a convenção "código nunca é reciclado" (`spec.md` §6.1): essa convenção vale a partir do congelamento do catálogo — ela protege contra reatribuir, no futuro, um código que já foi publicado em produção. Como a regra antiga de `P01` nunca foi implementada nem publicada (foi identificada e corrigida ainda na fase de revisão do SDD, antes de qualquer código ser escrito), reatribuir `P01` aqui é uma correção de rascunho, não uma reciclagem de contrato público.

## Consequências

- **Positiva:** o catálogo de `PROMOCAO` fica com exatamente 6 regras não redundantes, cada uma cobrindo um defeito de dado distinto (`spec.md` §6.4 traz a nota explícita: *"P01 — colaborador ativo não existe. Foi removido por duplicar G02"*).
- **Positiva:** qualquer defeito de "colaborador inativo" aparece sob um único código (`G02`), em qualquer tipo de movimentação — consistência entre os 5 tipos.
- **Verificação:** `tests/validation/test_promocao.py` documenta explicitamente que `P01` é "cargo de destino existe", e o teste de arquitetura/catálogo confirma que o conjunto de 34 códigos não contém duplicação semântica entre gerais e específicas.
