from datetime import datetime

from app.models import EstadoAprovacao, ResultadoValidacao, StatusMovimentacao, TipoMovimentacao, ValidacaoAuditoria
from app.processing import orchestrator, worker
from app.repositories import job_validacao_repository as job_repo
from tests.builders import ColaboradorBuilder, DepartamentoBuilder, MovimentacaoBuilder, criar_aprovacoes_exigidas


def _transferencia_valida(db_session):
    dep_origem = DepartamentoBuilder(gestor_id=ColaboradorBuilder().build(db_session).id).build(db_session)
    dep_destino = DepartamentoBuilder(gestor_id=ColaboradorBuilder().build(db_session).id).build(db_session)
    return MovimentacaoBuilder(
        tipo=TipoMovimentacao.TRANSFERENCIA,
        departamento_origem_id=dep_origem.id,
        departamento_destino_id=dep_destino.id,
    ).build(db_session)


def test_fila_vazia_retorna_false(db_session):
    assert worker.processar_um_job(db_session) is False


def test_worker_processa_job_valido_via_orquestrador(db_session):
    mov = _transferencia_valida(db_session)
    criar_aprovacoes_exigidas(db_session, mov, estado=EstadoAprovacao.APROVADA)
    db_session.commit()
    job = job_repo.criar(db_session, mov.id, datetime(2026, 1, 1))
    db_session.commit()

    processou = worker.processar_um_job(db_session)

    assert processou is True
    db_session.refresh(job)
    assert job.status.value == "CONCLUIDO"

    db_session.refresh(mov)
    assert mov.status == StatusMovimentacao.APROVADA
    assert mov.resultado_ultima_validacao == ResultadoValidacao.APROVADA
    assert db_session.query(ValidacaoAuditoria).filter_by(movimentacao_id=mov.id).count() == 1


def test_worker_processa_job_com_multiplas_inconsistencias(db_session):
    dep_destino = DepartamentoBuilder(ativo=False).build(db_session)
    mov = MovimentacaoBuilder(
        tipo=TipoMovimentacao.TRANSFERENCIA, departamento_destino_id=dep_destino.id
    ).build(db_session)
    criar_aprovacoes_exigidas(db_session, mov, estado=EstadoAprovacao.APROVADA)
    db_session.commit()
    job_repo.criar(db_session, mov.id, datetime(2026, 1, 1))
    db_session.commit()

    worker.processar_um_job(db_session)

    db_session.refresh(mov)
    assert mov.status == StatusMovimentacao.REPROVADA
    auditoria = db_session.query(ValidacaoAuditoria).filter_by(movimentacao_id=mov.id).one()
    assert auditoria.total_inconsistencias >= 1


def test_drenar_fila_processa_todos_os_jobs_pendentes(db_session):
    for _ in range(3):
        mov = _transferencia_valida(db_session)
        criar_aprovacoes_exigidas(db_session, mov, estado=EstadoAprovacao.APROVADA)
        db_session.commit()
        job_repo.criar(db_session, mov.id, datetime(2026, 1, 1))
        db_session.commit()

    total = worker.drenar_fila(db_session)

    assert total == 3
    assert job_repo.buscar_pendente_mais_antigo(db_session) is None


def test_worker_delega_para_o_orquestrador_unico(db_session):
    """INV-09: garante que o worker chama o mesmo orquestrador usado por
    `POST /validar` — não uma implementação paralela."""
    assert worker.orchestrator is orchestrator


def test_worker_recupera_jobs_stale_antes_de_consumir(db_session, monkeypatch):
    chamadas = []
    monkeypatch.setattr(
        orchestrator, "recuperar_jobs_stale", lambda session: chamadas.append(1) or 0
    )

    worker.processar_um_job(db_session)

    assert chamadas == [1]
