"""Repositório da fila local (`JobValidacao`) — spec.md §4.1, §7.5.

Diferente da auditoria de validação, `JobValidacao` **não** é append-only: é
uma máquina de estados (`PENDENTE → PROCESSANDO → CONCLUIDO|ERRO`) mutável
por natureza — representa a execução técnica, não o resultado de negócio.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import JobValidacao, StatusJob


def criar(session: Session, movimentacao_id: int, criado_em: datetime) -> JobValidacao:
    job = JobValidacao(
        movimentacao_id=movimentacao_id, status=StatusJob.PENDENTE, tentativas=0, criado_em=criado_em
    )
    session.add(job)
    session.flush()
    return job


def existe_para_movimentacao(session: Session, movimentacao_id: int) -> bool:
    """Base da idempotência do producer (INV-10): no máximo um job por
    movimentação no fluxo automático do MVP, independentemente do status
    atual do job."""
    consulta = select(JobValidacao.id).where(JobValidacao.movimentacao_id == movimentacao_id)
    return session.scalars(consulta).first() is not None


def buscar_pendente_mais_antigo(session: Session) -> JobValidacao | None:
    consulta = (
        select(JobValidacao)
        .where(JobValidacao.status == StatusJob.PENDENTE)
        .order_by(JobValidacao.criado_em.asc(), JobValidacao.id.asc())
        .limit(1)
    )
    return session.scalars(consulta).one_or_none()


def marcar_processando(session: Session, job: JobValidacao, agora: datetime) -> None:
    job.status = StatusJob.PROCESSANDO
    job.tentativas += 1
    job.iniciado_em = agora
    session.commit()


def marcar_concluido(session: Session, job: JobValidacao, agora: datetime) -> None:
    job.status = StatusJob.CONCLUIDO
    job.finalizado_em = agora
    session.commit()


def marcar_para_nova_tentativa(session: Session, job: JobValidacao, mensagem_erro: str) -> None:
    """Falha técnica, mas ainda dentro do limite de tentativas: volta para
    `PENDENTE` para ser reprocessado; não é terminal, `finalizado_em`
    permanece nulo."""
    job.status = StatusJob.PENDENTE
    job.ultimo_erro = mensagem_erro
    session.commit()


def marcar_erro_terminal(session: Session, job: JobValidacao, mensagem_erro: str, agora: datetime) -> None:
    """Limite de tentativas esgotado: estado terminal `ERRO`."""
    job.status = StatusJob.ERRO
    job.ultimo_erro = mensagem_erro
    job.finalizado_em = agora
    session.commit()
