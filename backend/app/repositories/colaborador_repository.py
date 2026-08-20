"""spec.md §3.3 — colaboradores disponíveis para solicitação. BOLA aplicado
antes de qualquer limite/ordenação (RC-16/plan §7.3), nunca cacheado
(RC-29 — só cargos/departamentos/CC são referência estável)."""

from __future__ import annotations

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.models import Colaborador


def listar(
    session: Session, colaborador_ids_permitidos: set[int] | None, busca: str | None = None
) -> list[Colaborador]:
    """spec.md RC-49/T-86 — `busca` (nome parcial ou matrícula) é aplicada
    aqui, sempre depois do filtro BOLA — nunca no Angular (plan.md §24.4)."""
    consulta = select(Colaborador).where(Colaborador.ativo.is_(True))
    if colaborador_ids_permitidos is not None:
        consulta = consulta.where(Colaborador.id.in_(colaborador_ids_permitidos))
    if busca:
        consulta = consulta.where(
            or_(Colaborador.matricula.ilike(f"%{busca}%"), Colaborador.nome.ilike(f"%{busca}%"))
        )
    consulta = consulta.order_by(Colaborador.nome)
    return list(session.scalars(consulta))
