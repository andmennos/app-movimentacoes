from datetime import datetime, timedelta

import pytest

from app.models import StatusMovimentacao
from tests.builders import ColaboradorBuilder, MovimentacaoBuilder

pytestmark = pytest.mark.usefixtures("admin_headers")


def test_ca001_listagem_default_traz_primeira_pagina(client, db_session):
    for i in range(3):
        MovimentacaoBuilder(data_solicitacao=datetime(2026, 1, 1) + timedelta(days=i)).build(db_session)
    db_session.commit()

    resposta = client.get("/movimentacoes")

    assert resposta.status_code == 200
    corpo = resposta.json()
    assert corpo["page"] == 1
    assert corpo["pageSize"] == 20
    assert corpo["total"] == 3
    assert len(corpo["items"]) == 3


def test_ca002_page_size_acima_de_100_e_truncado(client, db_session):
    MovimentacaoBuilder().build(db_session)
    db_session.commit()

    resposta = client.get("/movimentacoes", params={"pageSize": 500})

    assert resposta.status_code == 200
    assert resposta.json()["pageSize"] == 100


def test_ca003_filtro_por_status(client, db_session):
    MovimentacaoBuilder(status=StatusMovimentacao.APROVADA).build(db_session)
    MovimentacaoBuilder(status=StatusMovimentacao.REPROVADA).build(db_session)
    db_session.commit()

    resposta = client.get("/movimentacoes", params={"status": "REPROVADA"})

    assert resposta.status_code == 200
    corpo = resposta.json()
    assert corpo["total"] == 1
    assert corpo["items"][0]["status"] == "REPROVADA"


def test_ca004_busca_por_matricula_exata_e_nome_parcial(client, db_session):
    colaborador = ColaboradorBuilder(matricula="M555555", nome="Carla Nogueira").build(db_session)
    MovimentacaoBuilder(colaborador_id=colaborador.id).build(db_session)
    MovimentacaoBuilder().build(db_session)
    db_session.commit()

    por_matricula = client.get("/movimentacoes", params={"busca": "M555555"})
    por_nome = client.get("/movimentacoes", params={"busca": "nogueira"})

    assert por_matricula.json()["total"] == 1
    assert por_nome.json()["total"] == 1


def test_e2e03_busca_por_id_da_movimentacao(client, db_session):
    """spec.md RC-46/T-84 — termo numérico filtra por ID sem remover a busca
    textual por matrícula/nome (as três continuam funcionando). Não assume
    `total == 1`: nomes/matrículas auto-gerados por outros builders no mesmo
    teste podem coincidir por substring com o ID buscado (contador global) —
    a asserção real é que o alvo aparece e o ID inexistente não aparece."""
    colaborador = ColaboradorBuilder(matricula="M777777", nome="Bruno Salgado").build(db_session)
    alvo = MovimentacaoBuilder(colaborador_id=colaborador.id).build(db_session)
    MovimentacaoBuilder().build(db_session)
    db_session.commit()

    por_id = client.get("/movimentacoes", params={"busca": str(alvo.id)})
    assert alvo.id in [item["id"] for item in por_id.json()["items"]]

    por_matricula = client.get("/movimentacoes", params={"busca": "M777777"})
    assert por_matricula.json()["total"] == 1
    assert por_matricula.json()["items"][0]["id"] == alvo.id

    por_nome = client.get("/movimentacoes", params={"busca": "salgado"})
    assert por_nome.json()["total"] == 1
    assert por_nome.json()["items"][0]["id"] == alvo.id

    id_inexistente = 999_999_999
    sem_correspondencia = client.get("/movimentacoes", params={"busca": str(id_inexistente)})
    assert alvo.id not in [item["id"] for item in sem_correspondencia.json()["items"]]


def test_ca005_ordenacao_valida_e_invalida(client, db_session):
    MovimentacaoBuilder(data_solicitacao=datetime(2026, 1, 1)).build(db_session)
    MovimentacaoBuilder(data_solicitacao=datetime(2026, 6, 1)).build(db_session)
    db_session.commit()

    asc = client.get("/movimentacoes", params={"ordenarPor": "dataSolicitacao", "direcao": "asc"})
    invalida = client.get("/movimentacoes", params={"ordenarPor": "campoLixo"})

    assert asc.status_code == 200
    assert invalida.status_code == 400
    assert invalida.json()["erro"]["codigo"] == "PARAMETRO_INVALIDO"


def test_ca006_a_ca008_detalhe_resolve_entidades_e_ultima_validacao(client, db_session):
    mov = MovimentacaoBuilder().build(db_session)
    db_session.commit()

    resposta = client.get(f"/movimentacoes/{mov.id}")

    assert resposta.status_code == 200
    corpo = resposta.json()
    assert corpo["id"] == mov.id
    assert corpo["departamentoOrigem"] is not None
    assert corpo["departamentoDestino"] is not None
    assert corpo["aprovacoes"] == []
    assert corpo["ultimaValidacao"] is None


def test_campos_de_cargo_aparecem_apenas_em_promocao(client, db_session):
    from app.models import TipoMovimentacao

    transferencia = MovimentacaoBuilder(tipo=TipoMovimentacao.TRANSFERENCIA).build(db_session)
    promocao = MovimentacaoBuilder(tipo=TipoMovimentacao.PROMOCAO).build(db_session)
    db_session.commit()

    resp_transferencia = client.get(f"/movimentacoes/{transferencia.id}").json()
    resp_promocao = client.get(f"/movimentacoes/{promocao.id}").json()

    assert resp_transferencia["cargoAtual"] is None
    assert resp_transferencia["cargoDestino"] is None
    assert resp_promocao["cargoAtual"] is not None
    assert resp_promocao["cargoDestino"] is not None


def test_ca015_404_para_id_inexistente(client):
    detalhe = client.get("/movimentacoes/999999")
    assert detalhe.status_code == 404
    assert detalhe.json()["erro"]["codigo"] == "MOVIMENTACAO_NAO_ENCONTRADA"


def test_resultado_ultima_validacao_nulo_quando_nunca_validada(client, db_session):
    mov = MovimentacaoBuilder().build(db_session)
    db_session.commit()

    resposta = client.get("/movimentacoes")

    item = next(i for i in resposta.json()["items"] if i["id"] == mov.id)
    assert item["resultadoUltimaValidacao"] is None
