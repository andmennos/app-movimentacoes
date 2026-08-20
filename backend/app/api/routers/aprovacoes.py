from typing import Literal

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.schemas import AprovacaoPendenteResponse
from app.database import get_db
from app.models import Usuario
from app.security.dependencies import require_scope
from app.security.permissions import SCOPE_MOVIMENTACOES_APPROVE
from app.services import aprovacao_service, rotulo_service

router = APIRouter(prefix="/aprovacoes", tags=["aprovacoes"])


@router.get("/pendentes", response_model=list[AprovacaoPendenteResponse])
def listar_pendentes(
    busca: str | None = Query(None, max_length=200),
    ordenar_por: str = Query(aprovacao_service.ORDENACAO_PENDENTES_PADRAO, alias="ordenarPor"),
    direcao: Literal["asc", "desc"] = Query("desc"),
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(require_scope(SCOPE_MOVIMENTACOES_APPROVE)),
) -> list[AprovacaoPendenteResponse]:
    pendentes = aprovacao_service.listar_pendentes(db, usuario, busca, ordenar_por, direcao)
    resultado = []
    for mov, exigencia, _aprovacao in pendentes:
        origem, destino = rotulo_service.origem_destino(mov)
        resultado.append(
            AprovacaoPendenteResponse(
                movimentacao_id=mov.id,
                tipo=exigencia.tipo.value,
                tipo_movimentacao=mov.tipo.value,
                ordem=exigencia.ordem,
                colaborador={
                    "id": mov.colaborador.id,
                    "matricula": mov.colaborador.matricula,
                    "nome": mov.colaborador.nome,
                },
                data_solicitacao=mov.data_solicitacao,
                solicitante=(
                    {"id": mov.solicitante.id, "username": mov.solicitante.username, "perfil": mov.solicitante.perfil.value}
                    if mov.solicitante
                    else None
                ),
                origem=origem,
                destino=destino,
                setor=rotulo_service.setor(mov),
            )
        )
    return resultado
