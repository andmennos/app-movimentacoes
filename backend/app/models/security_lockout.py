from datetime import datetime

from sqlalchemy import DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class SecurityLockout(Base):
    """spec.md §12.3/RC-25 — bloqueio de força bruta por IP, persistido no
    SQLite (sobrevive a reinício de processo, ao contrário do rate limiter
    geral em memória — plan.md §14.3). Reset via `python -m
    app.security.reset_lockouts`, que só altera esta tabela."""

    __tablename__ = "security_lockout"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ip: Mapped[str] = mapped_column(String, unique=True, index=True, nullable=False)
    failed_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    window_started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    blocked_until: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
