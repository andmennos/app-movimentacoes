from sqlalchemy import Boolean, Enum, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.enums import AprovacaoAdicional


class Cargo(Base):
    __tablename__ = "cargo"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    codigo: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    nome: Mapped[str] = mapped_column(String, nullable=False)
    nivel: Mapped[int] = mapped_column(Integer, nullable=False)
    ativo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    permite_gestao: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    aprovacao_adicional: Mapped[AprovacaoAdicional | None] = mapped_column(
        Enum(AprovacaoAdicional, native_enum=False), nullable=True
    )

    colaboradores: Mapped[list["Colaborador"]] = relationship(back_populates="cargo")
