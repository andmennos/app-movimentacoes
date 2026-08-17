"""Orquestra `POST /validar` (plan.md §6). Único ponto que decide status e
persiste auditoria — a decisão de validade em si pertence a `validation/`.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.config import settings
from app.models import Movimentacao, ResultadoValidacao, StatusMovimentacao
from app.models import ValidacaoAuditoria
from app.repositories import auditoria_repository, movimentacao_repository
from app.services.exceptions import MovimentacaoNaoEncontrada
from app.services.movimentacao_service import montar_contexto
from app.validation import types as vt
from app.validation.engine import executar, resolver_resultado

__all__ = ["MovimentacaoNaoEncontrada", "validar"]

_STATUS_POR_RESULTADO = {
    vt.ResultadoValidacao.APROVADA: StatusMovimentacao.APROVADA,
    vt.ResultadoValidacao.REPROVADA: StatusMovimentacao.REPROVADA,
    vt.ResultadoValidacao.AGUARDANDO_APROVACAO: StatusMovimentacao.PENDENTE,
}


def validar(session: Session, movimentacao_id: int) -> tuple[Movimentacao, ValidacaoAuditoria]:
    """Fluxo de `plan.md` §6. Não há `try/except` ao redor de `executar`:
    uma exceção não tratada propaga (INV-04) — a sessão nunca chega a commit,
    e `get_db` reverte a transação (database.py)."""
    movimentacao = movimentacao_repository.carregar_para_validacao(session, movimentacao_id)
    if movimentacao is None:
        raise MovimentacaoNaoEncontrada(movimentacao_id)

    ctx = montar_contexto(session, movimentacao)
    inconsistencias = executar(ctx)
    resultado = resolver_resultado(inconsistencias, ctx.aprovacoes)

    agora = datetime.now(timezone.utc).replace(tzinfo=None)
    auditoria = auditoria_repository.criar(
        session,
        movimentacao_id=movimentacao.id,
        resultado=ResultadoValidacao(resultado.value),
        inconsistencias=inconsistencias,
        versao_motor=settings.versao_motor,
        data_hora=agora,
    )

    movimentacao.resultado_ultima_validacao = ResultadoValidacao(resultado.value)
    movimentacao.data_ultima_validacao = agora
    movimentacao.status = _STATUS_POR_RESULTADO[resultado]

    session.commit()
    session.refresh(movimentacao)
    return movimentacao, auditoria
