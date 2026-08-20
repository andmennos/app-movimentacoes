"""`motivoResumo` — spec.md §8/plan.md §13. Uma única função monta o resumo a
partir do estado real (status, última validação, aprovações pendentes/
reprovadas) — nunca uma string fixa por status, nunca lógica no Angular.

Reaproveita `processing.approval_gate`/`validation.aprovacoes` (mesma fonte
das exigências e dos impedimentos do detalhe) em vez de reimplementar a
matriz de aprovações aqui.
"""

from __future__ import annotations

from app.models import StatusMovimentacao
from app.validation.aprovacoes import exigencias_para
from app.validation.types import EstadoAprovacao, ValidationContext


def _tipos_pendentes(ctx: ValidationContext) -> list[str]:
    decididos = {a.tipo: a.estado for a in ctx.aprovacoes}
    return [
        e.tipo.value
        for e in exigencias_para(ctx)
        if decididos.get(e.tipo, EstadoAprovacao.PENDENTE) == EstadoAprovacao.PENDENTE
    ]


def _primeira_reprovada(ctx: ValidationContext):
    tipos_exigidos = {e.tipo for e in exigencias_para(ctx)}
    for aprovacao in ctx.aprovacoes:
        if aprovacao.tipo in tipos_exigidos and aprovacao.estado == EstadoAprovacao.REPROVADA:
            return aprovacao
    return None


def montar_motivo_resumo(
    status: StatusMovimentacao,
    ctx: ValidationContext,
    total_inconsistencias_ultima_validacao: int | None,
) -> str:
    if status == StatusMovimentacao.APROVADA:
        return "Movimentação efetivada."

    if status == StatusMovimentacao.REPROVADA:
        n = total_inconsistencias_ultima_validacao or 0
        plural = "" if n == 1 else "s"
        return f"Validação encontrou {n} inconsistência{plural}."

    if status == StatusMovimentacao.BLOQUEADA:
        reprovada = _primeira_reprovada(ctx)
        if reprovada is None:
            return "Bloqueada: aprovação reprovada."
        quem = f" por {reprovada.aprovador_nome}" if reprovada.aprovador_nome else ""
        return f"Bloqueada: {reprovada.tipo.value} reprovada{quem}."

    if status == StatusMovimentacao.AGUARDANDO_APROVACAO:
        pendentes = _tipos_pendentes(ctx)
        if not pendentes:
            return "Aguardando aprovação."
        return f"Aguardando aprovação: {', '.join(pendentes)}."

    # PENDENTE: aprovações concluídas, processamento final ainda não
    # concluiu — spec RC-24 nunca confunde com AGUARDANDO_APROVACAO.
    return "Processamento pendente."
