# ADR-0002 — `Movimentacao` usa 10 FKs explícitas nullable, uma por par origem/destino, em vez de um modelo polimórfico

**Status:** Aceita.

## Contexto

`Movimentacao` precisa representar 5 tipos de movimentação, cada um com seu próprio par de campos origem/destino (departamento, cargo, gestor, centro de custo, estrutura). Duas abordagens foram consideradas:

1. **Campos polimórficos genéricos:** `entidade_origem_tipo` (string), `entidade_origem_id` (int), `entidade_destino_tipo`, `entidade_destino_id` — um único par de colunas reaproveitado para todos os tipos, com o significado dependendo de `entidade_origem_tipo`.
2. **10 FKs explícitas nullable:** `departamento_origem_id`, `departamento_destino_id`, `cargo_origem_id`, `cargo_destino_id`, `gestor_origem_id`, `gestor_destino_id`, `centro_custo_origem_id`, `centro_custo_destino_id`, `estrutura_origem_id`, `estrutura_destino_id` — uma coluna por combinação (tipo × origem/destino), nula para os tipos que não a usam.

## Decisão

Adotar a opção 2: 10 FKs explícitas e nullable.

## Alternativas consideradas e por que foram rejeitadas

**Campos polimórficos** economizariam colunas, mas trocam integridade referencial real por integridade validada em código: o banco não consegue garantir, via `FOREIGN KEY`, que `entidade_origem_id` aponta para a tabela certa quando o tipo é dinâmico. Toda consulta que precisa "resolver a entidade de origem" também precisa de um `switch` sobre `entidade_origem_tipo`, espalhando essa lógica por repositórios e serviços. Índices e `JOIN`s diretos deixam de ser triviais.

## Consequências

- **Positivas:** cada FK é uma `ForeignKey` real, validada pelo SQLite (`PRAGMA foreign_keys=ON`) e navegável por `JOIN` direto — inclusive via `joinedload` do SQLAlchemy, permitindo a carga em consulta única usada por `carregar_para_validacao` (ver `movimentacao_repository.py`). O schema é autoexplicativo: olhar as colunas da tabela já revela o modelo de domínio.
- **Negativa:** 10 colunas majoritariamente nulas por linha — mais colunas do que um modelo polimórfico teria. Aceitável neste volume (RNF-02: ~5.000/dia) e mais barato do que a complexidade que o polimorfismo introduziria em validação, teste e leitura.
- **Trade-off explícito:** a spec (`spec.md` §4.3) já assume esse modelo ao declarar "campos obrigatórios" e "campos que devem ser nulos" por tipo — o mapa de campos por tipo é, na prática, a regra de negócio que substitui o polimorfismo em tempo de execução.
