from datetime import datetime

from pydantic import ConfigDict

from app.api.schemas.base import CamelModel
from app.api.schemas.movimentacao import InconsistenciaResponse


class ValidarRequest(CamelModel):
    """spec.md RC-40/SEC-02 (T-78) — `extra="forbid"` também neste payload
    autenticado: um campo extra deve reprovar com 422, nunca ser
    silenciosamente ignorado."""

    model_config = ConfigDict(extra="forbid")

    movimentacao_id: int


class ValidarResponse(CamelModel):
    movimentacao_id: int
    status: str
    validado_em: datetime
    inconsistencias: list[InconsistenciaResponse]
