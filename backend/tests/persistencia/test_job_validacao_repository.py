from datetime import datetime

from sqlalchemy import inspect

from app.models import StatusJob
from app.repositories import job_validacao_repository as repo
from tests.builders import JobValidacaoBuilder, MovimentacaoBuilder


def test_schema_tem_indice_status_criado_em(engine):
    inspector = inspect(engine)
    indices = [tuple(i["column_names"]) for i in inspector.get_indexes("job_validacao")]
    assert ("status", "criado_em") in indices


def test_schema_movimentacao_id_e_unico(engine):
    inspector = inspect(engine)
    unicos = inspector.get_unique_constraints("job_validacao")
    colunas_unicas = {c for u in unicos for c in u["column_names"]}
    # SQLite pode expor unique via índice único em vez de constraint nomeada
    indices_unicos = {
        c for i in inspector.get_indexes("job_validacao") if i["unique"] for c in i["column_names"]
    }
    assert "movimentacao_id" in (colunas_unicas | indices_unicos)


def test_criar_job(db_session):
    mov = MovimentacaoBuilder().build(db_session)
    job = repo.criar(db_session, mov.id, datetime(2026, 1, 1, 9, 0, 0))

    assert job.id is not None
    assert job.status == StatusJob.PENDENTE
    assert job.tentativas == 0
    assert job.movimentacao_id == mov.id


def test_existe_para_movimentacao(db_session):
    mov = MovimentacaoBuilder().build(db_session)
    assert repo.existe_para_movimentacao(db_session, mov.id) is False

    repo.criar(db_session, mov.id, datetime(2026, 1, 1))
    assert repo.existe_para_movimentacao(db_session, mov.id) is True


def test_buscar_pendente_mais_antigo(db_session):
    mov1 = MovimentacaoBuilder().build(db_session)
    mov2 = MovimentacaoBuilder().build(db_session)
    JobValidacaoBuilder(movimentacao_id=mov1.id, criado_em=datetime(2026, 1, 2)).build(db_session)
    mais_antigo = JobValidacaoBuilder(movimentacao_id=mov2.id, criado_em=datetime(2026, 1, 1)).build(
        db_session
    )

    encontrado = repo.buscar_pendente_mais_antigo(db_session)

    assert encontrado.id == mais_antigo.id


def test_buscar_pendente_ignora_outros_status(db_session):
    JobValidacaoBuilder(status=StatusJob.CONCLUIDO).build(db_session)
    JobValidacaoBuilder(status=StatusJob.PROCESSANDO).build(db_session)

    assert repo.buscar_pendente_mais_antigo(db_session) is None


def test_marcar_processando_incrementa_tentativa(db_session):
    job = JobValidacaoBuilder().build(db_session)

    repo.marcar_processando(db_session, job, datetime(2026, 1, 1, 10, 0, 0))

    assert job.status == StatusJob.PROCESSANDO
    assert job.tentativas == 1
    assert job.iniciado_em == datetime(2026, 1, 1, 10, 0, 0)


def test_marcar_concluido(db_session):
    job = JobValidacaoBuilder(status=StatusJob.PROCESSANDO).build(db_session)

    repo.marcar_concluido(db_session, job, datetime(2026, 1, 1, 11, 0, 0))

    assert job.status == StatusJob.CONCLUIDO
    assert job.finalizado_em == datetime(2026, 1, 1, 11, 0, 0)


def test_marcar_para_nova_tentativa_nao_finaliza(db_session):
    job = JobValidacaoBuilder(status=StatusJob.PROCESSANDO).build(db_session)

    repo.marcar_para_nova_tentativa(db_session, job, "erro técnico simulado")

    assert job.status == StatusJob.PENDENTE
    assert job.ultimo_erro == "erro técnico simulado"
    assert job.finalizado_em is None


def test_marcar_erro_terminal(db_session):
    job = JobValidacaoBuilder(status=StatusJob.PROCESSANDO, tentativas=3).build(db_session)

    repo.marcar_erro_terminal(db_session, job, "limite de tentativas esgotado", datetime(2026, 1, 1, 12))

    assert job.status == StatusJob.ERRO
    assert job.finalizado_em == datetime(2026, 1, 1, 12)
