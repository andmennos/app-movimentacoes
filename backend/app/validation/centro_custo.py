"""Mudança de centro de custo — CC01 a CC06 (spec.md §6.6). Exatamente 6 regras."""

from __future__ import annotations

from app.validation.aprovacoes import emitir_se_nao_integra
from app.validation.types import Inconsistencia, TipoAprovacao, ValidationContext


def cc01_centro_custo_origem_existe(ctx: ValidationContext) -> list[Inconsistencia]:
    if ctx.centro_custo_origem is None:
        return [Inconsistencia("CC01", "Centro de custo de origem não encontrado")]
    return []


def cc02_centro_custo_origem_ativo(ctx: ValidationContext) -> list[Inconsistencia]:
    if ctx.centro_custo_origem is None:  # pré-condição: CC01 passou
        return []
    if not ctx.centro_custo_origem.ativo:
        return [Inconsistencia("CC02", "Centro de custo de origem não está ativo")]
    return []


def cc03_centro_custo_destino_existe(ctx: ValidationContext) -> list[Inconsistencia]:
    if ctx.centro_custo_destino is None:
        return [Inconsistencia("CC03", "Centro de custo de destino não encontrado")]
    return []


def cc04_centro_custo_destino_ativo(ctx: ValidationContext) -> list[Inconsistencia]:
    if ctx.centro_custo_destino is None:  # pré-condição: CC03 passou
        return []
    if not ctx.centro_custo_destino.ativo:
        return [Inconsistencia("CC04", "Centro de custo de destino não está ativo")]
    return []


def cc05_origem_diferente_destino(ctx: ValidationContext) -> list[Inconsistencia]:
    if ctx.centro_custo_origem is None or ctx.centro_custo_destino is None:  # CC01 e CC03 passaram
        return []
    if ctx.centro_custo_origem.id == ctx.centro_custo_destino.id:
        return [Inconsistencia("CC05", "Centro de custo de origem e destino são iguais")]
    return []


def cc06_aprovacao_responsavel(ctx: ValidationContext) -> list[Inconsistencia]:
    return emitir_se_nao_integra(
        ctx,
        TipoAprovacao.GESTOR_DESTINO,
        "CC06",
        "Aprovação do responsável pelo centro de custo ausente / inválida",
    )


REGRAS_CENTRO_CUSTO = [
    cc01_centro_custo_origem_existe,
    cc02_centro_custo_origem_ativo,
    cc03_centro_custo_destino_existe,
    cc04_centro_custo_destino_ativo,
    cc05_origem_diferente_destino,
    cc06_aprovacao_responsavel,
]
