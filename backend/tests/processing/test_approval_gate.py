from app.processing.approval_gate import GateResultado, avaliar
from app.validation.types import EstadoAprovacao, TipoAprovacao
from tests.validation.factories import aprovacao_ref, colaborador_ref, contexto_transferencia


def test_todas_aprovadas_resulta_apta():
    ctx = contexto_transferencia()
    assert avaliar(ctx) == GateResultado.APTA


def test_uma_pendente_resulta_pendente():
    ctx = contexto_transferencia(
        aprovacoes=[
            aprovacao_ref(TipoAprovacao.GESTOR_ORIGEM),
            aprovacao_ref(TipoAprovacao.GESTOR_DESTINO, estado=EstadoAprovacao.PENDENTE, aprovador_id=None),
        ]
    )
    assert avaliar(ctx) == GateResultado.PENDENTE


def test_uma_reprovada_resulta_reprovada():
    ctx = contexto_transferencia(
        aprovacoes=[
            aprovacao_ref(TipoAprovacao.GESTOR_ORIGEM, estado=EstadoAprovacao.REPROVADA),
            aprovacao_ref(TipoAprovacao.GESTOR_DESTINO),
        ]
    )
    assert avaliar(ctx) == GateResultado.REPROVADA


def test_reprovada_tem_precedencia_sobre_pendente():
    ctx = contexto_transferencia(
        aprovacoes=[
            aprovacao_ref(TipoAprovacao.GESTOR_ORIGEM, estado=EstadoAprovacao.REPROVADA),
            aprovacao_ref(TipoAprovacao.GESTOR_DESTINO, estado=EstadoAprovacao.PENDENTE, aprovador_id=None),
        ]
    )
    assert avaliar(ctx) == GateResultado.REPROVADA


def test_linha_exigida_ausente_resulta_anomalo():
    ctx = contexto_transferencia(aprovacoes=[aprovacao_ref(TipoAprovacao.GESTOR_ORIGEM)])
    assert avaliar(ctx) == GateResultado.ANOMALO


def test_aprovada_sem_integridade_resulta_anomalo():
    ctx = contexto_transferencia(
        responsaveis_derivados={"GESTOR_ORIGEM": None, "GESTOR_DESTINO": colaborador_ref()}
    )
    assert avaliar(ctx) == GateResultado.ANOMALO


def test_anomalo_nao_e_mascarado_como_reprovada():
    # ausência de linha não deve nunca virar REPROVADA por conta própria do gate
    ctx = contexto_transferencia(aprovacoes=[])
    assert avaliar(ctx) == GateResultado.ANOMALO
