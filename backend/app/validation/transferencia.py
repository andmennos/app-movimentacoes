"""Transferência — T01 a T06 (spec.md §6.3). Exatamente 6 regras."""

from __future__ import annotations

from app.validation.aprovacoes import emitir_se_nao_integra
from app.validation.types import Inconsistencia, TipoAprovacao, ValidationContext


def t01_departamento_origem_existe(ctx: ValidationContext) -> list[Inconsistencia]:
    if ctx.departamento_origem is None:
        return [Inconsistencia("T01", "Departamento de origem não encontrado")]
    return []


def t02_departamento_origem_ativo(ctx: ValidationContext) -> list[Inconsistencia]:
    if ctx.departamento_origem is None:  # pré-condição: T01 passou
        return []
    if not ctx.departamento_origem.ativo:
        return [Inconsistencia("T02", "Departamento de origem não está ativo")]
    return []


def t03_departamento_destino_existe(ctx: ValidationContext) -> list[Inconsistencia]:
    if ctx.departamento_destino is None:
        return [Inconsistencia("T03", "Departamento de destino não encontrado")]
    return []


def t04_departamento_destino_ativo(ctx: ValidationContext) -> list[Inconsistencia]:
    if ctx.departamento_destino is None:  # pré-condição: T03 passou
        return []
    if not ctx.departamento_destino.ativo:
        return [Inconsistencia("T04", "Departamento de destino não está ativo")]
    return []


def t05_origem_diferente_destino(ctx: ValidationContext) -> list[Inconsistencia]:
    if ctx.departamento_origem is None or ctx.departamento_destino is None:  # T01 e T03 passaram
        return []
    if ctx.departamento_origem.id == ctx.departamento_destino.id:
        return [Inconsistencia("T05", "Departamento de origem e destino são iguais")]
    return []


def t06_aprovacoes_integras(ctx: ValidationContext) -> list[Inconsistencia]:
    inconsistencias: list[Inconsistencia] = []
    for tipo in (TipoAprovacao.GESTOR_ORIGEM, TipoAprovacao.GESTOR_DESTINO):
        inconsistencias.extend(emitir_se_nao_integra(ctx, tipo, "T06"))
    return inconsistencias


REGRAS_TRANSFERENCIA = [
    t01_departamento_origem_existe,
    t02_departamento_origem_ativo,
    t03_departamento_destino_existe,
    t04_departamento_destino_ativo,
    t05_origem_diferente_destino,
    t06_aprovacoes_integras,
]
