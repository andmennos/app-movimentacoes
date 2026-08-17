from datetime import datetime

import pytest

from app.models import (
    EstadoAprovacao,
    JobValidacao,
    ResultadoValidacao,
    StatusJob,
    StatusMovimentacao,
    TipoMovimentacao,
    ValidacaoAuditoria,
)
from app.processing import worker
from app.repositories import job_validacao_repository as job_repo
from app.services import validacao_service
from tests.builders import (
    ColaboradorBuilder,
    DepartamentoBuilder,
    JobValidacaoBuilder,
    MovimentacaoBuilder,
    criar_aprovacoes_exigidas,
)


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


def test_cnq04_worker_processa_job_valido_aprovada_com_auditoria(db_session):
    mov = _transferencia_valida(db_session)
    criar_aprovacoes_exigidas(db_session, mov, estado=EstadoAprovacao.APROVADA)
    db_session.commit()
    job = job_repo.criar(db_session, mov.id, datetime(2026, 1, 1))
    db_session.commit()

    processou = worker.processar_um_job(db_session)

    assert processou is True
    db_session.refresh(job)
    assert job.status == StatusJob.CONCLUIDO
    assert job.tentativas == 1
    assert job.iniciado_em is not None
    assert job.finalizado_em is not None

    db_session.refresh(mov)
    assert mov.status == StatusMovimentacao.APROVADA
    assert mov.resultado_ultima_validacao == ResultadoValidacao.APROVADA
    assert db_session.query(ValidacaoAuditoria).filter_by(movimentacao_id=mov.id).count() == 1


def test_cnq05_worker_processa_job_com_multiplas_inconsistencias(db_session):
    dep_destino = DepartamentoBuilder(ativo=False).build(db_session)
    mov = MovimentacaoBuilder(
        tipo=TipoMovimentacao.TRANSFERENCIA, departamento_destino_id=dep_destino.id
    ).build(db_session)
    db_session.commit()
    job_repo.criar(db_session, mov.id, datetime(2026, 1, 1))
    db_session.commit()

    worker.processar_um_job(db_session)

    db_session.refresh(mov)
    assert mov.status == StatusMovimentacao.REPROVADA
    auditoria = db_session.query(ValidacaoAuditoria).filter_by(movimentacao_id=mov.id).one()
    assert auditoria.total_inconsistencias >= 1


def test_ca047_falha_tecnica_nao_deixa_estado_parcial_e_registra_tentativa(db_session, monkeypatch):
    mov = _transferencia_valida(db_session)
    criar_aprovacoes_exigidas(db_session, mov, estado=EstadoAprovacao.APROVADA)
    db_session.commit()
    job_repo.criar(db_session, mov.id, datetime(2026, 1, 1))
    db_session.commit()
    status_original = mov.status
    resultado_original = mov.resultado_ultima_validacao

    def quebrar(session, movimentacao_id):
        raise RuntimeError("falha técnica simulada")

    monkeypatch.setattr(worker, "validacao_service", type("M", (), {"validar": staticmethod(quebrar)}))

    processou = worker.processar_um_job(db_session)

    assert processou is True
    job = db_session.query(JobValidacao).filter_by(movimentacao_id=mov.id).one()
    assert job.tentativas == 1
    assert job.status == StatusJob.PENDENTE  # ainda dentro do limite: nova tentativa
    assert "RuntimeError" in job.ultimo_erro
    assert job.finalizado_em is None

    db_session.refresh(mov)
    assert mov.status == status_original
    assert mov.resultado_ultima_validacao == resultado_original
    assert db_session.query(ValidacaoAuditoria).filter_by(movimentacao_id=mov.id).count() == 0


def test_falha_tecnica_apos_limite_de_tentativas_vai_para_erro_terminal(db_session, monkeypatch):
    mov = _transferencia_valida(db_session)
    criar_aprovacoes_exigidas(db_session, mov, estado=EstadoAprovacao.APROVADA)
    db_session.commit()
    job = JobValidacaoBuilder(
        movimentacao_id=mov.id, status=StatusJob.PENDENTE, tentativas=worker.LIMITE_TENTATIVAS - 1
    ).build(db_session)
    db_session.commit()

    def quebrar(session, movimentacao_id):
        raise RuntimeError("falha persistente")

    monkeypatch.setattr(worker, "validacao_service", type("M", (), {"validar": staticmethod(quebrar)}))

    worker.processar_um_job(db_session)

    db_session.refresh(job)
    assert job.tentativas == worker.LIMITE_TENTATIVAS
    assert job.status == StatusJob.ERRO
    assert job.finalizado_em is not None


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


def test_worker_reutiliza_validacao_service_nao_duplica_regras(db_session):
    """INV-11: garante que o worker chama o mesmo módulo usado por POST /validar,
    não uma implementação paralela das 34 regras."""
    assert worker.validacao_service is validacao_service
