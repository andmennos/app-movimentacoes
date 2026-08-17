"""Exigências de aprovação por tipo e verificação de integridade — spec.md §5.

Fonte única da verdade: nenhuma regra específica de tipo decide, por conta
própria, quais aprovações são exigidas nem como avaliar integridade. Todas
chamam as funções deste módulo.
"""

from __future__ import annotations

from app.validation.types import (
    EstadoAprovacao,
    Inconsistencia,
    TipoAprovacao,
    TipoMovimentacao,
    ValidationContext,
)

EXIGENCIAS_BASE_POR_TIPO: dict[TipoMovimentacao, list[TipoAprovacao]] = {
    TipoMovimentacao.TRANSFERENCIA: [TipoAprovacao.GESTOR_ORIGEM, TipoAprovacao.GESTOR_DESTINO],
    TipoMovimentacao.PROMOCAO: [TipoAprovacao.GESTOR_ORIGEM, TipoAprovacao.RH],
    TipoMovimentacao.TROCA_GESTOR: [TipoAprovacao.GESTOR_ORIGEM, TipoAprovacao.GESTOR_DESTINO],
    TipoMovimentacao.MUDANCA_CENTRO_CUSTO: [TipoAprovacao.GESTOR_DESTINO],
    TipoMovimentacao.ALTERACAO_ESTRUTURA: [TipoAprovacao.GESTOR_ORIGEM],
}


def aprovacao_adicional_promocao(ctx: ValidationContext) -> TipoAprovacao | None:
    """A aprovação extra de PROMOCAO (spec §5.3.1) — GERENCIA/DIRETORIA quando
    `cargo_destino.aprovacao_adicional` não é nulo. `None` nos demais tipos ou
    quando não aplicável."""
    if ctx.movimentacao is None or ctx.movimentacao.tipo != TipoMovimentacao.PROMOCAO:
        return None
    if ctx.cargo_destino is None or ctx.cargo_destino.aprovacao_adicional is None:
        return None
    return TipoAprovacao(ctx.cargo_destino.aprovacao_adicional.value)


def tipos_exigidos(ctx: ValidationContext) -> list[TipoAprovacao]:
    if ctx.movimentacao is None:
        return []
    tipos = list(EXIGENCIAS_BASE_POR_TIPO.get(ctx.movimentacao.tipo, []))
    extra = aprovacao_adicional_promocao(ctx)
    if extra is not None:
        tipos.append(extra)
    return tipos


def _linha(ctx: ValidationContext, tipo: TipoAprovacao):
    for aprovacao in ctx.aprovacoes:
        if aprovacao.tipo == tipo:
            return aprovacao
    return None


def _responsavel_esperado_valido(ctx: ValidationContext, tipo: TipoAprovacao) -> bool:
    """Condição 3 de spec §5.3 — aplica-se apenas a GESTOR_ORIGEM/GESTOR_DESTINO.
    O responsável esperado é resolvido pelo `services/` conforme spec §5.3.1 e
    chega pronto em `ctx.responsaveis_derivados`."""
    if tipo not in (TipoAprovacao.GESTOR_ORIGEM, TipoAprovacao.GESTOR_DESTINO):
        return True
    responsavel = ctx.responsaveis_derivados.get(tipo.value)
    return responsavel is not None and responsavel.ativo


def integra(ctx: ValidationContext, tipo: TipoAprovacao) -> bool:
    linha = _linha(ctx, tipo)
    if linha is None:
        return False
    if linha.estado in (EstadoAprovacao.APROVADA, EstadoAprovacao.REPROVADA):
        if not linha.aprovador_id or not linha.aprovador_ativo:
            return False
    return _responsavel_esperado_valido(ctx, tipo)


def mensagem_generica(tipo: TipoAprovacao) -> str:
    return f"Aprovação {tipo.value} ausente / aprovador inválido"


def emitir_se_nao_integra(
    ctx: ValidationContext, tipo: TipoAprovacao, codigo: str, mensagem: str | None = None
) -> list[Inconsistencia]:
    """Bloco de construção usado pelas regras Txx/Pxx/TGxx/CCxx/AExx de aprovação:
    avalia a integridade de `tipo` e, se falhar, emite uma Inconsistencia sob o
    código público da regra do tipo (spec §5.3) — nunca um código próprio."""
    if integra(ctx, tipo):
        return []
    return [Inconsistencia(codigo, mensagem or mensagem_generica(tipo))]
