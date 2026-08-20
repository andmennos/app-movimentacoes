"""Promoção — P01 a P09 (spec.md §10.3, revisão 2026-08-19). Exatamente 9 regras.

`P01` é "cargo de destino existe" — não "colaborador ativo". Essa regra foi
removida por duplicar G02 (decisão PA-01 = B) e não existe neste módulo.

P03/P07/P08/P09 (revisão): trilha sequencial por família (`ordem_progressao`),
mesma família de cargo, intervalo mínimo de 6 meses-calendário desde a última
promoção efetivada, e capacidade orçamentária do centro de custo atual.
Seguindo o padrão de pré-condição já usado por P02/P06, P03/P07/P08/P09 não
avaliam nada quando `cargo_destino` é `None` (P01 já reportou)."""

from __future__ import annotations

import calendar

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


def p03_proximo_passo_da_trilha(ctx: ValidationContext) -> list[Inconsistencia]:
    """spec.md §10.3/plan.md §11.2 — `ordem_progressao` é a fonte de
    verdade, não `nivel`: o destino precisa ser exatamente a próxima
    posição da trilha (`atual + 1`), nunca um salto."""
    if ctx.cargo_destino is None or ctx.cargo_atual is None:  # P01 passou e cargo_atual conhecido
        return []
    atual = ctx.cargo_atual.ordem_progressao
    destino = ctx.cargo_destino.ordem_progressao
    if atual is None or destino is None or destino != atual + 1:
        return [Inconsistencia("P03", "Cargo de destino não é o próximo passo da trilha de progressão")]
    return []


def p04_aprovacao_gestor(ctx: ValidationContext) -> list[Inconsistencia]:
    for tipo in (TipoAprovacao.GESTOR_ORIGEM, TipoAprovacao.GESTOR_SUPERIOR, TipoAprovacao.GESTOR_RH):
        if any(a.tipo == tipo for a in ctx.aprovacoes):
            return emitir_se_nao_integra(
                ctx, tipo, "P04", "Aprovação hierárquica ausente / aprovador inválido"
            )
    return emitir_se_nao_integra(
        ctx, TipoAprovacao.GESTOR_ORIGEM, "P04", "Aprovação hierárquica ausente / aprovador inválido"
    )


def p05_aprovacao_rh(ctx: ValidationContext) -> list[Inconsistencia]:
    for tipo in (TipoAprovacao.RH, TipoAprovacao.GESTOR_RH):
        if any(a.tipo == tipo for a in ctx.aprovacoes):
            return emitir_se_nao_integra(ctx, tipo, "P05", "Aprovação de RH ausente / aprovador inválido")
    return emitir_se_nao_integra(ctx, TipoAprovacao.RH, "P05", "Aprovação de RH ausente / aprovador inválido")


def p06_aprovacao_superior(ctx: ValidationContext) -> list[Inconsistencia]:
    """spec.md §10.3 (P06) — com `cargo_destino.aprovacao_adicional`
    definido, o bundle completo precisa estar íntegro: a etapa
    GERENCIA/DIRETORIA (liderança concreta) *e* a etapa
    `GESTOR_RH_ADICIONAL` (perfil RH_GESTOR) — spec.md RC-36/T-75, não
    apenas a primeira das duas."""
    if ctx.cargo_destino is None:  # pré-condição: P01 passou
        return []
    nivel_exigido = aprovacao_adicional_promocao(ctx)
    if nivel_exigido is None:
        return []
    inconsistencias = emitir_se_nao_integra(
        ctx, nivel_exigido, "P06", f"Aprovação de {nivel_exigido.value} ausente / aprovador inválido"
    )
    inconsistencias += emitir_se_nao_integra(
        ctx,
        TipoAprovacao.GESTOR_RH_ADICIONAL,
        "P06",
        "Aprovação de GESTOR_RH_ADICIONAL ausente / aprovador inválido",
    )
    return inconsistencias


def p07_mesma_familia_cargo(ctx: ValidationContext) -> list[Inconsistencia]:
    if ctx.cargo_destino is None or ctx.cargo_atual is None:  # pré-condição: P01 passou
        return []
    if ctx.cargo_atual.familia_cargo != ctx.cargo_destino.familia_cargo:
        return [Inconsistencia("P07", "Cargo de destino pertence a outra família de carreira")]
    return []


def _ultimo_dia_do_mes(ano: int, mes: int) -> int:
    return calendar.monthrange(ano, mes)[1]


def _adicionar_meses(momento, meses: int):
    total = momento.month - 1 + meses
    ano = momento.year + total // 12
    mes = total % 12 + 1
    dia = min(momento.day, _ultimo_dia_do_mes(ano, mes))
    return momento.replace(year=ano, month=mes, day=dia)


def p08_intervalo_minimo_desde_ultima_promocao(ctx: ValidationContext) -> list[Inconsistencia]:
    """spec.md §9.3/§11.4 — 6 meses-calendário, não uma contagem fixa de
    dias. Sem promoção efetivada anterior, a regra passa."""
    if ctx.cargo_destino is None:  # pré-condição: P01 passou
        return []
    if ctx.data_ultima_promocao_efetivada is None:
        return []
    if ctx.movimentacao is None or ctx.movimentacao.data_solicitacao is None:
        return []
    liberado_em = _adicionar_meses(ctx.data_ultima_promocao_efetivada, 6)
    if ctx.movimentacao.data_solicitacao < liberado_em:
        return [Inconsistencia("P08", "Intervalo mínimo de 6 meses desde a última promoção ainda não decorrido")]
    return []


def p09_orcamento_centro_custo(ctx: ValidationContext) -> list[Inconsistencia]:
    """spec.md §9.3/§11.5 — delta = max(custo_destino - custo_atual, 0);
    reprova quando o delta excede o saldo disponível do CC atual."""
    if ctx.cargo_destino is None:  # pré-condição: P01 passou
        return []
    if ctx.centro_custo_origem is None:
        return []
    custo_atual = ctx.cargo_atual.custo_mensal_referencia if ctx.cargo_atual else 0
    delta = max(ctx.cargo_destino.custo_mensal_referencia - custo_atual, 0)
    saldo = ctx.centro_custo_origem.orcamento_mensal - ctx.centro_custo_origem.custo_comprometido
    if delta > saldo:
        return [Inconsistencia("P09", "Centro de custo não possui saldo orçamentário suficiente")]
    return []


REGRAS_PROMOCAO = [
    p01_cargo_destino_existe,
    p02_cargo_destino_ativo,
    p03_proximo_passo_da_trilha,
    p04_aprovacao_gestor,
    p05_aprovacao_rh,
    p06_aprovacao_superior,
    p07_mesma_familia_cargo,
    p08_intervalo_minimo_desde_ultima_promocao,
    p09_orcamento_centro_custo,
]
