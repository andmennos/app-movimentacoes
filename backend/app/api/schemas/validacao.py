from datetime import datetime

from app.api.schemas.base import CamelModel
from app.api.schemas.movimentacao import InconsistenciaResponse


class ValidarRequest(CamelModel):
    movimentacao_id: int


class ValidarResponse(CamelModel):
    movimentacao_id: int
    status: str
    validado_em: datetime
    inconsistencias: list[InconsistenciaResponse]
