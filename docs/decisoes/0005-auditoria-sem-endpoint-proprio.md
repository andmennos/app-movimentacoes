# ADR-0005 — Auditoria é persistida e append-only, mas não tem endpoint nem tela próprios

**Status:** Aceita (RC-07, RC-08).

## Contexto

Toda execução de `POST /validar` precisa deixar rastro: o que foi encontrado, quando, com que versão do motor. Isso é a trilha de auditoria (`ValidacaoAuditoria` + `InconsistenciaAuditoria`). A pergunta de design foi: essa trilha deve ser consultável via API própria (`GET /auditorias`, `GET /movimentacoes/{id}/historico`) e ter uma tela de histórico no frontend?

## Decisão

Não. A auditoria é:

- **Persistida** — toda execução de `POST /validar` grava exatamente um `ValidacaoAuditoria` com N `InconsistenciaAuditoria` (INV-07), na mesma transação que atualiza a movimentação.
- **Append-only** — o repositório (`auditoria_repository.py`) expõe apenas `criar` e `buscar_ultima`. Não existe, e não deve existir, nenhum método de update ou delete (INV-08).
- **Exposta apenas indiretamente** — via `GET /movimentacoes/{id}`, que traz somente a **última** validação (RC-08). O histórico completo permanece no banco, acessível por quem tem acesso direto ao banco (ex.: investigação de incidente — ver `docs/operations.md`), mas não por um endpoint HTTP dedicado nem por uma tela.

Endpoint de auditoria e tela de histórico estão explicitamente fora de escopo do MVP (`spec.md` §13).

## Alternativas consideradas

Um endpoint `GET /movimentacoes/{id}/historico` foi cogitado, mas rejeitado para o MVP: não há requisito funcional que o exija (a experiência demonstrável do MVP pede apenas "consultar a última validação realizada" — `spec.md` §1.1, item 13), e adicioná-lo sem necessidade concreta contraria o princípio de "evitar complexidade que não contribua diretamente para os objetivos do case".

## Consequências

- **Positiva:** a superfície de API fica mínima (3 endpoints), com contrato claro. A auditoria completa não é descartada — apenas não é exposta por HTTP — o que preserva a possibilidade de adicionar esse endpoint depois sem migração de dado.
- **Positiva:** por ser append-only e nunca editável, a auditoria serve como fonte confiável para investigação de incidente sem risco de ter sido adulterada pela própria aplicação.
- **Gatilho de evolução:** se o negócio precisar de um relatório de histórico de validações, isso se torna um novo endpoint de leitura sobre uma tabela que já existe e já está correta — não uma mudança de modelo.

## Nota de atualização (2026-08-16 — ADR-0010)

Esta decisão permanece válida: nenhum endpoint novo foi criado e a auditoria continua exposta só indiretamente (RC-08). A única mudança é que o detalhe de uma solicitação `APROVADA` agora renderiza uma linha do tempo **client-side**, montada a partir de campos já retornados por `GET /movimentacoes/{id}` (aprovações + última validação), sem consultar auditoria histórica nem introduzir uma tabela ou rota nova. Ver ADR-0010 para o detalhamento e para o porquê de uma entrada dela ser deliberadamente fictícia.
