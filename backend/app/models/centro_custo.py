from sqlalchemy import Boolean, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class CentroCusto(Base):
    __tablename__ = "centro_custo"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    codigo: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    nome: Mapped[str] = mapped_column(String, nullable=False)
    ativo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    responsavel_id: Mapped[int | None] = mapped_column(ForeignKey("colaborador.id"), nullable=True)
    estrutura_id: Mapped[int] = mapped_column(ForeignKey("estrutura_organizacional.id"), nullable=False)

    responsavel: Mapped["Colaborador | None"] = relationship(foreign_keys=[responsavel_id])
    estrutura: Mapped["EstruturaOrganizacional"] = relationship(foreign_keys=[estrutura_id])
    colaboradores: Mapped[list["Colaborador"]] = relationship(
        foreign_keys="Colaborador.centro_custo_id", back_populates="centro_custo"
    )
