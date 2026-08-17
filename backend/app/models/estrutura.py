from sqlalchemy import Boolean, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class EstruturaOrganizacional(Base):
    __tablename__ = "estrutura_organizacional"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    codigo: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    nome: Mapped[str] = mapped_column(String, nullable=False)
    ativo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    estrutura_pai_id: Mapped[int | None] = mapped_column(
        ForeignKey("estrutura_organizacional.id"), nullable=True
    )
    nivel: Mapped[int] = mapped_column(Integer, nullable=False)

    estrutura_pai: Mapped["EstruturaOrganizacional | None"] = relationship(
        remote_side="EstruturaOrganizacional.id", foreign_keys=[estrutura_pai_id]
    )
