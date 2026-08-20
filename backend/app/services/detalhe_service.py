"""Compõe impedimentos e estado de processamento exibidos no detalhe
(`GET /movimentacoes/{id}` — spec.md §8.2/T-53). O backend é a única fonte de
`podeValidarManualmente` (RC-13); o Angular nunca deriva elegibilidade a
partir do status.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app.config import settings
from app.models import JobValidacao, Movimentacao, StatusJob, StatusMovimentacao
from app.processing.approval_gate import Impedimento, calcular_impedimentos
from app.repositories import job_validacao_repository as job_repo
from app.services.movimentacao_service import montar_contexto

ESTADOS_BLOQUEIO_APROVACAO = (StatusMovimentacao.BLOQUEADA, StatusMovimentacao.AGUARDANDO_APROVACAO)
ESTADOS_TERMINAIS_VALIDACAO = (StatusMovimentacao.APROVADA, StatusMovimentacao.REPROVADA)


@dataclass
class Processamento:
    estado: str | None
    pode_validar_manualmente: bool
    motivo_validacao_manual: str | None


def _job_processando_saudavel(job: JobValidacao, agora: datetime) -> bool:
    if job.status != StatusJob.PROCESSANDO:
        return False
    if job.iniciado_em is None:
        return True
    limite = agora - timedelta(seconds=settings.job_stale_after_seconds)
    return job.iniciado_em >= limite


def compor(session: Session, movimentacao: Movimentacao, agora: datetime) -> tuple[list[Impedimento], Processamento]:
    if movimentacao.status in ESTADOS_BLOQUEIO_APROVACAO:
        ctx = montar_contexto(session, movimentacao)
        impedimentos = calcular_impedimentos(ctx)
        motivo = "; ".join(i.mensagem for i in impedimentos) or "Aprovação exigida ainda não concluída."
        return impedimentos, Processamento(estado=None, pode_validar_manualmente=False, motivo_validacao_manual=motivo)

    job = job_repo.buscar_por_movimentacao(session, movimentacao.id)

    if movimentacao.status in ESTADOS_TERMINAIS_VALIDACAO:
        estado = job.status.value if job else None
        return [], Processamento(estado=estado, pode_validar_manualmente=False, motivo_validacao_manual=None)

    # PENDENTE: todas as aprovações concluídas, processamento final ainda não concluído.
    if job is None:
        return [], Processamento(estado=None, pode_validar_manualmente=True, motivo_validacao_manual=None)

    if _job_processando_saudavel(job, agora):
        return [], Processamento(
            estado=job.status.value,
            pode_validar_manualmente=False,
            motivo_validacao_manual="Processamento automático em andamento.",
        )

    return [], Processamento(estado=job.status.value, pode_validar_manualmente=True, motivo_validacao_manual=None)
