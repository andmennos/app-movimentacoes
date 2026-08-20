from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.models import Aprovacao, EstadoAprovacao, TipoAprovacao


def listar_por_movimentacao(session: Session, movimentacao_id: int) -> list[Aprovacao]:
    consulta = (
        select(Aprovacao)
        .where(Aprovacao.movimentacao_id == movimentacao_id)
        .options(joinedload(Aprovacao.aprovador))
    )
    return list(session.scalars(consulta).unique())


def listar_por_movimentacoes(session: Session, movimentacao_ids: list[int]) -> dict[int, list[Aprovacao]]:
    """T-68 — uma única consulta para todas as movimentações de uma página
    (spec §13 "queries em lote"), em vez de uma consulta por linha."""
    if not movimentacao_ids:
        return {}
    consulta = (
        select(Aprovacao)
        .where(Aprovacao.movimentacao_id.in_(movimentacao_ids))
        .options(joinedload(Aprovacao.aprovador))
    )
    agrupadas: dict[int, list[Aprovacao]] = {mid: [] for mid in movimentacao_ids}
    for aprovacao in session.scalars(consulta).unique():
        agrupadas[aprovacao.movimentacao_id].append(aprovacao)
    return agrupadas


def criar_pendente(session: Session, movimentacao_id: int, tipo: TipoAprovacao) -> Aprovacao:
    aprovacao = Aprovacao(
        movimentacao_id=movimentacao_id, tipo=tipo, estado=EstadoAprovacao.PENDENTE, aprovador_id=None, data_decisao=None
    )
    session.add(aprovacao)
    session.flush()
    return aprovacao


def buscar_por_movimentacao_e_tipo(session: Session, movimentacao_id: int, tipo: TipoAprovacao) -> Aprovacao | None:
    consulta = (
        select(Aprovacao)
        .where(Aprovacao.movimentacao_id == movimentacao_id, Aprovacao.tipo == tipo)
        .options(joinedload(Aprovacao.aprovador))
    )
    return session.scalars(consulta).unique().one_or_none()


def decidir(
    session: Session,
    aprovacao: Aprovacao,
    estado: EstadoAprovacao,
    aprovador_id: int,
    justificativa: str | None,
    agora: datetime,
) -> Aprovacao:
    aprovacao.estado = estado
    aprovacao.aprovador_id = aprovador_id
    aprovacao.data_decisao = agora
    aprovacao.justificativa = justificativa
    session.flush()
    return aprovacao
