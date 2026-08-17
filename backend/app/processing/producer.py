"""Producer local — spec.md §5.4, §7.2; plan.md §6.1.

Idempotente: nunca cria um segundo `JobValidacao` para a mesma movimentação
(INV-10, CA-043, CN-Q06). Delega toda decisão de aprovação a
`processing.approval_gate` — não reimplementa regra de negócio.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models import Movimentacao, StatusMovimentacao
from app.processing.approval_gate import GateResultado, avaliar
from app.repositories import job_validacao_repository as job_repo
from app.services.movimentacao_service import montar_contexto


@dataclass
class ResultadoProducer:
    agendadas: int = 0
    bloqueadas: int = 0
    aguardando: int = 0
    anomalas: int = 0
    ids_agendados: list[int] = field(default_factory=list)


def _aplicar_gate(session: Session, movimentacao: Movimentacao, agora: datetime) -> GateResultado:
    """Assume que o chamador já verificou que não existe job para esta
    movimentação. Avalia o gate e aplica exatamente a ação correspondente
    (spec §5.4) — nenhuma outra combinação de estado é escrita aqui."""
    ctx = montar_contexto(session, movimentacao)
    resultado = avaliar(ctx)

    if resultado == GateResultado.REPROVADA:
        movimentacao.status = StatusMovimentacao.REPROVADA
    elif resultado == GateResultado.APTA:
        job_repo.criar(session, movimentacao.id, agora)
    # PENDENTE / ANOMALO: nenhuma ação — não mascara o estado real (spec §5.4)

    return resultado


def executar(session: Session, agora: datetime | None = None) -> ResultadoProducer:
    """Varre movimentações candidatas (`status = PENDENTE`) e aplica o gate a
    cada uma que ainda não tenha job. Reexecutar não duplica jobs nem
    reprocessa movimentações já decididas — idempotência por construção.
    """
    agora = agora or datetime.now(timezone.utc).replace(tzinfo=None)
    resultado = ResultadoProducer()

    candidatas = (
        session.query(Movimentacao)
        .filter(Movimentacao.status == StatusMovimentacao.PENDENTE)
        .order_by(Movimentacao.id.asc())
        .all()
    )

    for mov in candidatas:
        if job_repo.existe_para_movimentacao(session, mov.id):
            continue

        gate = _aplicar_gate(session, mov, agora)

        if gate == GateResultado.REPROVADA:
            resultado.bloqueadas += 1
        elif gate == GateResultado.APTA:
            resultado.agendadas += 1
            resultado.ids_agendados.append(mov.id)
        elif gate == GateResultado.ANOMALO:
            resultado.anomalas += 1
        else:
            resultado.aguardando += 1

    session.commit()
    return resultado
