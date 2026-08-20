"""GET /referencias/* — spec.md §15/plan.md §8.3. Cache local TTL curto
(RC-29/T-68): cargos/departamentos/centros de custo são referência
estável; nunca aprovação/status/BOLA passam por aqui."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.schemas import CargoResumo, CentroCustoResumo, DepartamentoResumo, EstruturaResumo
from app.config import settings
from app.database import get_db
from app.models import Usuario
from app.repositories import referencia_repository
from app.security.dependencies import require_scope
from app.security.permissions import SCOPE_COLABORADORES_READ
from app.services import reference_cache

router = APIRouter(prefix="/referencias", tags=["referencias"])


@router.get("/cargos", response_model=list[CargoResumo])
def listar_cargos(
    db: Session = Depends(get_db), _usuario: Usuario = Depends(require_scope(SCOPE_COLABORADORES_READ))
) -> list[CargoResumo]:
    # Cacheia os schemas de resposta (dados planos), não os objetos ORM —
    # evita reter instâncias de uma sessão já fechada de outra requisição.
    def _calcular():
        return [CargoResumo(id=c.id, nome=c.nome, nivel=c.nivel) for c in referencia_repository.listar_cargos(db)]

    return reference_cache.obter_ou_calcular("cargos", settings.reference_cache_ttl_seconds, _calcular)


@router.get("/departamentos", response_model=list[DepartamentoResumo])
def listar_departamentos(
    db: Session = Depends(get_db), _usuario: Usuario = Depends(require_scope(SCOPE_COLABORADORES_READ))
) -> list[DepartamentoResumo]:
    def _calcular():
        return [
            DepartamentoResumo(id=d.id, codigo=d.codigo, nome=d.nome, ativo=d.ativo)
            for d in referencia_repository.listar_departamentos(db)
        ]

    return reference_cache.obter_ou_calcular("departamentos", settings.reference_cache_ttl_seconds, _calcular)


@router.get("/centros-custo", response_model=list[CentroCustoResumo])
def listar_centros_custo(
    db: Session = Depends(get_db), _usuario: Usuario = Depends(require_scope(SCOPE_COLABORADORES_READ))
) -> list[CentroCustoResumo]:
    def _calcular():
        return [
            CentroCustoResumo(id=c.id, codigo=c.codigo, nome=c.nome, ativo=c.ativo)
            for c in referencia_repository.listar_centros_custo(db)
        ]

    return reference_cache.obter_ou_calcular("centros_custo", settings.reference_cache_ttl_seconds, _calcular)


@router.get("/estruturas", response_model=list[EstruturaResumo])
def listar_estruturas(
    db: Session = Depends(get_db), _usuario: Usuario = Depends(require_scope(SCOPE_COLABORADORES_READ))
) -> list[EstruturaResumo]:
    def _calcular():
        return [
            EstruturaResumo(id=e.id, codigo=e.codigo, nome=e.nome, ativo=e.ativo)
            for e in referencia_repository.listar_estruturas(db)
        ]

    return reference_cache.obter_ou_calcular("estruturas", settings.reference_cache_ttl_seconds, _calcular)
