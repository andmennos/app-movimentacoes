from datetime import datetime

from app.models import EstadoAprovacao, JobValidacao, StatusJob, StatusMovimentacao, TipoMovimentacao
from app.processing import producer
from tests.builders import (
    ColaboradorBuilder,
    DepartamentoBuilder,
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


def test_ca042_todas_aprovadas_cria_job_pendente_e_movimentacao_fica_pendente(db_session):
    mov = _transferencia_valida(db_session)
    criar_aprovacoes_exigidas(db_session, mov, estado=EstadoAprovacao.APROVADA)
    db_session.commit()

    resultado = producer.executar(db_session)

    assert resultado.agendadas == 1
    assert mov.id in resultado.ids_agendados
    db_session.refresh(mov)
    assert mov.status == StatusMovimentacao.PENDENTE
    job = db_session.query(JobValidacao).filter_by(movimentacao_id=mov.id).one()
    assert job.status == StatusJob.PENDENTE


def test_ca040_aprovacao_pendente_nao_cria_job_e_fica_aguardando_aprovacao(db_session):
    mov = _transferencia_valida(db_session)
    criar_aprovacoes_exigidas(db_session, mov, estado=EstadoAprovacao.PENDENTE)
    db_session.commit()

    resultado = producer.executar(db_session)

    assert resultado.agendadas == 0
    assert resultado.aguardando == 1
    assert db_session.query(JobValidacao).filter_by(movimentacao_id=mov.id).count() == 0
    db_session.refresh(mov)
    assert mov.status == StatusMovimentacao.AGUARDANDO_APROVACAO


def test_ca041_aprovacao_reprovada_bloqueia_sem_job(db_session):
    mov = _transferencia_valida(db_session)
    criar_aprovacoes_exigidas(db_session, mov, estado=EstadoAprovacao.REPROVADA)
    db_session.commit()

    resultado = producer.executar(db_session)

    assert resultado.bloqueadas == 1
    assert db_session.query(JobValidacao).filter_by(movimentacao_id=mov.id).count() == 0
    db_session.refresh(mov)
    assert mov.status == StatusMovimentacao.BLOQUEADA


def test_ca043_cnq06_producer_e_idempotente(db_session):
    mov = _transferencia_valida(db_session)
    criar_aprovacoes_exigidas(db_session, mov, estado=EstadoAprovacao.APROVADA)
    db_session.commit()

    primeira = producer.executar(db_session)
    segunda = producer.executar(db_session)

    assert primeira.agendadas == 1
    assert segunda.agendadas == 0
    assert db_session.query(JobValidacao).filter_by(movimentacao_id=mov.id).count() == 1


def test_producer_nao_reprocessa_movimentacao_ja_bloqueada(db_session):
    mov = _transferencia_valida(db_session)
    criar_aprovacoes_exigidas(db_session, mov, estado=EstadoAprovacao.REPROVADA)
    db_session.commit()

    producer.executar(db_session)
    segunda = producer.executar(db_session)

    # mov.status já é BLOQUEADA após a primeira execução — não é mais
    # candidata (query filtra status=AGUARDANDO_APROVACAO) — nenhuma ação.
    assert segunda.bloqueadas == 0
    assert segunda.agendadas == 0


def test_producer_nao_reprocessa_movimentacao_ainda_aguardando(db_session):
    mov = _transferencia_valida(db_session)
    criar_aprovacoes_exigidas(db_session, mov, estado=EstadoAprovacao.PENDENTE)
    db_session.commit()

    producer.executar(db_session)
    segunda = producer.executar(db_session)

    # continua candidata (ainda AGUARDANDO_APROVACAO) — reavaliada, mas o
    # resultado não muda: nenhum evento/job novo.
    assert segunda.aguardando == 1
    db_session.refresh(mov)
    assert mov.status == StatusMovimentacao.AGUARDANDO_APROVACAO


def test_cnq02_multiplas_movimentacoes_resultados_distintos(db_session):
    aprovada = _transferencia_valida(db_session)
    criar_aprovacoes_exigidas(db_session, aprovada, estado=EstadoAprovacao.APROVADA)

    pendente = _transferencia_valida(db_session)
    criar_aprovacoes_exigidas(db_session, pendente, estado=EstadoAprovacao.PENDENTE)

    reprovada = _transferencia_valida(db_session)
    criar_aprovacoes_exigidas(db_session, reprovada, estado=EstadoAprovacao.REPROVADA)

    db_session.commit()

    resultado = producer.executar(db_session)

    assert resultado.agendadas == 1
    assert resultado.aguardando == 1
    assert resultado.bloqueadas == 1


def test_executar_aceita_timestamp_explicito(db_session):
    mov = _transferencia_valida(db_session)
    criar_aprovacoes_exigidas(db_session, mov, estado=EstadoAprovacao.APROVADA)
    db_session.commit()

    agora = datetime(2026, 3, 1, 8, 0, 0)
    producer.executar(db_session, agora=agora)

    job = db_session.query(JobValidacao).filter_by(movimentacao_id=mov.id).one()
    assert job.criado_em == agora


def test_aprovacao_extra_nao_exigida_nao_interfere_no_producer(db_session):
    """CN-Q20 no nível do producer: uma aprovação extra reprovada (não
    exigida pelo tipo) não impede o agendamento."""
    from app.models import Aprovacao, EstadoAprovacao as EA, TipoAprovacao

    mov = _transferencia_valida(db_session)
    criar_aprovacoes_exigidas(db_session, mov, estado=EstadoAprovacao.APROVADA)
    aprovador = ColaboradorBuilder().build(db_session)
    db_session.add(
        Aprovacao(
            movimentacao_id=mov.id,
            tipo=TipoAprovacao.GERENCIA,
            estado=EA.REPROVADA,
            aprovador_id=aprovador.id,
        )
    )
    db_session.commit()

    resultado = producer.executar(db_session)

    assert resultado.agendadas == 1
