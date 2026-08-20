from datetime import date

from sqlalchemy import Boolean, Date, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Colaborador(Base):
    __tablename__ = "colaborador"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    matricula: Mapped[str] = mapped_column(String, unique=True, index=True, nullable=False)
    nome: Mapped[str] = mapped_column(String, index=True, nullable=False)
    ativo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    cargo_id: Mapped[int] = mapped_column(ForeignKey("cargo.id"), nullable=False)
    departamento_id: Mapped[int] = mapped_column(ForeignKey("departamento.id"), nullable=False)
    centro_custo_id: Mapped[int] = mapped_column(ForeignKey("centro_custo.id"), nullable=False)
    gestor_id: Mapped[int | None] = mapped_column(ForeignKey("colaborador.id"), nullable=True)
    estrutura_id: Mapped[int | None] = mapped_column(
        ForeignKey("estrutura_organizacional.id"), nullable=True
    )
    data_admissao: Mapped[date] = mapped_column(Date, nullable=False)

    cargo: Mapped["Cargo"] = relationship(foreign_keys=[cargo_id], back_populates="colaboradores")
    departamento: Mapped["Departamento"] = relationship(
        foreign_keys=[departamento_id], back_populates="colaboradores"
    )
    centro_custo: Mapped["CentroCusto"] = relationship(
        foreign_keys=[centro_custo_id], back_populates="colaboradores"
    )
    gestor: Mapped["Colaborador | None"] = relationship(
        remote_side="Colaborador.id", foreign_keys=[gestor_id]
    )
    estrutura: Mapped["EstruturaOrganizacional | None"] = relationship(foreign_keys=[estrutura_id])
