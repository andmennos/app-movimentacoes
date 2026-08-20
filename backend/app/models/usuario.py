from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.enums import PerfilUsuario


class Usuario(Base):
    """spec.md §2.1/RC-13 — usuário autenticável do MVP. Apenas o hash da
    senha é persistido (RC-15/plan.md §4) — nunca a senha em texto puro."""

    __tablename__ = "usuario"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String, unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String, nullable=False)
    perfil: Mapped[PerfilUsuario] = mapped_column(Enum(PerfilUsuario, native_enum=False), nullable=False)
    colaborador_id: Mapped[int | None] = mapped_column(ForeignKey("colaborador.id"), nullable=True)
    ativo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    criado_em: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    colaborador: Mapped["Colaborador | None"] = relationship(foreign_keys=[colaborador_id])
