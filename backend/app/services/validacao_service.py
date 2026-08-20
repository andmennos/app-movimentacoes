"""Executa o motor de validação sobre uma movimentação já carregada e grava a
auditoria correspondente (spec.md §7.5, plan.md §8).

Não decide status de negócio, não toca na fila e não registra histórico de
processamento — isso é responsabilidade exclusiva do orquestrador
(`processing/orchestrator.py`, INV-08). Chamado somente por ele, que por sua
vez é chamado tanto pelo Worker quanto por `POST /validar` (INV-09) — nenhuma
das 34 regras é reimplementada em nenhum dos dois caminhos.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.config import settings
from app.models import Movimentacao, OrigemExecucao, ResultadoValidacao, ValidacaoAuditoria
from app.repositories import auditoria_repository
from app.services.movimentacao_service import montar_contexto
from app.validation.engine import executar, resolver_resultado

__all__ = ["validar"]


def validar(
    session: Session, movimentacao: Movimentacao, origem_execucao: OrigemExecucao
) -> ValidacaoAuditoria:
    """spec.md §7.5: monta o contexto, executa as 34 regras e grava a
    auditoria (INV-07: exatamente um registro por execução concluída).

    Não há `try/except` ao redor de `executar`: uma exceção não tratada
    propaga (INV-04) para o orquestrador, que decide o que fazer com a falha
    técnica — a validação não foi concluída, não há resultado de negócio
    confiável a persistir.
    """
    ctx = montar_contexto(session, movimentacao)
    inconsistencias = executar(ctx)
    resultado = resolver_resultado(inconsistencias)

    agora = datetime.now(timezone.utc).replace(tzinfo=None)
    auditoria = auditoria_repository.criar(
        session,
        movimentacao_id=movimentacao.id,
        resultado=ResultadoValidacao(resultado.value),
        inconsistencias=inconsistencias,
        versao_motor=settings.versao_motor,
        data_hora=agora,
        origem_execucao=origem_execucao,
        solicitante_usuario_id=movimentacao.solicitante_usuario_id,
    )

    movimentacao.resultado_ultima_validacao = ResultadoValidacao(resultado.value)
    movimentacao.data_ultima_validacao = agora

    return auditoria
