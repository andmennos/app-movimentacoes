"""Regras gerais — G01 a G04 (spec.md §6.2). Exatamente 4 regras.

Existência e atividade de departamento, cargo, centro de custo, estrutura e
gestor NÃO pertencem às gerais — vivem nas específicas de cada tipo.
"""

from __future__ import annotations

from app.validation.types import Inconsistencia, TipoMovimentacao, ValidationContext


def g01_colaborador_existe(ctx: ValidationContext) -> list[Inconsistencia]:
    if ctx.colaborador is None:
        return [Inconsistencia("G01", "Colaborador não encontrado")]
    return []


def g02_colaborador_ativo(ctx: ValidationContext) -> list[Inconsistencia]:
    if ctx.colaborador is None:  # pré-condição: G01 passou
        return []
    if not ctx.colaborador.ativo:
        return [Inconsistencia("G02", "Colaborador não está ativo")]
    return []


def g03_tipo_valido(ctx: ValidationContext) -> list[Inconsistencia]:
    if ctx.movimentacao is None:
        return []
    if not isinstance(ctx.movimentacao.tipo, TipoMovimentacao):
        return [Inconsistencia("G03", "Tipo de movimentação inválido")]
    return []


def g04_sem_conflito(ctx: ValidationContext) -> list[Inconsistencia]:
    if ctx.colaborador is None:  # pré-condição: G01 passou
        return []
    if ctx.conflito_mesmo_tipo_em_aberto:
        return [
            Inconsistencia(
                "G04", "Existe outra movimentação do mesmo tipo em aberto para este colaborador"
            )
        ]
    return []


REGRAS_GERAIS = [g01_colaborador_existe, g02_colaborador_ativo, g03_tipo_valido, g04_sem_conflito]
