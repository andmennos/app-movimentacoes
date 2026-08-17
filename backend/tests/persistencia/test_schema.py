from sqlalchemy import inspect

ENTIDADES_ESPERADAS = {
    "colaborador",
    "cargo",
    "departamento",
    "centro_custo",
    "estrutura_organizacional",
    "movimentacao",
    "aprovacao",
    "validacao_auditoria",
    "inconsistencia_auditoria",
}


def test_schema_cria_as_9_entidades(engine):
    inspector = inspect(engine)
    tabelas = set(inspector.get_table_names())
    assert ENTIDADES_ESPERADAS <= tabelas
    assert len(ENTIDADES_ESPERADAS) == 9


def test_cargo_tem_campos_de_promocao(engine):
    inspector = inspect(engine)
    colunas = {c["name"] for c in inspector.get_columns("cargo")}
    assert {"nivel", "permite_gestao", "aprovacao_adicional"} <= colunas


def test_estrutura_tem_estrutura_pai_id(engine):
    inspector = inspect(engine)
    colunas = {c["name"] for c in inspector.get_columns("estrutura_organizacional")}
    assert "estrutura_pai_id" in colunas


def test_movimentacao_tem_10_fks_de_tipo(engine):
    inspector = inspect(engine)
    colunas = {c["name"] for c in inspector.get_columns("movimentacao")}
    campos_por_tipo = {
        "departamento_origem_id",
        "departamento_destino_id",
        "cargo_origem_id",
        "cargo_destino_id",
        "gestor_origem_id",
        "gestor_destino_id",
        "centro_custo_origem_id",
        "centro_custo_destino_id",
        "estrutura_origem_id",
        "estrutura_destino_id",
    }
    assert campos_por_tipo <= colunas
    assert len(campos_por_tipo) == 10
