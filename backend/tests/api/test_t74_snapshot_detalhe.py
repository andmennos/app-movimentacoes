"""T-74 — snapshot correto no detalhe (spec.md §7.5/RC-34).

Depois de efetivada, o colaborador já está no estado destino — o detalhe
não pode usar esse estado vivo como origem histórica. Os cinco tipos devem
sempre ler origem/destino das FKs snapshot da própria `Movimentacao`.
"""

from datetime import datetime

import pytest

from app.models import Colaborador, EstadoAprovacao, OrigemExecucao, StatusMovimentacao, TipoMovimentacao
from app.processing import orchestrator
from app.repositories import job_validacao_repository as job_repo
from tests.builders import (
    CargoBuilder,
    CentroCustoBuilder,
    ColaboradorBuilder,
    DepartamentoBuilder,
    MovimentacaoBuilder,
)
from tests.builders.aprovacoes_helper import criar_aprovacoes_exigidas

pytestmark = pytest.mark.usefixtures("admin_headers")


def _apto_com_job(db_session, mov):
    """Mesmo padrão de tests/processing/test_orchestrator.py::_apto_com_job —
    simula o que o producer faz (aprovações concluídas, PENDENTE, job
    criado), sem depender da avaliação real do gate."""
    criar_aprovacoes_exigidas(db_session, mov, estado=EstadoAprovacao.APROVADA)
    mov.status = StatusMovimentacao.PENDENTE
    db_session.commit()
    job_repo.criar(db_session, mov.id, datetime(2026, 1, 1))
    db_session.commit()
    return mov


def _efetivar(db_session, mov):
    saida = orchestrator.processar(db_session, mov.id, OrigemExecucao.AUTOMATICO)
    assert saida.movimentacao.status == StatusMovimentacao.APROVADA, "pré-condição do teste: engine deve aprovar"
    return saida


def test_promocao_pos_efetivacao_preserva_cargo_origem_e_destino(client, db_session):
    """Caso obrigatório de spec §7.5: Júnior 3 -> Pleno 1 efetivada; o
    colaborador já está em Pleno 1, mas o detalhe continua mostrando origem
    Júnior 3 / destino Pleno 1, nunca o estado atual duplicado como origem."""
    origem = CargoBuilder(nivel=3, ordem_progressao=3, familia_cargo="X").build(db_session)
    destino = CargoBuilder(nivel=1, ordem_progressao=4, familia_cargo="X").build(db_session)
    gestor = ColaboradorBuilder().build(db_session)
    colaborador = ColaboradorBuilder(cargo_id=origem.id, gestor_id=gestor.id).build(db_session)
    mov = MovimentacaoBuilder(
        tipo=TipoMovimentacao.PROMOCAO,
        colaborador_id=colaborador.id,
        cargo_origem_id=origem.id,
        cargo_destino_id=destino.id,
    ).build(db_session)
    mov = _apto_com_job(db_session, mov)

    _efetivar(db_session, mov)

    colaborador_atualizado = db_session.get(Colaborador, colaborador.id)
    assert colaborador_atualizado.cargo_id == destino.id  # efetivação real ocorreu

    corpo = client.get(f"/movimentacoes/{mov.id}").json()
    assert corpo["status"] == "APROVADA"
    assert corpo["cargoAtual"]["id"] == origem.id
    assert corpo["cargoDestino"]["id"] == destino.id
    assert corpo["cargoAtual"]["id"] != colaborador_atualizado.cargo_id


