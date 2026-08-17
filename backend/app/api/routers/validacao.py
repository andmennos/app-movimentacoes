from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.schemas import InconsistenciaResponse, ValidarRequest, ValidarResponse
from app.database import get_db
from app.services import validacao_service

router = APIRouter(tags=["validacao"])


@router.post("/validar", response_model=ValidarResponse)
def validar_movimentacao(payload: ValidarRequest, db: Session = Depends(get_db)) -> ValidarResponse:
    movimentacao, auditoria = validacao_service.validar(db, payload.movimentacao_id)

    return ValidarResponse(
        movimentacao_id=movimentacao.id,
        status=auditoria.resultado.value,
        validado_em=auditoria.data_hora,
        inconsistencias=[
            InconsistenciaResponse(codigo=i.codigo_regra, mensagem=i.mensagem, severidade=i.severidade.value)
            for i in auditoria.inconsistencias
        ],
    )
