from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.models import Aprovacao


def listar_por_movimentacao(session: Session, movimentacao_id: int) -> list[Aprovacao]:
    consulta = (
        select(Aprovacao)
        .where(Aprovacao.movimentacao_id == movimentacao_id)
        .options(joinedload(Aprovacao.aprovador))
    )
    return list(session.scalars(consulta).unique())
