import pytest
from sqlalchemy import inspect
from sqlalchemy.exc import IntegrityError

from app.models import Aprovacao, EstadoAprovacao, TipoAprovacao
from tests.builders import MovimentacaoBuilder


def _nomes_colunas_indexadas(inspector, tabela):
    resultado = []
    for indice in inspector.get_indexes(tabela):
        resultado.append(tuple(indice["column_names"]))
    return resultado


def test_indices_de_movimentacao(engine):
    inspector = inspect(engine)
    indices = _nomes_colunas_indexadas(inspector, "movimentacao")
    assert ("colaborador_id",) in indices
    assert ("status",) in indices
    assert ("data_solicitacao",) in indices
    assert ("colaborador_id", "tipo", "status") in indices


def test_indices_de_colaborador(engine):
    inspector = inspect(engine)
    indices = _nomes_colunas_indexadas(inspector, "colaborador")
    assert ("matricula",) in indices
    assert ("nome",) in indices


def test_indice_de_aprovacao(engine):
    inspector = inspect(engine)
    indices = _nomes_colunas_indexadas(inspector, "aprovacao")
    assert ("movimentacao_id",) in indices


def test_indice_de_validacao_auditoria(engine):
    inspector = inspect(engine)
    indices = _nomes_colunas_indexadas(inspector, "validacao_auditoria")
    assert ("movimentacao_id", "data_hora") in indices


def test_indice_de_historico_processamento(engine):
    inspector = inspect(engine)
    indices = _nomes_colunas_indexadas(inspector, "historico_processamento")
    assert ("movimentacao_id", "data_hora", "id") in indices


def test_cnq19_unique_aprovacao_movimentacao_tipo(engine):
    inspector = inspect(engine)
    unicos = inspector.get_unique_constraints("aprovacao")
    colunas_unicas = {tuple(u["column_names"]) for u in unicos}
    indices_unicos = {
        tuple(i["column_names"]) for i in inspector.get_indexes("aprovacao") if i["unique"]
    }
    assert ("movimentacao_id", "tipo") in (colunas_unicas | indices_unicos)


def test_cnq19_persistir_aprovacao_duplicada_falha(db_session):
    mov = MovimentacaoBuilder().build(db_session)
    db_session.add(
        Aprovacao(movimentacao_id=mov.id, tipo=TipoAprovacao.GESTOR_ORIGEM, estado=EstadoAprovacao.PENDENTE)
    )
    db_session.commit()

    db_session.add(
        Aprovacao(movimentacao_id=mov.id, tipo=TipoAprovacao.GESTOR_ORIGEM, estado=EstadoAprovacao.PENDENTE)
    )
    with pytest.raises(IntegrityError):
        db_session.commit()
