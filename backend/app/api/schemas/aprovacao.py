from datetime import datetime
from typing import Literal

from pydantic import ConfigDict, Field

from app.api.schemas.base import CamelModel
from app.api.schemas.movimentacao import ColaboradorResumo, SolicitanteResumo


class DecidirAprovacaoRequest(CamelModel):
    model_config = ConfigDict(extra="forbid")

    decisao: Literal["APROVADA", "REPROVADA"]
    justificativa: str | None = Field(default=None, max_length=1000)


class DecidirAprovacaoResponse(CamelModel):
    movimentacao_id: int
    tipo: str
    estado: str
    data_decisao: datetime
    movimentacao_status: str


class AprovacaoPendenteResponse(CamelModel):
    movimentacao_id: int
    tipo: str
    tipo_movimentacao: str
    ordem: int
    colaborador: ColaboradorResumo
    data_solicitacao: datetime
    solicitante: SolicitanteResumo | None = None
    origem: str | None = None
    destino: str | None = None
    setor: str | None = None
