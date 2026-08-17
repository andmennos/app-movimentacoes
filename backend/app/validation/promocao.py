"""Promoção — P01 a P06 (spec.md §6.4). Exatamente 6 regras.

`P01` é "cargo de destino existe" — não "colaborador ativo". Essa regra foi
removida por duplicar G02 (decisão PA-01 = B) e não existe neste módulo.
"""

from __future__ import annotations

from app.validation.aprovacoes import aprovacao_adicional_promocao, emitir_se_nao_integra
from app.validation.types import Inconsistencia, TipoAprovacao, ValidationContext


def p01_cargo_destino_existe(ctx: ValidationContext) -> list[Inconsistencia]:
    if ctx.cargo_destino is None:
        return [Inconsistencia("P01", "Cargo de destino não encontrado")]
    return []


def p02_cargo_destino_ativo(ctx: ValidationContext) -> list[Inconsistencia]:
    if ctx.cargo_destino is None:  # pré-condição: P01 passou
        return []
    if not ctx.cargo_destino.ativo:
        return [Inconsistencia("P02", "Cargo de destino não está ativo")]
    return []


def p03_nivel_superior(ctx: ValidationContext) -> list[Inconsistencia]:
    if ctx.cargo_destino is None or ctx.cargo_atual is None:  # P01 passou e cargo_atual conhecido
        return []
    if ctx.cargo_destino.nivel <= ctx.cargo_atual.nivel:
        return [Inconsistencia("P03", "Cargo de destino não possui nível superior ao cargo atual")]
    return []


def p04_aprovacao_gestor(ctx: ValidationContext) -> list[Inconsistencia]:
    return emitir_se_nao_integra(
        ctx, TipoAprovacao.GESTOR_ORIGEM, "P04", "Aprovação do gestor ausente / aprovador inválido"
    )


def p05_aprovacao_rh(ctx: ValidationContext) -> list[Inconsistencia]:
    return emitir_se_nao_integra(ctx, TipoAprovacao.RH, "P05", "Aprovação de RH ausente / aprovador inválido")


def p06_aprovacao_superior(ctx: ValidationContext) -> list[Inconsistencia]:
    if ctx.cargo_destino is None:  # pré-condição: P01 passou
        return []
    nivel_exigido = aprovacao_adicional_promocao(ctx)
    if nivel_exigido is None:
        return []
    return emitir_se_nao_integra(
        ctx, nivel_exigido, "P06", f"Aprovação de {nivel_exigido.value} ausente / aprovador inválido"
    )


REGRAS_PROMOCAO = [
    p01_cargo_destino_existe,
    p02_cargo_destino_ativo,
    p03_nivel_superior,
    p04_aprovacao_gestor,
    p05_aprovacao_rh,
    p06_aprovacao_superior,
]
