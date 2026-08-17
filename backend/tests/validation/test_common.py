from app.validation.common import g01_colaborador_existe, g02_colaborador_ativo, g03_tipo_valido, g04_sem_conflito
from app.validation.types import MovimentacaoRef, TipoMovimentacao
from tests.validation.factories import colaborador_ref, contexto_transferencia, novo_id


def test_g01_dispara_quando_colaborador_ausente():
    ctx = contexto_transferencia(colaborador=None)
    assert [i.codigo for i in g01_colaborador_existe(ctx)] == ["G01"]


def test_g01_suprime_quando_colaborador_presente():
    ctx = contexto_transferencia()
    assert g01_colaborador_existe(ctx) == []


def test_g02_dispara_quando_colaborador_inativo():
    ctx = contexto_transferencia(colaborador=colaborador_ref(ativo=False))
    assert [i.codigo for i in g02_colaborador_ativo(ctx)] == ["G02"]


def test_g02_suprime_quando_colaborador_ativo():
    ctx = contexto_transferencia()
    assert g02_colaborador_ativo(ctx) == []


def test_g02_precondicao_g01_nao_avalia_sem_colaborador():
    ctx = contexto_transferencia(colaborador=None)
    assert g02_colaborador_ativo(ctx) == []


def test_g03_dispara_quando_tipo_fora_do_enum():
    ctx = contexto_transferencia()
    ctx.movimentacao = MovimentacaoRef(id=novo_id(), tipo="LIXO", colaborador_id=ctx.colaborador.id)
    assert [i.codigo for i in g03_tipo_valido(ctx)] == ["G03"]


def test_g03_suprime_para_tipo_valido():
    ctx = contexto_transferencia()
    assert g03_tipo_valido(ctx) == []


def test_g04_dispara_quando_ha_conflito():
    ctx = contexto_transferencia(conflito_mesmo_tipo_em_aberto=True)
    assert [i.codigo for i in g04_sem_conflito(ctx)] == ["G04"]


def test_g04_suprime_sem_conflito():
    ctx = contexto_transferencia(conflito_mesmo_tipo_em_aberto=False)
    assert g04_sem_conflito(ctx) == []


def test_g04_precondicao_g01_nao_avalia_sem_colaborador():
    ctx = contexto_transferencia(colaborador=None, conflito_mesmo_tipo_em_aberto=True)
    assert g04_sem_conflito(ctx) == []


def test_tipo_invalido_ainda_assim_executa_regras_gerais_no_engine():
    from app.validation.engine import executar

    ctx = contexto_transferencia()
    ctx.movimentacao = MovimentacaoRef(id=novo_id(), tipo="LIXO", colaborador_id=ctx.colaborador.id)

    codigos = [i.codigo for i in executar(ctx)]

    assert "G03" in codigos
