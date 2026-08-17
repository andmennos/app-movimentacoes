from sqlalchemy import inspect


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
