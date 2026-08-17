from sqlalchemy import Boolean, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Departamento(Base):
    __tablename__ = "departamento"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    codigo: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    nome: Mapped[str] = mapped_column(String, nullable=False)
    ativo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    gestor_id: Mapped[int | None] = mapped_column(ForeignKey("colaborador.id"), nullable=True)
    estrutura_id: Mapped[int] = mapped_column(ForeignKey("estrutura_organizacional.id"), nullable=False)

    gestor: Mapped["Colaborador | None"] = relationship(foreign_keys=[gestor_id])
    estrutura: Mapped["EstruturaOrganizacional"] = relationship(foreign_keys=[estrutura_id])
    colaboradores: Mapped[list["Colaborador"]] = relationship(
        foreign_keys="Colaborador.departamento_id", back_populates="departamento"
    )
