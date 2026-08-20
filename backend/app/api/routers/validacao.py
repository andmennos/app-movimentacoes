from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.schemas import InconsistenciaResponse, ValidarRequest, ValidarResponse
from app.database import get_db
from app.models import OrigemExecucao, Usuario
from app.processing import orchestrator
from app.processing.orchestrator import OrchestratorResultado
from app.repositories import movimentacao_repository
from app.security import object_scope
from app.security.dependencies import require_scope
from app.security.permissions import SCOPE_MOVIMENTACOES_VALIDATE
from app.services.exceptions import (
    FalhaTecnicaValidacao,
    MovimentacaoNaoEncontrada,
    ValidacaoEmAndamento,
    ValidacaoManualNaoPermitida,
)

router = APIRouter(tags=["validacao"])


@router.post("/validar", response_model=ValidarResponse)
def validar_movimentacao(
    payload: ValidarRequest,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(require_scope(SCOPE_MOVIMENTACOES_VALIDATE)),
) -> ValidarResponse:
    """Adaptador síncrono técnico (spec §8.3) — chama o mesmo orquestrador do
    Worker (INV-09). Reavalia o gate de aprovação antes de executar a engine
    (RF-16): uma aprovação pendente/reprovada, ou uma solicitação já
    terminal, nunca chega à engine — vira 409, não uma execução "vazia"."""
    alvo = movimentacao_repository.buscar_por_id(db, payload.movimentacao_id)
    if alvo is None or not object_scope.pode_visualizar_movimentacao(db, usuario, alvo.colaborador_id):
        raise MovimentacaoNaoEncontrada(payload.movimentacao_id)

    saida = orchestrator.processar(db, payload.movimentacao_id, OrigemExecucao.MANUAL)

    if saida.resultado == OrchestratorResultado.EXECUTADO:
        auditoria = saida.auditoria
        return ValidarResponse(
            movimentacao_id=saida.movimentacao.id,
            status=auditoria.resultado.value,
            validado_em=auditoria.data_hora,
            inconsistencias=[
                InconsistenciaResponse(codigo=i.codigo_regra, mensagem=i.mensagem, severidade=i.severidade.value)
                for i in auditoria.inconsistencias
            ],
        )

    if saida.resultado in (OrchestratorResultado.BLOQUEADO_APROVACAO, OrchestratorResultado.JA_TERMINAL):
        raise ValidacaoManualNaoPermitida(saida.impedimentos)

    if saida.resultado == OrchestratorResultado.EM_ANDAMENTO:
        raise ValidacaoEmAndamento()

    raise FalhaTecnicaValidacao()  # ERRO_TECNICO: o orquestrador já tratou retry/erro do job