def test_transferencia_pos_efetivacao_preserva_departamento_origem(client, db_session):
    dep_origem = DepartamentoBuilder(gestor_id=ColaboradorBuilder().build(db_session).id).build(db_session)
    dep_destino = DepartamentoBuilder(gestor_id=ColaboradorBuilder().build(db_session).id).build(db_session)
    mov = MovimentacaoBuilder(
        tipo=TipoMovimentacao.TRANSFERENCIA,
        departamento_origem_id=dep_origem.id,
        departamento_destino_id=dep_destino.id,
    ).build(db_session)
    mov = _apto_com_job(db_session, mov)

    _efetivar(db_session, mov)

    colaborador = db_session.get(Colaborador, mov.colaborador_id)
    assert colaborador.departamento_id == dep_destino.id

    corpo = client.get(f"/movimentacoes/{mov.id}").json()
    assert corpo["status"] == "APROVADA"
    assert corpo["departamentoOrigem"]["id"] == dep_origem.id
    assert corpo["departamentoDestino"]["id"] == dep_destino.id


def test_troca_gestor_pos_efetivacao_preserva_gestor_origem(client, db_session):
    gestor_atual = ColaboradorBuilder().build(db_session)
    cargo_gestor = CargoBuilder(permite_gestao=True).build(db_session)
    novo_gestor = ColaboradorBuilder(cargo_id=cargo_gestor.id).build(db_session)
    colaborador = ColaboradorBuilder(gestor_id=gestor_atual.id).build(db_session)
    mov = MovimentacaoBuilder(
        tipo=TipoMovimentacao.TROCA_GESTOR,
        colaborador_id=colaborador.id,
        gestor_origem_id=gestor_atual.id,
        gestor_destino_id=novo_gestor.id,
    ).build(db_session)
    mov = _apto_com_job(db_session, mov)

    _efetivar(db_session, mov)

    colaborador_atualizado = db_session.get(Colaborador, colaborador.id)
    assert colaborador_atualizado.gestor_id == novo_gestor.id

    corpo = client.get(f"/movimentacoes/{mov.id}").json()
    assert corpo["status"] == "APROVADA"
    assert corpo["gestorOrigem"]["id"] == gestor_atual.id
    assert corpo["gestorDestino"]["id"] == novo_gestor.id


def test_mudanca_centro_custo_pos_efetivacao_preserva_centro_custo_origem(client, db_session):
    responsavel = ColaboradorBuilder().build(db_session)
    cc_origem = CentroCustoBuilder(responsavel_id=responsavel.id).build(db_session)
    cc_destino = CentroCustoBuilder(responsavel_id=responsavel.id).build(db_session)
    mov = MovimentacaoBuilder(
        tipo=TipoMovimentacao.MUDANCA_CENTRO_CUSTO,
        centro_custo_origem_id=cc_origem.id,
        centro_custo_destino_id=cc_destino.id,
    ).build(db_session)
    mov = _apto_com_job(db_session, mov)

    _efetivar(db_session, mov)

    colaborador = db_session.get(Colaborador, mov.colaborador_id)
    assert colaborador.centro_custo_id == cc_destino.id

    corpo = client.get(f"/movimentacoes/{mov.id}").json()
    assert corpo["status"] == "APROVADA"
    assert corpo["centroCustoOrigem"]["id"] == cc_origem.id
    assert corpo["centroCustoDestino"]["id"] == cc_destino.id


def test_alteracao_estrutura_pos_efetivacao_preserva_estrutura_origem(client, db_session):
    gestor = ColaboradorBuilder().build(db_session)
    colaborador = ColaboradorBuilder(gestor_id=gestor.id).build(db_session)
    mov = MovimentacaoBuilder(tipo=TipoMovimentacao.ALTERACAO_ESTRUTURA, colaborador_id=colaborador.id).build(
        db_session
    )
    origem_id = mov.estrutura_origem_id
    destino_id = mov.estrutura_destino_id
    mov = _apto_com_job(db_session, mov)

    _efetivar(db_session, mov)

    colaborador_atualizado = db_session.get(Colaborador, colaborador.id)
    assert colaborador_atualizado.estrutura_id == destino_id

    corpo = client.get(f"/movimentacoes/{mov.id}").json()
    assert corpo["status"] == "APROVADA"
    assert corpo["estruturaOrigem"]["id"] == origem_id
    assert corpo["estruturaDestino"]["id"] == destino_id
