from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.models import HistoricoProcessamento, OrigemEvento, TipoEventoProcessamento

"""Repositório do histórico de processamento — append-only (RC-16/RC-17,
RNF-04). Não existe (e não deve existir) update/delete: a timeline reflete
exatamente os eventos que o backend/Worker realmente observaram.
"""


def registrar(
    session: Session,
    movimentacao_id: int,
    tipo_evento: TipoEventoProcessamento,
    origem: OrigemEvento,
    mensagem: str,
    data_hora: datetime,
    detalhe_sanitizado: str | None = None,
    ator_usuario_id: int | None = None,
    solicitante_usuario_id: int | None = None,
) -> HistoricoProcessamento:
    evento = HistoricoProcessamento(
        movimentacao_id=movimentacao_id,
        tipo_evento=tipo_evento,
        data_hora=data_hora,
        origem=origem,
        mensagem=mensagem,
        detalhe_sanitizado=detalhe_sanitizado,
        ator_usuario_id=ator_usuario_id,
        solicitante_usuario_id=solicitante_usuario_id,
    )
    session.add(evento)
    session.flush()
    return evento


def listar_por_movimentacao(session: Session, movimentacao_id: int) -> list[HistoricoProcessamento]:
    consulta = (
        select(HistoricoProcessamento)
        .where(HistoricoProcessamento.movimentacao_id == movimentacao_id)
        .options(joinedload(HistoricoProcessamento.ator), joinedload(HistoricoProcessamento.solicitante))
        .order_by(HistoricoProcessamento.data_hora.asc(), HistoricoProcessamento.id.asc())
    )
    return list(session.scalars(consulta))
