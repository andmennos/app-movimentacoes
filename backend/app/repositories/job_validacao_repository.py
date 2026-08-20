"""Repositório da fila local (`JobValidacao`) — spec.md §4.1/§7.2-§7.4
(revisão 2026-08-18: T-50/T-52).

Diferente da auditoria de validação, `JobValidacao` não é append-only: é uma
máquina de estados (`PENDENTE → PROCESSANDO → CONCLUIDO|ERRO`) mutável por
natureza — representa a execução técnica, não o resultado de negócio.

`tentar_adquirir` é a única mutação que confirma sua própria transação de
imediato — é o "compare-and-set" que impede duas origens (Worker e validação
manual) de processarem o mesmo job ao mesmo tempo (spec §7.3, RF-19/RF-20,
CN-Q11/CN-Q12). As demais mutações não commitam por conta própria: o
orquestrador (`processing/orchestrator.py`) decide a fronteira de transação
(INV-08) — um único commit por resultado de processamento.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.models import JobValidacao, StatusJob


def criar(session: Session, movimentacao_id: int, criado_em: datetime) -> JobValidacao:
    job = JobValidacao(
        movimentacao_id=movimentacao_id, status=StatusJob.PENDENTE, tentativas=0, criado_em=criado_em
    )
    session.add(job)
    session.flush()
    return job


def buscar_por_movimentacao(session: Session, movimentacao_id: int) -> JobValidacao | None:
    consulta = select(JobValidacao).where(JobValidacao.movimentacao_id == movimentacao_id)
    return session.scalars(consulta).one_or_none()


def obter_ou_criar(session: Session, movimentacao_id: int, agora: datetime) -> JobValidacao:
    """RF-19 — se já existe job (qualquer status) para a movimentação,
    reaproveita-o; nunca cria um segundo (a unique constraint em
    `movimentacao_id` garante isso mesmo sob corrida)."""
    job = buscar_por_movimentacao(session, movimentacao_id)
    if job is None:
        job = criar(session, movimentacao_id, agora)
    return job


def existe_para_movimentacao(session: Session, movimentacao_id: int) -> bool:
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


def buscar_processando_stale(session: Session, limite: datetime) -> list[JobValidacao]:
    """T-52 — jobs `PROCESSANDO` cujo `iniciado_em` é anterior a `limite`
    (tipicamente `agora - JOB_STALE_AFTER_SECONDS`): o processo que os
    adquiriu provavelmente morreu no meio da execução."""
    consulta = select(JobValidacao).where(
        JobValidacao.status == StatusJob.PROCESSANDO,
        JobValidacao.iniciado_em.is_not(None),
        JobValidacao.iniciado_em < limite,
    )
    return list(session.scalars(consulta))


def tentar_adquirir(session: Session, job_id: int, agora: datetime) -> bool:
    """Aquisição condicional (compare-and-set): só marca `PROCESSANDO` se o
    job ainda estiver `PENDENTE` no banco neste exato instante — impede que
    Worker e validação manual processem o mesmo job ao mesmo tempo. Confirma
    a própria transação imediatamente para que a checagem seja durável e
    visível para qualquer outra origem que tente adquirir o mesmo job."""
    resultado = session.execute(
        update(JobValidacao)
        .where(JobValidacao.id == job_id, JobValidacao.status == StatusJob.PENDENTE)
        .values(status=StatusJob.PROCESSANDO, tentativas=JobValidacao.tentativas + 1, iniciado_em=agora)
    )
    session.commit()
    return resultado.rowcount == 1


def reabrir(session: Session, job: JobValidacao) -> None:
    """plan.md §11.3 — um job `ERRO` pode ser reaberto para nova tentativa
    quando o gate confirma que a movimentação continua apta."""
    job.status = StatusJob.PENDENTE


def marcar_concluido(session: Session, job: JobValidacao, agora: datetime) -> None:
    job.status = StatusJob.CONCLUIDO
    job.finalizado_em = agora


def marcar_para_nova_tentativa(session: Session, job: JobValidacao, mensagem_erro: str) -> None:
    """Falha técnica, mas ainda dentro do limite de tentativas: volta para
    `PENDENTE` para ser reprocessado; não é terminal, `finalizado_em`
    permanece nulo."""
    job.status = StatusJob.PENDENTE
    job.ultimo_erro = mensagem_erro


def marcar_erro_terminal(session: Session, job: JobValidacao, mensagem_erro: str, agora: datetime) -> None:
    """Limite de tentativas esgotado: estado terminal `ERRO`."""
    job.status = StatusJob.ERRO
    job.ultimo_erro = mensagem_erro
    job.finalizado_em = agora


def marcar_recuperado(session: Session, job: JobValidacao, agora: datetime, limite_tentativas: int) -> StatusJob:
    """T-52 — recupera um job `PROCESSANDO` stale: volta para `PENDENTE` se
    ainda há tentativa disponível, ou vai direto para `ERRO` se o limite já
    estava esgotado quando o processo morreu."""
    if job.tentativas >= limite_tentativas:
        job.status = StatusJob.ERRO
        job.finalizado_em = agora
    else:
        job.status = StatusJob.PENDENTE
    return job.status
