"""Fluxo completo via `POST /validar` — o adaptador síncrono técnico (spec
§7.3, RC-15): listar → detalhar → validar → auditoria persistida → detalhe
reflete a última validação. Um cenário por tipo de movimentação; ao menos um
cenário por resultado possível.

Este arquivo testa o contrato do endpoint em si (exigido pelo case, coberto
no Swagger) — não o fluxo normal do produto. O gatilho automático
(seed → producer → `JobValidacao` → Worker) tem cobertura própria em
`test_fluxo_automatico.py`; o Angular nunca chama `POST /validar`
(`tests/api/test_movimentacoes_api.py`, frontend `*.spec.ts`).
"""

from app.models import EstadoAprovacao, TipoMovimentacao
from tests.builders import (
    CargoBuilder,
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
    assert resultado_validar.status_code == 200

    detalhe_depois = client.get(f"/movimentacoes/{mov.id}")
    assert detalhe_depois.status_code == 200
    assert detalhe_depois.json()["ultimaValidacao"]["resultado"] == resultado_validar.json()["status"]

    return resultado_validar.json()["status"]


def test_fluxo_completo_transferencia_aprovada(client, db_session):
    mov = _transferencia_valida(db_session)
    resultado = _fluxo(client, db_session, mov)
    assert resultado == "APROVADA"


def test_fluxo_completo_transferencia_aguardando_aprovacao(client, db_session):
    mov = _transferencia_valida(db_session)
    resultado = _fluxo(client, db_session, mov, estado_aprovacoes=EstadoAprovacao.PENDENTE)
    assert resultado == "AGUARDANDO_APROVACAO"


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

    resultado = _fluxo(client, db_session, mov)

    assert resultado == "REPROVADA"


def test_fluxo_completo_troca_gestor_aprovada(client, db_session):
    gestor_ativo = ColaboradorBuilder().build(db_session)
    cargo_gestor = CargoBuilder(permite_gestao=True).build(db_session)
    novo_gestor = ColaboradorBuilder(cargo_id=cargo_gestor.id).build(db_session)
    mov = MovimentacaoBuilder(
        tipo=TipoMovimentacao.TROCA_GESTOR,
        gestor_origem_id=gestor_ativo.id,
        gestor_destino_id=novo_gestor.id,
    ).build(db_session)

    resultado = _fluxo(client, db_session, mov)

    assert resultado == "APROVADA"


def test_fluxo_completo_centro_custo_aprovada(client, db_session):
    responsavel = ColaboradorBuilder().build(db_session)
    from tests.builders import CentroCustoBuilder

    cc_destino = CentroCustoBuilder(responsavel_id=responsavel.id).build(db_session)
    mov = MovimentacaoBuilder(
        tipo=TipoMovimentacao.MUDANCA_CENTRO_CUSTO, centro_custo_destino_id=cc_destino.id
    ).build(db_session)

    resultado = _fluxo(client, db_session, mov)

    assert resultado == "APROVADA"


def test_fluxo_completo_estrutura_aprovada(client, db_session):
    gestor = ColaboradorBuilder().build(db_session)
    colaborador = ColaboradorBuilder(gestor_id=gestor.id).build(db_session)
    mov = MovimentacaoBuilder(tipo=TipoMovimentacao.ALTERACAO_ESTRUTURA, colaborador_id=colaborador.id).build(
        db_session
    )

    resultado = _fluxo(client, db_session, mov)

    assert resultado == "APROVADA"
