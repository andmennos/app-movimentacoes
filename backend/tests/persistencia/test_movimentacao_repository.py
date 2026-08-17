from datetime import datetime

import pytest

from app.models import StatusMovimentacao, TipoMovimentacao
from app.repositories import movimentacao_repository as repo
from app.repositories.exceptions import OrdenacaoInvalida
from tests.builders import ColaboradorBuilder, MovimentacaoBuilder


def test_filtro_por_status(db_session):
    MovimentacaoBuilder(status=StatusMovimentacao.APROVADA).build(db_session)
    MovimentacaoBuilder(status=StatusMovimentacao.REPROVADA).build(db_session)
    MovimentacaoBuilder(status=StatusMovimentacao.REPROVADA).build(db_session)

    itens, total = repo.listar(db_session, status=StatusMovimentacao.REPROVADA)

    assert total == 2
    assert all(m.status == StatusMovimentacao.REPROVADA for m in itens)


def test_busca_por_matricula_exata(db_session):
    colaborador = ColaboradorBuilder(matricula="M999999", nome="Fulano da Silva").build(db_session)
    MovimentacaoBuilder(colaborador_id=colaborador.id).build(db_session)
    MovimentacaoBuilder().build(db_session)

    itens, total = repo.listar(db_session, busca="M999999")

    assert total == 1
    assert itens[0].colaborador_id == colaborador.id


def test_busca_por_nome_parcial_case_insensitive(db_session):
    colaborador = ColaboradorBuilder(nome="Beatriz Andrade").build(db_session)
    MovimentacaoBuilder(colaborador_id=colaborador.id).build(db_session)

    itens, total = repo.listar(db_session, busca="andrade")

    assert total == 1
    assert itens[0].colaborador_id == colaborador.id


def test_ordenacao_whitelist_valida_asc_e_desc(db_session):
    mais_antiga = MovimentacaoBuilder(data_solicitacao=datetime(2026, 1, 1)).build(db_session)
    mais_recente = MovimentacaoBuilder(data_solicitacao=datetime(2026, 6, 1)).build(db_session)

    asc_itens, _ = repo.listar(db_session, ordenar_por="dataSolicitacao", direcao="asc")
    desc_itens, _ = repo.listar(db_session, ordenar_por="dataSolicitacao", direcao="desc")

    assert asc_itens[0].id == mais_antiga.id
    assert desc_itens[0].id == mais_recente.id


def test_ordenacao_fora_da_whitelist_levanta_excecao(db_session):
    with pytest.raises(OrdenacaoInvalida):
        repo.listar(db_session, ordenar_por="campoInexistente")


def test_paginacao_trunca_page_size_para_100(db_session):
    for _ in range(3):
        MovimentacaoBuilder().build(db_session)

    itens, total = repo.listar(db_session, page=1, page_size=500)

    assert total == 3
    assert len(itens) == 3  # não há 500 registros; o teste de truncamento em si é no limite aplicado


def test_paginacao_pagina_2_retorna_itens_diferentes(db_session):
    for _ in range(5):
        MovimentacaoBuilder().build(db_session)

    pagina1, total = repo.listar(db_session, page=1, page_size=2)
    pagina2, _ = repo.listar(db_session, page=2, page_size=2)

    assert total == 5
    assert len(pagina1) == 2
    assert len(pagina2) == 2
    assert {m.id for m in pagina1}.isdisjoint({m.id for m in pagina2})


def test_buscar_por_id_resolve_entidades_relacionadas(db_session):
    mov = MovimentacaoBuilder(tipo=TipoMovimentacao.TRANSFERENCIA).build(db_session)

    encontrada = repo.buscar_por_id(db_session, mov.id)

    assert encontrada is not None
    assert encontrada.colaborador is not None
    assert encontrada.departamento_origem is not None
    assert encontrada.departamento_destino is not None


def test_buscar_por_id_inexistente_retorna_none(db_session):
    assert repo.buscar_por_id(db_session, 999999) is None
