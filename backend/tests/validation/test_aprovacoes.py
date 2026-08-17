from app.validation.aprovacoes import aprovacao_adicional_promocao, integra, tipos_exigidos
from app.validation.types import AprovacaoAdicional, EstadoAprovacao, TipoAprovacao, TipoMovimentacao
from tests.validation.factories import (
    aprovacao_ref,
    cargo_ref,
    colaborador_ref,
    contexto_centro_custo,
    contexto_promocao,
    contexto_transferencia,
)


def test_tipos_exigidos_por_tipo_conforme_spec_5_2():
    assert set(tipos_exigidos(contexto_transferencia())) == {
        TipoAprovacao.GESTOR_ORIGEM,
        TipoAprovacao.GESTOR_DESTINO,
    }
    assert set(tipos_exigidos(contexto_centro_custo())) == {TipoAprovacao.GESTOR_DESTINO}


def test_promocao_sem_aprovacao_adicional_quando_cargo_nao_exige():
    ctx = contexto_promocao(cargo_destino=cargo_ref(nivel=2, aprovacao_adicional=None))
    assert aprovacao_adicional_promocao(ctx) is None
    assert TipoAprovacao.GERENCIA not in tipos_exigidos(ctx)
    assert TipoAprovacao.DIRETORIA not in tipos_exigidos(ctx)


def test_promocao_com_aprovacao_adicional_gerencia():
    ctx = contexto_promocao(cargo_destino=cargo_ref(nivel=5, aprovacao_adicional=AprovacaoAdicional.GERENCIA))
    assert aprovacao_adicional_promocao(ctx) == TipoAprovacao.GERENCIA
    assert TipoAprovacao.GERENCIA in tipos_exigidos(ctx)


def test_promocao_com_aprovacao_adicional_diretoria_cn_n09():
    ctx = contexto_promocao(cargo_destino=cargo_ref(nivel=6, aprovacao_adicional=AprovacaoAdicional.DIRETORIA))
    assert aprovacao_adicional_promocao(ctx) == TipoAprovacao.DIRETORIA
    assert TipoAprovacao.DIRETORIA in tipos_exigidos(ctx)


def test_integridade_condicao_1_linha_ausente():
    ctx = contexto_transferencia(aprovacoes=[])
    assert integra(ctx, TipoAprovacao.GESTOR_ORIGEM) is False


def test_integridade_condicao_2_aprovador_ausente_em_linha_decidida():
    ctx = contexto_transferencia(
        aprovacoes=[
            aprovacao_ref(TipoAprovacao.GESTOR_ORIGEM, estado=EstadoAprovacao.APROVADA, aprovador_id=None),
            aprovacao_ref(TipoAprovacao.GESTOR_DESTINO),
        ]
    )
    assert integra(ctx, TipoAprovacao.GESTOR_ORIGEM) is False


def test_integridade_condicao_2_aprovador_inativo_em_linha_decidida_ca033():
    ctx = contexto_transferencia(
        aprovacoes=[
            aprovacao_ref(TipoAprovacao.GESTOR_ORIGEM, estado=EstadoAprovacao.APROVADA, aprovador_ativo=False),
            aprovacao_ref(TipoAprovacao.GESTOR_DESTINO),
        ]
    )
    assert integra(ctx, TipoAprovacao.GESTOR_ORIGEM) is False


def test_integridade_condicao_2_nao_se_aplica_a_linha_pendente():
    ctx = contexto_transferencia(
        aprovacoes=[
            aprovacao_ref(TipoAprovacao.GESTOR_ORIGEM, estado=EstadoAprovacao.PENDENTE, aprovador_id=None),
            aprovacao_ref(TipoAprovacao.GESTOR_DESTINO),
        ]
    )
    assert integra(ctx, TipoAprovacao.GESTOR_ORIGEM) is True


def test_integridade_condicao_3_responsavel_esperado_ausente():
    ctx = contexto_transferencia(responsaveis_derivados={"GESTOR_ORIGEM": None, "GESTOR_DESTINO": colaborador_ref()})
    assert integra(ctx, TipoAprovacao.GESTOR_ORIGEM) is False


def test_integridade_condicao_3_responsavel_esperado_inativo():
    ctx = contexto_transferencia(
        responsaveis_derivados={
            "GESTOR_ORIGEM": colaborador_ref(ativo=False),
            "GESTOR_DESTINO": colaborador_ref(),
        }
    )
    assert integra(ctx, TipoAprovacao.GESTOR_ORIGEM) is False


def test_integridade_condicao_3_nao_se_aplica_a_rh():
    ctx = contexto_promocao(responsaveis_derivados={})
    assert integra(ctx, TipoAprovacao.RH) is True


def test_integra_quando_tudo_certo():
    assert integra(contexto_transferencia(), TipoAprovacao.GESTOR_ORIGEM) is True
    assert integra(contexto_transferencia(), TipoAprovacao.GESTOR_DESTINO) is True
