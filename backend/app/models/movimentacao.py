from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Index, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.enums import ResultadoValidacao, StatusMovimentacao, TipoMovimentacao


class Movimentacao(Base):
    __tablename__ = "movimentacao"
    __table_args__ = (
        Index("ix_movimentacao_colaborador_tipo_status", "colaborador_id", "tipo", "status"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tipo: Mapped[TipoMovimentacao] = mapped_column(Enum(TipoMovimentacao, native_enum=False), nullable=False)
    status: Mapped[StatusMovimentacao] = mapped_column(
        Enum(StatusMovimentacao, native_enum=False),
        nullable=False,
        default=StatusMovimentacao.PENDENTE,
        index=True,
    )
    colaborador_id: Mapped[int] = mapped_column(
        ForeignKey("colaborador.id"), nullable=False, index=True
    )
    data_solicitacao: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)

    departamento_origem_id: Mapped[int | None] = mapped_column(ForeignKey("departamento.id"), nullable=True)
    departamento_destino_id: Mapped[int | None] = mapped_column(ForeignKey("departamento.id"), nullable=True)
    cargo_origem_id: Mapped[int | None] = mapped_column(ForeignKey("cargo.id"), nullable=True)
    cargo_destino_id: Mapped[int | None] = mapped_column(ForeignKey("cargo.id"), nullable=True)
    gestor_origem_id: Mapped[int | None] = mapped_column(ForeignKey("colaborador.id"), nullable=True)
    gestor_destino_id: Mapped[int | None] = mapped_column(ForeignKey("colaborador.id"), nullable=True)
    centro_custo_origem_id: Mapped[int | None] = mapped_column(ForeignKey("centro_custo.id"), nullable=True)
    centro_custo_destino_id: Mapped[int | None] = mapped_column(ForeignKey("centro_custo.id"), nullable=True)
    estrutura_origem_id: Mapped[int | None] = mapped_column(
        ForeignKey("estrutura_organizacional.id"), nullable=True
    )
    estrutura_destino_id: Mapped[int | None] = mapped_column(
        ForeignKey("estrutura_organizacional.id"), nullable=True
    )

    resultado_ultima_validacao: Mapped[ResultadoValidacao | None] = mapped_column(
        Enum(ResultadoValidacao, native_enum=False), nullable=True
    )
    data_ultima_validacao: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    colaborador: Mapped["Colaborador"] = relationship(foreign_keys=[colaborador_id])
    departamento_origem: Mapped["Departamento | None"] = relationship(foreign_keys=[departamento_origem_id])
    departamento_destino: Mapped["Departamento | None"] = relationship(foreign_keys=[departamento_destino_id])
    cargo_origem: Mapped["Cargo | None"] = relationship(foreign_keys=[cargo_origem_id])
    cargo_destino: Mapped["Cargo | None"] = relationship(foreign_keys=[cargo_destino_id])
    gestor_origem: Mapped["Colaborador | None"] = relationship(foreign_keys=[gestor_origem_id])
    gestor_destino: Mapped["Colaborador | None"] = relationship(foreign_keys=[gestor_destino_id])
    centro_custo_origem: Mapped["CentroCusto | None"] = relationship(foreign_keys=[centro_custo_origem_id])
    centro_custo_destino: Mapped["CentroCusto | None"] = relationship(foreign_keys=[centro_custo_destino_id])
    estrutura_origem: Mapped["EstruturaOrganizacional | None"] = relationship(
        foreign_keys=[estrutura_origem_id]
    )
    estrutura_destino: Mapped["EstruturaOrganizacional | None"] = relationship(
        foreign_keys=[estrutura_destino_id]
    )
    aprovacoes: Mapped[list["Aprovacao"]] = relationship(back_populates="movimentacao")
