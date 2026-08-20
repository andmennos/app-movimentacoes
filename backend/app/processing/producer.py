"""Producer local — spec.md §1.1, §5.3; plan.md §6.

Idempotente por construção: uma movimentação só é candidata enquanto seu
`status` é `AGUARDANDO_APROVACAO`. Assim que o gate resolve (`BLOQUEADA` ou
`PENDENTE`+job), ela sai do universo de candidatas e nunca mais é reprocessada
por este loop — sem precisar de nenhuma checagem auxiliar de "já tem job".

Delega toda decisão de aprovação a `processing.approval_gate` — não
reimplementa regra de negócio.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models import Movimentacao, OrigemEvento, StatusJob, StatusMovimentacao, TipoEventoProcessamento
from app.processing.approval_gate import GateResultado, avaliar, calcular_impedimentos
from app.repositories import historico_processamento_repository as historico_repo
from app.repositories import job_validacao_repository as job_repo
from app.services.movimentacao_service import montar_contexto


@dataclass
class ResultadoProducer:
    agendadas: int = 0
    bloqueadas: int = 0
    aguardando: int = 0
    ids_agendados: list[int] = field(default_factory=list)


def aplicar_gate(session: Session, movimentacao: Movimentacao, agora: datetime) -> GateResultado:
    """Assume que o chamador já filtrou por `status=AGUARDANDO_APROVACAO`.
    Avalia o gate e aplica exatamente a ação correspondente (spec §5.3)."""
    ctx = montar_contexto(session, movimentacao)
    resultado = avaliar(ctx)

    if resultado == GateResultado.BLOQUEADA:
        movimentacao.status = StatusMovimentacao.BLOQUEADA
        for impedimento in calcular_impedimentos(ctx):
            historico_repo.registrar(
                session,
                movimentacao.id,
                TipoEventoProcessamento.APROVACAO_REPROVADA,
                OrigemEvento.SISTEMA,
                impedimento.mensagem,
                agora,
            )
    elif resultado == GateResultado.APTO:
        movimentacao.status = StatusMovimentacao.PENDENTE
        historico_repo.registrar(
            session,
            movimentacao.id,
            TipoEventoProcessamento.APROVACAO_CONCLUIDA,
            OrigemEvento.SISTEMA,
            "Todas as aprovações exigidas foram concluídas.",
            agora,
        )
        # `obter_ou_criar` (não `criar`): se a movimentação já teve um job
        # num ciclo anterior (voltou a AGUARDANDO_APROVACAO/BLOQUEADA e agora
        # está apta de novo), reaproveita a mesma linha — `movimentacao_id`
        # é única em `JobValidacao`.
        job = job_repo.obter_ou_criar(session, movimentacao.id, agora)
        if job.status != StatusJob.PENDENTE:
            job_repo.reabrir(session, job)
        historico_repo.registrar(
            session,
            movimentacao.id,
            TipoEventoProcessamento.PROCESSAMENTO_PENDENTE,
            OrigemEvento.SISTEMA,
            "Processamento agendado para validação automática.",
            agora,
        )
    # AGUARDANDO_APROVACAO: nenhuma aprovação nova foi decidida desde a
    # criação — permanece no mesmo status, nenhum evento novo é registrado.

    return resultado


def executar(session: Session, agora: datetime | None = None) -> ResultadoProducer:
    """Varre movimentações candidatas (`status = AGUARDANDO_APROVACAO`) e
    aplica o gate a cada uma. Reexecutar não duplica jobs nem reprocessa
    movimentações já decididas — idempotência por construção.
    """
    agora = agora or datetime.now(timezone.utc).replace(tzinfo=None)
    resultado = ResultadoProducer()

    candidatas = (
        session.query(Movimentacao)
        .filter(Movimentacao.status == StatusMovimentacao.AGUARDANDO_APROVACAO)
        .order_by(Movimentacao.id.asc())
        .all()
    )

    for mov in candidatas:
        gate = aplicar_gate(session, mov, agora)

        if gate == GateResultado.BLOQUEADA:
            resultado.bloqueadas += 1
        elif gate == GateResultado.APTO:
            resultado.agendadas += 1
            resultado.ids_agendados.append(mov.id)
        else:
            resultado.aguardando += 1

    session.commit()
    return resultado
