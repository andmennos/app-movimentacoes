"""Troca de gestor — TG01 a TG06 (spec.md §6.5). Exatamente 6 regras."""

from __future__ import annotations

from app.validation.aprovacoes import emitir_se_nao_integra
from app.validation.types import Inconsistencia, TipoAprovacao, ValidationContext

LIMITE_PROFUNDIDADE = 1000
"""Protege TG05 contra ciclo já presente nos dados (spec §6.5). Independente
de qualquer configuração da aplicação — validation/ não importa app.config."""


def tg01_novo_gestor_existe(ctx: ValidationContext) -> list[Inconsistencia]:
    if ctx.gestor_destino is None:
        return [Inconsistencia("TG01", "Novo gestor não encontrado")]
    return []


def tg02_novo_gestor_ativo(ctx: ValidationContext) -> list[Inconsistencia]:
    if ctx.gestor_destino is None:  # pré-condição: TG01 passou
        return []
    if not ctx.gestor_destino.ativo:
        return [Inconsistencia("TG02", "Novo gestor não está ativo")]
    return []


def tg03_funcao_compativel(ctx: ValidationContext) -> list[Inconsistencia]:
    if ctx.gestor_destino is None:  # pré-condição: TG01 passou
        return []
    cargo = ctx.gestor_destino.cargo
    if cargo is None or not cargo.permite_gestao:
        return [Inconsistencia("TG03", "Novo gestor não possui cargo com função de gestão")]
    return []


def tg04_nao_e_proprio_gestor(ctx: ValidationContext) -> list[Inconsistencia]:
    if ctx.colaborador is None or ctx.gestor_destino is None:  # G01 e TG01 passaram
        return []
    if ctx.gestor_destino.id == ctx.colaborador.id:
        return [Inconsistencia("TG04", "Colaborador não pode ser seu próprio gestor")]
    return []


def tg05_sem_ciclo_hierarquico(ctx: ValidationContext) -> list[Inconsistencia]:
    if ctx.colaborador is None or ctx.gestor_destino is None:  # G01 e TG01 passaram
        return []

    visitados: set[int] = set()
    atual_id: int | None = ctx.gestor_destino.id
    profundidade = 0

    while atual_id is not None and profundidade < LIMITE_PROFUNDIDADE:
        if atual_id == ctx.colaborador.id:
            return [Inconsistencia("TG05", "A alteração criaria um ciclo hierárquico")]
        if atual_id in visitados:
            break  # ciclo pré-existente nos dados — interrompe sem lançar exceção
        visitados.add(atual_id)
        no = ctx.cadeia_hierarquica.get(atual_id)
        atual_id = no.gestor_id if no is not None else None
        profundidade += 1

    return []


def tg06_aprovacoes_integras(ctx: ValidationContext) -> list[Inconsistencia]:
    inconsistencias: list[Inconsistencia] = []
    for tipo in (TipoAprovacao.GESTOR_ORIGEM, TipoAprovacao.GESTOR_DESTINO):
        inconsistencias.extend(emitir_se_nao_integra(ctx, tipo, "TG06"))
    return inconsistencias


REGRAS_TROCA_GESTOR = [
    tg01_novo_gestor_existe,
    tg02_novo_gestor_ativo,
    tg03_funcao_compativel,
    tg04_nao_e_proprio_gestor,
    tg05_sem_ciclo_hierarquico,
    tg06_aprovacoes_integras,
]
