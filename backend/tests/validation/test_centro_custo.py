from app.validation.centro_custo import (
    cc01_centro_custo_origem_existe,
    cc02_centro_custo_origem_ativo,
    cc03_centro_custo_destino_existe,
    cc04_centro_custo_destino_ativo,
    cc05_origem_diferente_destino,
    cc06_aprovacao_responsavel,
)
from app.validation.engine import executar
from app.validation.types import TipoAprovacao
from tests.validation.factories import aprovacao_ref, centro_custo_ref, contexto_centro_custo


def test_cc01_dispara_quando_origem_ausente():
    ctx = contexto_centro_custo(centro_custo_origem=None)
    assert [i.codigo for i in cc01_centro_custo_origem_existe(ctx)] == ["CC01"]


def test_cc01_suprime_quando_presente():
    assert cc01_centro_custo_origem_existe(contexto_centro_custo()) == []


def test_cc02_dispara_quando_origem_inativa():
    ctx = contexto_centro_custo(centro_custo_origem=centro_custo_ref(ativo=False))
    assert [i.codigo for i in cc02_centro_custo_origem_ativo(ctx)] == ["CC02"]


def test_cc02_suprime_quando_ativa():
    assert cc02_centro_custo_origem_ativo(contexto_centro_custo()) == []


def test_cc02_precondicao_nao_avalia_sem_origem():
    ctx = contexto_centro_custo(centro_custo_origem=None)
    assert cc02_centro_custo_origem_ativo(ctx) == []


def test_cc03_dispara_quando_destino_ausente():
    ctx = contexto_centro_custo(centro_custo_destino=None)
    assert [i.codigo for i in cc03_centro_custo_destino_existe(ctx)] == ["CC03"]


def test_cc03_suprime_quando_presente():
    assert cc03_centro_custo_destino_existe(contexto_centro_custo()) == []


def test_cc04_dispara_quando_destino_inativo_cn_n14():
    ctx = contexto_centro_custo(centro_custo_destino=centro_custo_ref(ativo=False))
    assert [i.codigo for i in cc04_centro_custo_destino_ativo(ctx)] == ["CC04"]


def test_cc04_suprime_quando_ativo():
    assert cc04_centro_custo_destino_ativo(contexto_centro_custo()) == []


def test_cc05_dispara_quando_origem_igual_destino_cn_n15():
    cc = centro_custo_ref()
    ctx = contexto_centro_custo(centro_custo_origem=cc, centro_custo_destino=cc)
    assert [i.codigo for i in cc05_origem_diferente_destino(ctx)] == ["CC05"]


def test_cc05_suprime_quando_diferentes():
    assert cc05_origem_diferente_destino(contexto_centro_custo()) == []


def test_cc06_dispara_quando_aprovacao_ausente():
    ctx = contexto_centro_custo(aprovacoes=[])
    assert [i.codigo for i in cc06_aprovacao_responsavel(ctx)] == ["CC06"]


def test_cc06_suprime_quando_integra():
    assert cc06_aprovacao_responsavel(contexto_centro_custo()) == []


def test_multiplas_inconsistencias_centro_custo():
    ctx = contexto_centro_custo(centro_custo_destino=centro_custo_ref(ativo=False), aprovacoes=[])
    codigos = [i.codigo for i in executar(ctx)]
    assert "CC04" in codigos
    assert "CC06" in codigos
