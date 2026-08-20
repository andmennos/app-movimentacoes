"""Fluxo automático de ponta a ponta: seed-like data → producer → gate →
`JobValidacao` → Worker → orquestrador → auditoria → efetivação → `GET`
detalhe. Complementa `test_fluxo_completo.py` (que cobre `POST /validar` como
adaptador síncrono) e `test_orchestrator.py` (que cobre os cenários de
corrida/duplicidade/stale em detalhe).
"""

import pytest

from app.models import (
    Colaborador,
    EstadoAprovacao,
    JobValidacao,
    StatusMovimentacao,
    TipoMovimentacao,
    ValidacaoAuditoria,
)
from app.processing import producer, worker
from tests.builders import ColaboradorBuilder, DepartamentoBuilder, MovimentacaoBuilder, criar_aprovacoes_exigidas

pytestmark = pytest.mark.usefixtures("admin_headers")


def _transferencia_valida(db_session):
    dep_origem = DepartamentoBuilder(gestor_id=ColaboradorBuilder().build(db_session).id).build(db_session)
    dep_destino = DepartamentoBuilder(gestor_id=ColaboradorBuilder().build(db_session).id).build(db_session)
    return MovimentacaoBuilder(
        tipo=TipoMovimentacao.TRANSFERENCIA,
        departamento_origem_id=dep_origem.id,
        departamento_destino_id=dep_destino.id,
    ).build(db_session)


def test_fluxo_automatico_aprovada_ponta_a_ponta(client, db_session):
    mov = _transferencia_valida(db_session)
    criar_aprovacoes_exigidas(db_session, mov, estado=EstadoAprovacao.APROVADA)
    db_session.commit()
    destino_id = mov.departamento_destino_id
    colaborador_id = mov.colaborador_id

    resultado_producer = producer.executar(db_session)
    assert resultado_producer.agendadas == 1

    processou = worker.processar_um_job(db_session)
    assert processou is True

    detalhe = client.get(f"/movimentacoes/{mov.id}")
    corpo = detalhe.json()
    assert corpo["status"] == "APROVADA"
    assert corpo["ultimaValidacao"]["resultado"] == "APROVADA"
    assert corpo["ultimaValidacao"]["inconsistencias"] == []
    assert corpo["processamento"]["podeValidarManualmente"] is False
    assert any(e["tipoEvento"] == "MOVIMENTACAO_EFETIVADA" for e in corpo["historicoProcessamento"])
    assert db_session.query(ValidacaoAuditoria).filter_by(movimentacao_id=mov.id).count() == 1
    assert db_session.get(Colaborador, colaborador_id).departamento_id == destino_id


def test_fluxo_automatico_reprovada_por_inconsistencias_ponta_a_ponta(client, db_session):
    dep_origem = DepartamentoBuilder(gestor_id=ColaboradorBuilder().build(db_session).id).build(db_session)
    dep_destino = DepartamentoBuilder(
        ativo=False, gestor_id=ColaboradorBuilder().build(db_session).id
    ).build(db_session)
    mov = MovimentacaoBuilder(
        tipo=TipoMovimentacao.TRANSFERENCIA,
        departamento_origem_id=dep_origem.id,
        departamento_destino_id=dep_destino.id,
    ).build(db_session)
    criar_aprovacoes_exigidas(db_session, mov, estado=EstadoAprovacao.APROVADA)
    db_session.commit()

    resultado_producer = producer.executar(db_session)
    assert resultado_producer.agendadas == 1  # gate só olha o estado das aprovações, não T04

    worker.processar_um_job(db_session)

    detalhe = client.get(f"/movimentacoes/{mov.id}")
    corpo = detalhe.json()
    assert corpo["status"] == "REPROVADA"
    assert corpo["ultimaValidacao"]["resultado"] == "REPROVADA"
    assert len(corpo["ultimaValidacao"]["inconsistencias"]) >= 1
    assert any(i["codigo"] == "T04" for i in corpo["ultimaValidacao"]["inconsistencias"])
    assert corpo["processamento"]["podeValidarManualmente"] is False


def test_fluxo_automatico_aguardando_aprovacao_sem_job_sem_validacao(client, db_session):
    mov = _transferencia_valida(db_session)
    criar_aprovacoes_exigidas(db_session, mov, estado=EstadoAprovacao.PENDENTE)
    db_session.commit()

    resultado_producer = producer.executar(db_session)
    assert resultado_producer.agendadas == 0
    assert db_session.query(JobValidacao).filter_by(movimentacao_id=mov.id).count() == 0

    processou = worker.processar_um_job(db_session)
    assert processou is False  # fila vazia — nada a consumir

    detalhe = client.get(f"/movimentacoes/{mov.id}")
    corpo = detalhe.json()
    assert corpo["status"] == "AGUARDANDO_APROVACAO"
    assert corpo["ultimaValidacao"] is None
    assert len(corpo["impedimentos"]) >= 1
    assert corpo["processamento"]["podeValidarManualmente"] is False
    assert db_session.query(ValidacaoAuditoria).filter_by(movimentacao_id=mov.id).count() == 0


def test_fluxo_automatico_reprovada_pelo_gate_bloqueia_sem_job_nem_auditoria(client, db_session):
    mov = _transferencia_valida(db_session)
    criar_aprovacoes_exigidas(db_session, mov, estado=EstadoAprovacao.REPROVADA)
    db_session.commit()

    resultado_producer = producer.executar(db_session)
    assert resultado_producer.bloqueadas == 1
    assert db_session.query(JobValidacao).filter_by(movimentacao_id=mov.id).count() == 0

    detalhe = client.get(f"/movimentacoes/{mov.id}")
    corpo = detalhe.json()
    assert corpo["status"] == "BLOQUEADA"
    # bloqueada pelo gate, não pela engine: nunca houve validação executada
    assert corpo["ultimaValidacao"] is None
    assert any(i["codigo"] == "APROVACAO_REPROVADA" for i in corpo["impedimentos"])
    assert corpo["processamento"]["podeValidarManualmente"] is False
    assert db_session.query(ValidacaoAuditoria).filter_by(movimentacao_id=mov.id).count() == 0


def test_worker_e_manual_usam_o_mesmo_orquestrador(db_session):
    """INV-09: prova, por identidade de objeto, que não existem duas
    implementações do caso de uso de processamento."""
    from app.processing import orchestrator

    assert worker.orchestrator is orchestrator
