"""Alteração de estrutura — AE01 a AE06 (spec.md §6.7). Exatamente 6 regras.

RC-02 / RC-03. `ALTERACAO_ESTRUTURA` move um colaborador entre estruturas —
não é o reparentamento de nós da árvore. `AE05` é `origem ≠ destino`.

Guarda anti-regressão (spec.md §9): este módulo NÃO referencia
`estrutura_pai_id` em nenhum ponto, e não existe, sob nenhum código, regra de
ciclo organizacional aqui. Ciclo é regra real exclusivamente em `TG05`
(troca_gestor.py). Não reintroduzir por inércia.
"""

from __future__ import annotations

from app.validation.aprovacoes import emitir_se_nao_integra
from app.validation.types import Inconsistencia, TipoAprovacao, ValidationContext


def ae01_estrutura_origem_existe(ctx: ValidationContext) -> list[Inconsistencia]:
    if ctx.estrutura_origem is None:
        return [Inconsistencia("AE01", "Estrutura de origem não encontrada")]
    return []


def ae02_estrutura_origem_ativa(ctx: ValidationContext) -> list[Inconsistencia]:
    if ctx.estrutura_origem is None:  # pré-condição: AE01 passou
        return []
    if not ctx.estrutura_origem.ativo:
        return [Inconsistencia("AE02", "Estrutura de origem não está ativa")]
    return []


def ae03_estrutura_destino_existe(ctx: ValidationContext) -> list[Inconsistencia]:
    if ctx.estrutura_destino is None:
        return [Inconsistencia("AE03", "Estrutura de destino não encontrada")]
    return []


def ae04_estrutura_destino_ativa(ctx: ValidationContext) -> list[Inconsistencia]:
    if ctx.estrutura_destino is None:  # pré-condição: AE03 passou
        return []
    if not ctx.estrutura_destino.ativo:
        return [Inconsistencia("AE04", "Estrutura de destino não está ativa")]
    return []


def ae05_origem_diferente_destino(ctx: ValidationContext) -> list[Inconsistencia]:
    """Origem ≠ destino. Nada além disso — nenhuma verificação de ancestralidade
    ou de ciclo. Ver guarda anti-regressão no cabeçalho do módulo."""
    if ctx.estrutura_origem is None or ctx.estrutura_destino is None:  # AE01 e AE03 passaram
        return []
    if ctx.estrutura_origem.id == ctx.estrutura_destino.id:
        return [Inconsistencia("AE05", "Estrutura de origem e destino são iguais")]
    return []


def ae06_aprovacoes_integras(ctx: ValidationContext) -> list[Inconsistencia]:
    return emitir_se_nao_integra(
        ctx, TipoAprovacao.GESTOR_ORIGEM, "AE06", "Aprovação do gestor ausente / aprovador inválido"
    )


REGRAS_ESTRUTURA = [
    ae01_estrutura_origem_existe,
    ae02_estrutura_origem_ativa,
    ae03_estrutura_destino_existe,
    ae04_estrutura_destino_ativa,
    ae05_origem_diferente_destino,
    ae06_aprovacoes_integras,
]
