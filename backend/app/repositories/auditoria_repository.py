from collections.abc import Iterable
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.models import InconsistenciaAuditoria, ResultadoValidacao, Severidade, ValidacaoAuditoria
from app.validation.types import Inconsistencia

"""Repositório de auditoria — expõe apenas `criar` e `buscar_ultima`.

Não existe (e não deve existir) nenhum método de update ou delete: a auditoria
é append-only (RC-07, INV-08).
"""


def criar(
    session: Session,
    movimentacao_id: int,
    resultado: ResultadoValidacao,
    inconsistencias: Iterable[Inconsistencia],
    versao_motor: str,
    data_hora: datetime,
) -> ValidacaoAuditoria:
    inconsistencias = list(inconsistencias)
    auditoria = ValidacaoAuditoria(
        movimentacao_id=movimentacao_id,
        data_hora=data_hora,
        resultado=resultado,
        total_inconsistencias=len(inconsistencias),
        versao_motor=versao_motor,
    )
    auditoria.inconsistencias = [
        InconsistenciaAuditoria(
            codigo_regra=inc.codigo,
            mensagem=inc.mensagem,
            severidade=Severidade(inc.severidade.value),
        )
        for inc in inconsistencias
    ]
    session.add(auditoria)
    session.flush()
    return auditoria


def buscar_ultima(session: Session, movimentacao_id: int) -> ValidacaoAuditoria | None:
    consulta = (
        select(ValidacaoAuditoria)
        .where(ValidacaoAuditoria.movimentacao_id == movimentacao_id)
        .options(joinedload(ValidacaoAuditoria.inconsistencias))
        .order_by(ValidacaoAuditoria.data_hora.desc(), ValidacaoAuditoria.id.desc())
        .limit(1)
    )
    return session.scalars(consulta).unique().one_or_none()
