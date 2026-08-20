from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.enums import OrigemExecucao, ResultadoValidacao, Severidade


class ValidacaoAuditoria(Base):
    __tablename__ = "validacao_auditoria"
    __table_args__ = (
        Index("ix_validacao_auditoria_movimentacao_data", "movimentacao_id", "data_hora"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    movimentacao_id: Mapped[int] = mapped_column(ForeignKey("movimentacao.id"), nullable=False)
    data_hora: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    resultado: Mapped[ResultadoValidacao] = mapped_column(
        Enum(ResultadoValidacao, native_enum=False), nullable=False
    )
    total_inconsistencias: Mapped[int] = mapped_column(Integer, nullable=False)
    versao_motor: Mapped[str] = mapped_column(String, nullable=False)
    origem_execucao: Mapped[OrigemExecucao] = mapped_column(
        Enum(OrigemExecucao, native_enum=False), nullable=False
    )
    solicitante_usuario_id: Mapped[int | None] = mapped_column(ForeignKey("usuario.id"), nullable=True)
    """spec.md §7.3 — rastreável mesmo quando a execução é AUTOMATICO."""
    ator_usuario_id: Mapped[int | None] = mapped_column(ForeignKey("usuario.id"), nullable=True)
    """spec.md §7.3 — nulo/SISTEMA quando `origem_execucao == AUTOMATICO`."""

    inconsistencias: Mapped[list["InconsistenciaAuditoria"]] = relationship(back_populates="validacao")
    solicitante: Mapped["Usuario | None"] = relationship(foreign_keys=[solicitante_usuario_id])
    ator: Mapped["Usuario | None"] = relationship(foreign_keys=[ator_usuario_id])


class InconsistenciaAuditoria(Base):
    __tablename__ = "inconsistencia_auditoria"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    validacao_id: Mapped[int] = mapped_column(ForeignKey("validacao_auditoria.id"), nullable=False)
    codigo_regra: Mapped[str] = mapped_column(String, nullable=False)
    mensagem: Mapped[str] = mapped_column(String, nullable=False)
    severidade: Mapped[Severidade] = mapped_column(Enum(Severidade, native_enum=False), nullable=False)

    validacao: Mapped["ValidacaoAuditoria"] = relationship(back_populates="inconsistencias")
