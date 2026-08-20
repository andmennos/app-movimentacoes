from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.enums import OrigemEvento, TipoEventoProcessamento


class HistoricoProcessamento(Base):
    """Linha do tempo real de uma movimentação (spec.md §2.5/RC-16/RC-17).

    Append-only: só existe `criar`/`listar_por_movimentacao` no repositório —
    nenhum update/delete. Nenhum evento é sintetizado pelo Angular; tudo que a
    timeline mostra vem persistido aqui pelo backend/Worker.
    """

    __tablename__ = "historico_processamento"
    __table_args__ = (
        Index("ix_historico_processamento_movimentacao_data", "movimentacao_id", "data_hora", "id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    movimentacao_id: Mapped[int] = mapped_column(ForeignKey("movimentacao.id"), nullable=False)
    tipo_evento: Mapped[TipoEventoProcessamento] = mapped_column(
        Enum(TipoEventoProcessamento, native_enum=False), nullable=False
    )
    data_hora: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    origem: Mapped[OrigemEvento] = mapped_column(Enum(OrigemEvento, native_enum=False), nullable=False)
    mensagem: Mapped[str] = mapped_column(String, nullable=False)
    detalhe_sanitizado: Mapped[str | None] = mapped_column(String, nullable=True)
    ator_usuario_id: Mapped[int | None] = mapped_column(ForeignKey("usuario.id"), nullable=True)
    """spec.md §7.2 — quem praticou a ação (decisão de aprovação, validação
    manual). Nulo em eventos de origem SISTEMA/AUTOMATICO."""
    solicitante_usuario_id: Mapped[int | None] = mapped_column(ForeignKey("usuario.id"), nullable=True)
    """spec.md §7.2 — mantém o solicitante rastreável mesmo em eventos
    automáticos, sem depender de join com `Movimentacao`."""

    movimentacao: Mapped["Movimentacao"] = relationship(foreign_keys=[movimentacao_id])
    ator: Mapped["Usuario | None"] = relationship(foreign_keys=[ator_usuario_id])
    solicitante: Mapped["Usuario | None"] = relationship(foreign_keys=[solicitante_usuario_id])
