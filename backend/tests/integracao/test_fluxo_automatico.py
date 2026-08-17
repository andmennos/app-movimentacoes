"""T-26 (revisão) — fluxo automático de ponta a ponta: seed-like data →
producer → `JobValidacao` → Worker → auditoria → `GET` detalhe. Complementa
`test_fluxo_completo.py`, que cobre `POST /validar` como adaptador síncrono
técnico — este arquivo cobre o gatilho **automático** que o Angular observa
apenas por leitura.
"""

from app.models import EstadoAprovacao, JobValidacao, StatusMovimentacao, TipoMovimentacao, ValidacaoAuditoria
from app.processing import producer, worker
from tests.builders import ColaboradorBuilder, DepartamentoBuilder, MovimentacaoBuilder, criar_aprovacoes_exigidas


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

    resultado_producer = producer.executar(db_session)
    assert resultado_producer.agendadas == 1

    processou = worker.processar_um_job(db_session)
    assert processou is True

    detalhe = client.get(f"/movimentacoes/{mov.id}")
    corpo = detalhe.json()
    assert corpo["status"] == "APROVADA"
    assert corpo["ultimaValidacao"]["resultado"] == "APROVADA"
    assert corpo["ultimaValidacao"]["inconsistencias"] == []
    assert db_session.query(ValidacaoAuditoria).filter_by(movimentacao_id=mov.id).count() == 1


def test_fluxo_automatico_reprovada_por_inconsistencias_ponta_a_ponta(client, db_session):
    # departamentos com gestor válido dos dois lados (senão GESTOR_ORIGEM/
    # DESTINO ficam sem responsável esperado e o gate classifica como
    # ANOMALO — não é o que este teste quer isolar). O destino, além disso,
    # está inativo: o único defeito de regra é T04; a aprovação em si
    # permanece íntegra, então o gate agenda normalmente e é a engine, no
    # Worker, que reprova.
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
    assert resultado_producer.agendadas == 1  # gate só olha estado/integridade das aprovações, não T04

    worker.processar_um_job(db_session)

    detalhe = client.get(f"/movimentacoes/{mov.id}")
    corpo = detalhe.json()
    assert corpo["status"] == "REPROVADA"
    assert corpo["ultimaValidacao"]["resultado"] == "REPROVADA"
    assert len(corpo["ultimaValidacao"]["inconsistencias"]) >= 1
    assert any(i["codigo"] == "T04" for i in corpo["ultimaValidacao"]["inconsistencias"])


def test_fluxo_automatico_pendente_sem_job_sem_validacao(client, db_session):
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
    assert corpo["status"] == "PENDENTE"
    assert corpo["ultimaValidacao"] is None
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
    assert corpo["status"] == "REPROVADA"
    # bloqueada pelo gate, não pela engine: nunca houve validação executada
    assert corpo["ultimaValidacao"] is None
    assert db_session.query(ValidacaoAuditoria).filter_by(movimentacao_id=mov.id).count() == 0


def test_post_validar_continua_funcional_como_adaptador_sincrono(client, db_session):
    """`POST /validar` permanece disponível e funcional (spec §7.3, RC-15),
    usado diretamente sem passar por producer/worker."""
    mov = _transferencia_valida(db_session)
    criar_aprovacoes_exigidas(db_session, mov, estado=EstadoAprovacao.APROVADA)
    db_session.commit()

    resposta = client.post("/validar", json={"movimentacaoId": mov.id})

    assert resposta.status_code == 200
    assert resposta.json()["status"] == "APROVADA"
    # nenhum job foi criado — o adaptador síncrono não passa pela fila
    assert db_session.query(JobValidacao).filter_by(movimentacao_id=mov.id).count() == 0


def test_worker_usa_o_mesmo_validacao_service_do_endpoint_sincrono(db_session):
    """INV-11: prova, por identidade de objeto, que não existem duas
    implementações do caso de uso de validação."""
    from app.services import validacao_service

    assert worker.validacao_service is validacao_service
