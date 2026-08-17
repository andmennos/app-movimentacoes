from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.enums import StatusJob


class JobValidacao(Base):
    """Fila local persistida no SQLite (spec.md §4.1, RC-14).

    Infraestrutura, não regra de domínio: representa a execução técnica da
    validação automática, não o estado de negócio da movimentação
    (`Movimentacao.status` é um conceito separado — spec.md §4.1).

    `movimentacao_id` é único: no fluxo automático do MVP, no máximo um job
    é criado por movimentação (idempotência do producer, RF-20/INV-10).
    """

    __tablename__ = "job_validacao"
    __table_args__ = (Index("ix_job_validacao_status_criado_em", "status", "criado_em"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    movimentacao_id: Mapped[int] = mapped_column(
        ForeignKey("movimentacao.id"), nullable=False, unique=True
    )
    status: Mapped[StatusJob] = mapped_column(
        Enum(StatusJob, native_enum=False), nullable=False, default=StatusJob.PENDENTE
    )
    tentativas: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    criado_em: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    iniciado_em: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    finalizado_em: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    ultimo_erro: Mapped[str | None] = mapped_column(String, nullable=True)

    movimentacao: Mapped["Movimentacao"] = relationship(foreign_keys=[movimentacao_id])
