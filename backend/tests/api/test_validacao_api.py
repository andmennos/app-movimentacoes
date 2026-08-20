import pytest

from app.models import TipoMovimentacao
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


def test_retorna_todas_as_inconsistencias_com_campos_completos(client, db_session):
    """Aprovações concluídas (gate apto) e um único defeito de negócio (T04):
    a engine roda e reprova — isso não é mais confundido com aprovação
    pendente/reprovada (spec RC-22)."""
    dep_origem = DepartamentoBuilder(gestor_id=ColaboradorBuilder().build(db_session).id).build(db_session)
    dep_destino = DepartamentoBuilder(
        ativo=False, gestor_id=ColaboradorBuilder().build(db_session).id
    ).build(db_session)
    mov = MovimentacaoBuilder(
        tipo=TipoMovimentacao.TRANSFERENCIA,
        departamento_origem_id=dep_origem.id,
        departamento_destino_id=dep_destino.id,
    ).build(db_session)
    criar_aprovacoes_exigidas(db_session, mov)
    db_session.commit()

    resposta = client.post("/validar", json={"movimentacaoId": mov.id})

    assert resposta.status_code == 200
    corpo = resposta.json()
    assert corpo["status"] == "REPROVADA"
    assert len(corpo["inconsistencias"]) >= 1
    for inc in corpo["inconsistencias"]:
        assert set(inc.keys()) == {"codigo", "mensagem", "severidade"}
        assert inc["severidade"] == "ERRO"


def test_status_e_resultado_atualizados_apos_validar(client, db_session):
    mov = _transferencia_valida(db_session)
    criar_aprovacoes_exigidas(db_session, mov)
    db_session.commit()

    resposta = client.post("/validar", json={"movimentacaoId": mov.id})

    assert resposta.status_code == 200
    assert resposta.json()["status"] == "APROVADA"

    detalhe = client.get(f"/movimentacoes/{mov.id}")
    corpo = detalhe.json()
    assert corpo["status"] == "APROVADA"
    assert corpo["ultimaValidacao"]["resultado"] == "APROVADA"
    assert corpo["ultimaValidacao"]["inconsistencias"] == []


def test_404_ao_validar_id_inexistente(client):
    resposta = client.post("/validar", json={"movimentacaoId": 999999})
    assert resposta.status_code == 404
    assert resposta.json()["erro"]["codigo"] == "MOVIMENTACAO_NAO_ENCONTRADA"


def test_422_payload_invalido(client):
    resposta = client.post("/validar", json={"campoErrado": "x"})
    assert resposta.status_code == 422
    assert resposta.json()["erro"]["codigo"] == "PAYLOAD_INVALIDO"


def test_cria_exatamente_um_registro_de_auditoria(client, db_session):
    mov = _transferencia_valida(db_session)
    criar_aprovacoes_exigidas(db_session, mov)
    db_session.commit()

    client.post("/validar", json={"movimentacaoId": mov.id})

    from app.models import ValidacaoAuditoria

    total = db_session.query(ValidacaoAuditoria).filter_by(movimentacao_id=mov.id).count()
    assert total == 1


def test_409_aprovacao_pendente_nao_executa_engine(client, db_session):
    from app.models import EstadoAprovacao

    mov = _transferencia_valida(db_session)
    criar_aprovacoes_exigidas(db_session, mov, estado=EstadoAprovacao.PENDENTE)
    db_session.commit()

    resposta = client.post("/validar", json={"movimentacaoId": mov.id})

    assert resposta.status_code == 409
    corpo = resposta.json()
    assert corpo["erro"]["codigo"] == "VALIDACAO_MANUAL_NAO_PERMITIDA"
    assert len(corpo["impedimentos"]) >= 1

    from app.models import ValidacaoAuditoria

    assert db_session.query(ValidacaoAuditoria).filter_by(movimentacao_id=mov.id).count() == 0


def test_409_job_processando_saudavel(client, db_session):
    from datetime import datetime, timezone

    from app.repositories import job_validacao_repository as job_repo

    mov = _transferencia_valida(db_session)
    criar_aprovacoes_exigidas(db_session, mov)
    db_session.commit()
    job = job_repo.criar(db_session, mov.id, datetime(2026, 1, 1))
    db_session.commit()
    agora = datetime.now(timezone.utc).replace(tzinfo=None)
    job_repo.tentar_adquirir(db_session, job.id, agora)

    resposta = client.post("/validar", json={"movimentacaoId": mov.id})

    assert resposta.status_code == 409
    assert resposta.json()["erro"]["codigo"] == "VALIDACAO_EM_ANDAMENTO"


def test_500_erro_interno_em_falha_tecnica_nao_tratada(client, db_session, monkeypatch):
    mov = _transferencia_valida(db_session)
    criar_aprovacoes_exigidas(db_session, mov)
    db_session.commit()

    from app.services import validacao_service

    def quebrar(ctx):
        raise RuntimeError("falha inesperada simulada")

    monkeypatch.setattr(validacao_service, "executar", quebrar)

    resposta = client.post("/validar", json={"movimentacaoId": mov.id})

    assert resposta.status_code == 500
    assert resposta.json()["erro"]["codigo"] == "ERRO_INTERNO"

    detalhe = client.get(f"/movimentacoes/{mov.id}")
    assert detalhe.json()["status"] == "PENDENTE"
    assert detalhe.json()["ultimaValidacao"] is None
