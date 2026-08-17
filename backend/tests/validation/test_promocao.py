from app.validation.engine import executar
from app.validation.promocao import (
    p01_cargo_destino_existe,
    p02_cargo_destino_ativo,
    p03_nivel_superior,
    p04_aprovacao_gestor,
    p05_aprovacao_rh,
    p06_aprovacao_superior,
)
from app.validation.types import AprovacaoAdicional, EstadoAprovacao, TipoAprovacao
from tests.validation.factories import aprovacao_ref, cargo_ref, contexto_promocao


def test_p01_dispara_quando_cargo_destino_ausente():
    ctx = contexto_promocao(cargo_destino=None)
    assert [i.codigo for i in p01_cargo_destino_existe(ctx)] == ["P01"]


def test_p01_suprime_quando_cargo_destino_presente():
    assert p01_cargo_destino_existe(contexto_promocao()) == []


def test_p02_dispara_quando_cargo_destino_inativo():
    ctx = contexto_promocao(cargo_destino=cargo_ref(nivel=2, ativo=False))
    assert [i.codigo for i in p02_cargo_destino_ativo(ctx)] == ["P02"]


def test_p02_suprime_quando_cargo_destino_ativo():
    assert p02_cargo_destino_ativo(contexto_promocao()) == []


def test_p02_precondicao_nao_avalia_sem_cargo_destino():
    ctx = contexto_promocao(cargo_destino=None)
    assert p02_cargo_destino_ativo(ctx) == []


def test_p03_dispara_quando_nivel_nao_superior():
    cargo_atual = cargo_ref(nivel=3)
    ctx = contexto_promocao(cargo_atual=cargo_atual, cargo_destino=cargo_ref(nivel=3))
    assert [i.codigo for i in p03_nivel_superior(ctx)] == ["P03"]


def test_p03_dispara_quando_nivel_inferior():
    cargo_atual = cargo_ref(nivel=3)
    ctx = contexto_promocao(cargo_atual=cargo_atual, cargo_destino=cargo_ref(nivel=1))
    assert [i.codigo for i in p03_nivel_superior(ctx)] == ["P03"]


def test_p03_suprime_quando_nivel_superior():
    assert p03_nivel_superior(contexto_promocao(cargo_atual=cargo_ref(nivel=1), cargo_destino=cargo_ref(nivel=2))) == []


def test_p03_precondicao_nao_avalia_sem_cargo_atual_conhecido():
    ctx = contexto_promocao(cargo_atual=None)
    assert p03_nivel_superior(ctx) == []


def test_p04_dispara_quando_aprovacao_gestor_ausente():
    ctx = contexto_promocao(aprovacoes=[aprovacao_ref(TipoAprovacao.RH)])
    assert [i.codigo for i in p04_aprovacao_gestor(ctx)] == ["P04"]


def test_p04_suprime_quando_aprovacao_gestor_integra():
    assert p04_aprovacao_gestor(contexto_promocao()) == []


def test_p05_dispara_quando_aprovacao_rh_ausente():
    ctx = contexto_promocao(aprovacoes=[aprovacao_ref(TipoAprovacao.GESTOR_ORIGEM)])
    assert [i.codigo for i in p05_aprovacao_rh(ctx)] == ["P05"]


def test_p05_suprime_quando_aprovacao_rh_integra():
    assert p05_aprovacao_rh(contexto_promocao()) == []


def test_p06_dispara_quando_diretoria_exigida_e_ausente():
    cargo_destino = cargo_ref(nivel=5, aprovacao_adicional=AprovacaoAdicional.DIRETORIA)
    ctx = contexto_promocao(
        cargo_destino=cargo_destino,
        aprovacoes=[aprovacao_ref(TipoAprovacao.GESTOR_ORIGEM), aprovacao_ref(TipoAprovacao.RH)],
    )
    assert [i.codigo for i in p06_aprovacao_superior(ctx)] == ["P06"]


def test_p06_suprime_quando_nao_aplicavel():
    ctx = contexto_promocao(cargo_destino=cargo_ref(nivel=2, aprovacao_adicional=None))
    assert p06_aprovacao_superior(ctx) == []


def test_p06_suprime_quando_diretoria_exigida_e_integra():
    cargo_destino = cargo_ref(nivel=5, aprovacao_adicional=AprovacaoAdicional.DIRETORIA)
    ctx = contexto_promocao(cargo_destino=cargo_destino)
    assert p06_aprovacao_superior(ctx) == []


def test_ca032_linha_ausente_reprova_sob_codigo_da_regra():
    ctx = contexto_promocao(aprovacoes=[aprovacao_ref(TipoAprovacao.GESTOR_ORIGEM)])
    codigos = [i.codigo for i in executar(ctx)]
    assert "P05" in codigos


def test_ca033_aprovador_inativo_produz_inconsistencia_de_integridade():
    ctx = contexto_promocao(
        aprovacoes=[
            aprovacao_ref(TipoAprovacao.GESTOR_ORIGEM),
            aprovacao_ref(TipoAprovacao.RH, estado=EstadoAprovacao.APROVADA, aprovador_ativo=False),
        ]
    )
    codigos = [i.codigo for i in executar(ctx)]
    assert "P05" in codigos


def test_cnm02_multiplas_inconsistencias_promocao():
    cargo_destino = cargo_ref(nivel=1, ativo=False)  # mesmo nível do atual (nivel=1) + inativo
    ctx = contexto_promocao(
        cargo_atual=cargo_ref(nivel=1),
        cargo_destino=cargo_destino,
        aprovacoes=[aprovacao_ref(TipoAprovacao.GESTOR_ORIGEM)],  # RH ausente
    )
    codigos = [i.codigo for i in executar(ctx)]
    assert "P02" in codigos
    assert "P03" in codigos
    assert "P05" in codigos
