from app.models import TipoMovimentacao
from tests.builders import ColaboradorBuilder, DepartamentoBuilder, MovimentacaoBuilder, criar_aprovacoes_exigidas


def _transferencia_valida(db_session):
    dep_origem = DepartamentoBuilder(gestor_id=ColaboradorBuilder().build(db_session).id).build(db_session)
    dep_destino = DepartamentoBuilder(gestor_id=ColaboradorBuilder().build(db_session).id).build(db_session)
    return MovimentacaoBuilder(
        tipo=TipoMovimentacao.TRANSFERENCIA,
        departamento_origem_id=dep_origem.id,
        departamento_destino_id=dep_destino.id,
    ).build(db_session)


def test_ca009_ca011_retorna_todas_as_inconsistencias_com_campos_completos(client, db_session):
    dep_destino = DepartamentoBuilder(ativo=False).build(db_session)
    mov = MovimentacaoBuilder(
        tipo=TipoMovimentacao.TRANSFERENCIA, departamento_destino_id=dep_destino.id
    ).build(db_session)
    db_session.commit()

    resposta = client.post("/validar", json={"movimentacaoId": mov.id})

    assert resposta.status_code == 200
    corpo = resposta.json()
    assert corpo["status"] == "REPROVADA"
    assert len(corpo["inconsistencias"]) >= 1
    for inc in corpo["inconsistencias"]:
        assert set(inc.keys()) == {"codigo", "mensagem", "severidade"}
        assert inc["severidade"] == "ERRO"


def test_ca014_status_e_resultado_atualizados_apos_validar(client, db_session):
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


def test_ca015_404_ao_validar_id_inexistente(client):
    resposta = client.post("/validar", json={"movimentacaoId": 999999})
    assert resposta.status_code == 404
    assert resposta.json()["erro"]["codigo"] == "MOVIMENTACAO_NAO_ENCONTRADA"


def test_422_payload_invalido(client):
    resposta = client.post("/validar", json={"campoErrado": "x"})
    assert resposta.status_code == 422
    assert resposta.json()["erro"]["codigo"] == "PAYLOAD_INVALIDO"


def test_ca012_cria_exatamente_um_registro_de_auditoria(client, db_session):
    mov = _transferencia_valida(db_session)
    criar_aprovacoes_exigidas(db_session, mov)
    db_session.commit()

    client.post("/validar", json={"movimentacaoId": mov.id})

    from app.models import ValidacaoAuditoria

    total = db_session.query(ValidacaoAuditoria).filter_by(movimentacao_id=mov.id).count()
    assert total == 1


def test_500_erro_interno_em_excecao_nao_tratada(client, db_session, monkeypatch):
    # `client` (fixture) usa raise_server_exceptions=True, útil para pegar bugs
    # reais durante o desenvolvimento. Este teste verifica especificamente o
    # contrato HTTP de erro (spec §8.4), então precisa que a exceção vire uma
    # resposta 500 em vez de propagar no processo de teste — daí um TestClient
    # local com raise_server_exceptions=False, reaproveitando o override de
    # sessão já configurado pela fixture `client`.
    from fastapi.testclient import TestClient

    from app.main import app

    mov = _transferencia_valida(db_session)
    criar_aprovacoes_exigidas(db_session, mov)
    db_session.commit()

    from app.services import validacao_service

    def quebrar(ctx):
        raise RuntimeError("falha inesperada simulada")

    monkeypatch.setattr(validacao_service, "executar", quebrar)

    with TestClient(app, raise_server_exceptions=False) as client_tolerante:
        resposta = client_tolerante.post("/validar", json={"movimentacaoId": mov.id})

        assert resposta.status_code == 500
        assert resposta.json()["erro"]["codigo"] == "ERRO_INTERNO"

        detalhe = client_tolerante.get(f"/movimentacoes/{mov.id}")
        assert detalhe.json()["status"] == "PENDENTE"
        assert detalhe.json()["ultimaValidacao"] is None
