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
    familia_cargo: Mapped[str] = mapped_column(String, nullable=False, index=True)
    """spec.md §9.1/RC-05 — trilha de carreira. P07 exige mesma família."""
    ordem_progressao: Mapped[int] = mapped_column(Integer, nullable=False)
    """spec.md §9.1/plan.md §11.2 — posição sequencial dentro da família,
    fonte de verdade de P03 (`destino.ordem_progressao == atual.ordem_progressao + 1`).
    Não é o mesmo que `nivel`/o número no nome do cargo, que reinicia entre
    senioridades."""
    custo_mensal_referencia: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    """spec.md §9.1/§11 — em centavos, para aritmética exata do delta de
    P09/efetivação (evita ponto flutuante)."""
    papel_lideranca: Mapped[AprovacaoAdicional | None] = mapped_column(
        Enum(AprovacaoAdicional, native_enum=False), nullable=True
    )
    """spec.md RC-38/§9.1 — discriminador técnico usado para resolver a
    pessoa concreta (via cadeia de `gestor_id`) que decide a etapa
    GERENCIA/DIRETORIA de uma promoção com `aprovacao_adicional` (T-75).
    Não define progressão nem participa de P03/P07; reaproveita o mesmo
    enum de `aprovacao_adicional` porque os valores coincidem
    (GERENCIA|DIRETORIA), sem duplicar um enum equivalente."""

    colaboradores: Mapped[list["Colaborador"]] = relationship(back_populates="cargo")
