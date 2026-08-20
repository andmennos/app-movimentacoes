"""GET /colaboradores — spec.md §3.3. BOLA aplicado na query, nunca
cacheado (RC-29): LIDERANCA só vê sua subárvore, demais perfis sem
filtro organizacional."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.schemas import ColaboradorResumo
from app.database import get_db
from app.models import Usuario
from app.repositories import colaborador_repository
from app.security import object_scope
from app.security.dependencies import require_scope
from app.security.permissions import SCOPE_COLABORADORES_READ

router = APIRouter(prefix="/colaboradores", tags=["colaboradores"])


@router.get("", response_model=list[ColaboradorResumo])
def listar_colaboradores(
    busca: str | None = Query(None, max_length=200),
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(require_scope(SCOPE_COLABORADORES_READ)),
) -> list[ColaboradorResumo]:
    ids_permitidos = object_scope.ids_colaboradores_permitidos(db, usuario)
    colaboradores = colaborador_repository.listar(db, ids_permitidos, busca)
    return [ColaboradorResumo(id=c.id, matricula=c.matricula, nome=c.nome) for c in colaboradores]
