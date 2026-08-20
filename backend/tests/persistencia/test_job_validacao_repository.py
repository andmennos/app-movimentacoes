from datetime import datetime, timedelta

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


def test_obter_ou_criar_reaproveita_job_existente(db_session):
    mov = MovimentacaoBuilder().build(db_session)
    primeiro = repo.criar(db_session, mov.id, datetime(2026, 1, 1))
    db_session.commit()

    obtido = repo.obter_ou_criar(db_session, mov.id, datetime(2026, 1, 2))

    assert obtido.id == primeiro.id


def test_obter_ou_criar_cria_quando_nao_existe(db_session):
    mov = MovimentacaoBuilder().build(db_session)

    job = repo.obter_ou_criar(db_session, mov.id, datetime(2026, 1, 1))

    assert job.id is not None
    assert job.status == StatusJob.PENDENTE


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


def test_tentar_adquirir_com_sucesso_marca_processando_e_incrementa(db_session):
    job = JobValidacaoBuilder().build(db_session)
    db_session.commit()

    adquiriu = repo.tentar_adquirir(db_session, job.id, datetime(2026, 1, 1, 10, 0, 0))

    assert adquiriu is True
    assert job.status == StatusJob.PROCESSANDO
    assert job.tentativas == 1
    assert job.iniciado_em == datetime(2026, 1, 1, 10, 0, 0)


def test_tentar_adquirir_falha_se_ja_nao_esta_pendente(db_session):
    job = JobValidacaoBuilder(status=StatusJob.PROCESSANDO).build(db_session)
    db_session.commit()

    adquiriu = repo.tentar_adquirir(db_session, job.id, datetime(2026, 1, 1))

    assert adquiriu is False


def test_tentar_adquirir_e_compare_and_set_segunda_chamada_falha(db_session):
    """Prova o "compare-and-set": a primeira aquisição sucede; qualquer
    tentativa seguinte sobre o mesmo job (já não mais PENDENTE) falha —
    impede que duas origens processem o mesmo job (CN-Q11/CN-Q12)."""
    job = JobValidacaoBuilder().build(db_session)
    db_session.commit()

    primeira = repo.tentar_adquirir(db_session, job.id, datetime(2026, 1, 1, 10, 0, 0))
    segunda = repo.tentar_adquirir(db_session, job.id, datetime(2026, 1, 1, 10, 0, 5))

    assert primeira is True
    assert segunda is False
    assert job.tentativas == 1


def test_reabrir_volta_para_pendente(db_session):
    job = JobValidacaoBuilder(status=StatusJob.ERRO).build(db_session)

    repo.reabrir(db_session, job)

    assert job.status == StatusJob.PENDENTE


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


def test_buscar_processando_stale(db_session):
    agora = datetime(2026, 1, 1, 12, 0, 0)
    antigo = JobValidacaoBuilder(status=StatusJob.PROCESSANDO, iniciado_em=agora - timedelta(hours=1)).build(
        db_session
    )
    recente = JobValidacaoBuilder(status=StatusJob.PROCESSANDO, iniciado_em=agora - timedelta(seconds=5)).build(
        db_session
    )
    JobValidacaoBuilder(status=StatusJob.PENDENTE).build(db_session)

    stale = repo.buscar_processando_stale(db_session, limite=agora - timedelta(minutes=5))

    ids = {j.id for j in stale}
    assert antigo.id in ids
    assert recente.id not in ids


def test_marcar_recuperado_volta_pendente_quando_ha_tentativa_disponivel(db_session):
    job = JobValidacaoBuilder(status=StatusJob.PROCESSANDO, tentativas=1).build(db_session)

    novo_status = repo.marcar_recuperado(db_session, job, datetime(2026, 1, 1), limite_tentativas=3)

    assert novo_status == StatusJob.PENDENTE
    assert job.status == StatusJob.PENDENTE


def test_marcar_recuperado_vai_para_erro_quando_limite_esgotado(db_session):
    job = JobValidacaoBuilder(status=StatusJob.PROCESSANDO, tentativas=3).build(db_session)

    novo_status = repo.marcar_recuperado(db_session, job, datetime(2026, 1, 1), limite_tentativas=3)

    assert novo_status == StatusJob.ERRO
    assert job.status == StatusJob.ERRO
    assert job.finalizado_em == datetime(2026, 1, 1)
