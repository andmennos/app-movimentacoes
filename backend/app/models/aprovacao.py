from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.enums import EstadoAprovacao, TipoAprovacao


class Aprovacao(Base):
    __tablename__ = "aprovacao"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    movimentacao_id: Mapped[int] = mapped_column(
        ForeignKey("movimentacao.id"), nullable=False, index=True
    )
    tipo: Mapped[TipoAprovacao] = mapped_column(Enum(TipoAprovacao, native_enum=False), nullable=False)
    estado: Mapped[EstadoAprovacao] = mapped_column(
        Enum(EstadoAprovacao, native_enum=False), nullable=False, default=EstadoAprovacao.PENDENTE
    )
    aprovador_id: Mapped[int | None] = mapped_column(ForeignKey("colaborador.id"), nullable=True)
    data_decisao: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    justificativa: Mapped[str | None] = mapped_column(String, nullable=True)

    movimentacao: Mapped["Movimentacao"] = relationship(
        foreign_keys=[movimentacao_id], back_populates="aprovacoes"
    )
    aprovador: Mapped["Colaborador | None"] = relationship(foreign_keys=[aprovador_id])
