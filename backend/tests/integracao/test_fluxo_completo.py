"""Fluxo completo via `POST /validar` — o adaptador síncrono técnico (spec
§8.3): listar → detalhar → validar → auditoria persistida → detalhe reflete
a última validação. Um cenário por tipo de movimentação; ao menos um cenário
por resultado possível.

Este arquivo testa o contrato do endpoint em si (exigido pelo case, coberto
no Swagger) — não o fluxo normal do produto. O gatilho automático
(seed → producer → `JobValidacao` → Worker) tem cobertura própria em
`test_fluxo_automatico.py`; o Angular nunca chama `POST /validar` fora do
botão manual condicional (`tests/api/test_movimentacoes_api.py`, frontend
`*.spec.ts`).
"""

import pytest

from app.models import EstadoAprovacao, TipoMovimentacao
from tests.builders import (
    CargoBuilder,
    ColaboradorBuilder,
    DepartamentoBuilder,
    MovimentacaoBuilder,
    criar_aprovacoes_exigidas,
)

pytestmark = pytest.mark.usefixtures("admin_headers")


def _transferencia_valida(db_session):
    dep_origem = DepartamentoBuilder(gestor_id=ColaboradorBuilder().build(db_session).id).build(db_session)
    dep_destino = DepartamentoBuilder(gestor_id=ColaboradorBuilder().build(db_session).id).build(db_session)
    return MovimentacaoBuilder(
        tipo=TipoMovimentacao.TRANSFERENCIA,
        departamento_origem_id=dep_origem.id,
        departamento_destino_id=dep_destino.id,
    ).build(db_session)


def _fluxo(client, db_session, mov, estado_aprovacoes=EstadoAprovacao.APROVADA):
    criar_aprovacoes_exigidas(db_session, mov, estado=estado_aprovacoes)
    db_session.commit()

    listagem = client.get("/movimentacoes")
    assert listagem.status_code == 200
    assert any(i["id"] == mov.id for i in listagem.json()["items"])

    detalhe_antes = client.get(f"/movimentacoes/{mov.id}")
    assert detalhe_antes.status_code == 200
    assert detalhe_antes.json()["ultimaValidacao"] is None

    resultado_validar = client.post("/validar", json={"movimentacaoId": mov.id})

    if resultado_validar.status_code == 200:
        detalhe_depois = client.get(f"/movimentacoes/{mov.id}")
        assert detalhe_depois.status_code == 200
        assert detalhe_depois.json()["ultimaValidacao"]["resultado"] == resultado_validar.json()["status"]

    return resultado_validar


def test_fluxo_completo_transferencia_aprovada(client, db_session):
    mov = _transferencia_valida(db_session)
    resposta = _fluxo(client, db_session, mov)
    assert resposta.status_code == 200
    assert resposta.json()["status"] == "APROVADA"


def test_fluxo_completo_transferencia_com_aprovacao_pendente_retorna_409(client, db_session):
    mov = _transferencia_valida(db_session)
    resposta = _fluxo(client, db_session, mov, estado_aprovacoes=EstadoAprovacao.PENDENTE)
    assert resposta.status_code == 409
    corpo = resposta.json()
    assert corpo["erro"]["codigo"] == "VALIDACAO_MANUAL_NAO_PERMITIDA"
    assert any(i["codigo"] == "APROVACAO_PENDENTE" for i in corpo["impedimentos"])

    detalhe = client.get(f"/movimentacoes/{mov.id}")
    assert detalhe.json()["status"] == "AGUARDANDO_APROVACAO"


def test_fluxo_completo_transferencia_com_aprovacao_reprovada_retorna_409(client, db_session):
    mov = _transferencia_valida(db_session)
    resposta = _fluxo(client, db_session, mov, estado_aprovacoes=EstadoAprovacao.REPROVADA)
    assert resposta.status_code == 409
    corpo = resposta.json()
    assert corpo["erro"]["codigo"] == "VALIDACAO_MANUAL_NAO_PERMITIDA"
    assert any(i["codigo"] == "APROVACAO_REPROVADA" for i in corpo["impedimentos"])

    detalhe = client.get(f"/movimentacoes/{mov.id}")
    assert detalhe.json()["status"] == "BLOQUEADA"


def test_fluxo_completo_promocao_reprovada_por_defeito(client, db_session):
    cargo_baixo = CargoBuilder(nivel=1).build(db_session)
    colaborador = ColaboradorBuilder(cargo_id=cargo_baixo.id, gestor_id=ColaboradorBuilder().build(db_session).id).build(
        db_session
    )
    mov = MovimentacaoBuilder(
        tipo=TipoMovimentacao.PROMOCAO,
        colaborador_id=colaborador.id,
        cargo_origem_id=cargo_baixo.id,
        cargo_destino_id=cargo_baixo.id,  # P03: nível não superior
    ).build(db_session)

    resposta = _fluxo(client, db_session, mov)

    assert resposta.status_code == 200
    assert resposta.json()["status"] == "REPROVADA"


def test_fluxo_completo_troca_gestor_aprovada(client, db_session):
    gestor_ativo = ColaboradorBuilder().build(db_session)
    cargo_gestor = CargoBuilder(permite_gestao=True).build(db_session)
    novo_gestor = ColaboradorBuilder(cargo_id=cargo_gestor.id).build(db_session)
    colaborador = ColaboradorBuilder(gestor_id=gestor_ativo.id).build(db_session)
    mov = MovimentacaoBuilder(
        tipo=TipoMovimentacao.TROCA_GESTOR,
        colaborador_id=colaborador.id,
        gestor_origem_id=gestor_ativo.id,
        gestor_destino_id=novo_gestor.id,
    ).build(db_session)

    resposta = _fluxo(client, db_session, mov)

    assert resposta.status_code == 200
    assert resposta.json()["status"] == "APROVADA"


def test_fluxo_completo_centro_custo_aprovada(client, db_session):
    responsavel = ColaboradorBuilder().build(db_session)
    from tests.builders import CentroCustoBuilder

    cc_destino = CentroCustoBuilder(responsavel_id=responsavel.id).build(db_session)
    mov = MovimentacaoBuilder(
        tipo=TipoMovimentacao.MUDANCA_CENTRO_CUSTO, centro_custo_destino_id=cc_destino.id
    ).build(db_session)

    resposta = _fluxo(client, db_session, mov)

    assert resposta.status_code == 200
    assert resposta.json()["status"] == "APROVADA"


def test_fluxo_completo_estrutura_aprovada(client, db_session):
    gestor = ColaboradorBuilder().build(db_session)
    colaborador = ColaboradorBuilder(gestor_id=gestor.id).build(db_session)
    mov = MovimentacaoBuilder(tipo=TipoMovimentacao.ALTERACAO_ESTRUTURA, colaborador_id=colaborador.id).build(
        db_session
    )

    resposta = _fluxo(client, db_session, mov)

    assert resposta.status_code == 200
    assert resposta.json()["status"] == "APROVADA"


def test_segunda_chamada_apos_aprovada_retorna_409_terminal(client, db_session):
    mov = _transferencia_valida(db_session)
    primeira = _fluxo(client, db_session, mov)
    assert primeira.status_code == 200

    segunda = client.post("/validar", json={"movimentacaoId": mov.id})

    assert segunda.status_code == 409
    assert segunda.json()["erro"]["codigo"] == "VALIDACAO_MANUAL_NAO_PERMITIDA"
