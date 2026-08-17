# ADR-0007 — Exceção não tratada em uma regra não vira inconsistência de negócio; propaga como HTTP 500

**Status:** Aceita.

## Contexto

Uma versão anterior da análise deste projeto especificava que, se uma regra lançasse uma exceção inesperada durante `POST /validar`, o motor deveria capturá-la, convertê-la em uma inconsistência de código `SYS01` ("erro de sistema"), e continuar — a movimentação terminaria com `status = REPROVADA` como qualquer outra reprovação por regra de negócio.

Essa abordagem foi revertida durante a revisão do SDD por um motivo de segurança de dados: uma exceção interna é um **defeito do sistema** (bug de código, dado corrompido de um jeito que a regra não previu, falha de infraestrutura), não um **defeito da movimentação**. Se o motor a converte em inconsistência e segue o fluxo normal até persistir um resultado, um bug de código passa a **reprovar movimentações de RH que poderiam ser perfeitamente válidas** — e o usuário não tem como distinguir "esta movimentação tem um problema real" de "o sistema quebrou ao tentar validar". A validação, nesse caso, não foi de fato concluída; não existe resultado de negócio confiável para persistir.

## Decisão

- O motor (`validation/engine.py`) **não usa `try/except` por regra**. Uma exceção não tratada propaga imediatamente.
- `services/validacao_service.py` também não a captura — ela sobe até a camada HTTP.
- A API (`app/api/errors.py`) tem um handler para `Exception` genérica que responde **HTTP 500** com o contrato `{"erro": {"codigo": "ERRO_INTERNO", ...}}`.
- Como a exceção interrompe antes de `session.commit()`, nenhuma escrita parcial ocorre: nenhum `ValidacaoAuditoria` é criado, `Movimentacao.status` e `resultado_ultima_validacao` permanecem exatamente como estavam antes da chamada. `database.get_db` reverte a sessão (`rollback`) nesse caminho.
- **Não existe o código `SYS01`** em nenhum lugar do catálogo, do código ou da documentação deste projeto.

## Consequências

- **Positiva:** uma reprovação (`status = REPROVADA`) sempre significa "o motor rodou até o fim e encontrou um defeito real de dado ou de regra" — nunca "o motor quebrou no meio do caminho". Isso preserva a confiabilidade do resultado para quem toma decisão de RH a partir dele.
- **Positiva:** erros de infraestrutura/código ficam visíveis como o que são (500, investigável via logs — ver `docs/operations.md`), em vez de se disfarçarem de decisão de negócio.
- **Custo aceito:** o cliente da API precisa tratar 500 como um caso à parte (repetir a chamada, reportar ao suporte), em vez de tratá-lo uniformemente como "mais um código de inconsistência". Esse custo é pequeno e correto — 500 é, por definição em HTTP, "o servidor falhou em processar", uma categoria diferente de 200 com um resultado de negócio.
- **Verificado por teste:** `tests/engine/test_engine.py` (propagação da exceção), `tests/integracao/test_validacao_service.py` e `tests/api/test_validacao_api.py` (CA-024: nenhuma auditoria criada, nenhuma alteração de status, resposta 500 com o contrato de erro).
