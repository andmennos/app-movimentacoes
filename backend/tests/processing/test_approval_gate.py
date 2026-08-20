from app.processing.approval_gate import GateResultado, avaliar, calcular_impedimentos
from app.validation.types import EstadoAprovacao, TipoAprovacao
from tests.validation.factories import aprovacao_ref, contexto_transferencia


def test_todas_aprovadas_resulta_apto():
    ctx = contexto_transferencia()
    assert avaliar(ctx) == GateResultado.APTO
    assert calcular_impedimentos(ctx) == []


def test_uma_pendente_resulta_aguardando_aprovacao():
    ctx = contexto_transferencia(
        aprovacoes=[
            aprovacao_ref(TipoAprovacao.GESTOR_ORIGEM),
            aprovacao_ref(TipoAprovacao.GESTOR_DESTINO, estado=EstadoAprovacao.PENDENTE, aprovador_id=None),
            aprovacao_ref(TipoAprovacao.RH),
        ]
    )
    assert avaliar(ctx) == GateResultado.AGUARDANDO_APROVACAO
    impedimentos = calcular_impedimentos(ctx)
    assert len(impedimentos) == 1
    assert impedimentos[0].codigo == "APROVACAO_PENDENTE"
    assert "GESTOR_DESTINO" in impedimentos[0].mensagem


def test_linha_ausente_e_tratada_como_pendente():
    ctx = contexto_transferencia(aprovacoes=[aprovacao_ref(TipoAprovacao.GESTOR_ORIGEM)])
    assert avaliar(ctx) == GateResultado.AGUARDANDO_APROVACAO


def test_uma_reprovada_resulta_bloqueada():
    ctx = contexto_transferencia(
        aprovacoes=[
            aprovacao_ref(
                TipoAprovacao.GESTOR_ORIGEM,
                estado=EstadoAprovacao.REPROVADA,
                aprovador_nome="Felipe Almeida",
            ),
            aprovacao_ref(TipoAprovacao.GESTOR_DESTINO),
            aprovacao_ref(TipoAprovacao.RH),
        ]
    )
    assert avaliar(ctx) == GateResultado.BLOQUEADA
    impedimentos = calcular_impedimentos(ctx)
    assert len(impedimentos) == 1
    assert impedimentos[0].codigo == "APROVACAO_REPROVADA"
    assert impedimentos[0].mensagem == "Aprovação GESTOR_ORIGEM reprovada por Felipe Almeida."


def test_reprovada_tem_precedencia_sobre_pendente():
    ctx = contexto_transferencia(
        aprovacoes=[
            aprovacao_ref(TipoAprovacao.GESTOR_ORIGEM, estado=EstadoAprovacao.REPROVADA),
            aprovacao_ref(TipoAprovacao.GESTOR_DESTINO, estado=EstadoAprovacao.PENDENTE, aprovador_id=None),
        ]
    )
    assert avaliar(ctx) == GateResultado.BLOQUEADA


def test_aprovacao_extra_nao_exigida_nao_interfere():
    """CN-Q20: uma aprovação de um tipo que este tipo de movimentação não
    exige (ex.: GERENCIA numa TRANSFERENCIA) nunca altera o resultado do
    gate, mesmo reprovada."""
    ctx = contexto_transferencia(
        aprovacoes=[
            aprovacao_ref(TipoAprovacao.GESTOR_ORIGEM),
            aprovacao_ref(TipoAprovacao.GESTOR_DESTINO),
            aprovacao_ref(TipoAprovacao.RH),
            aprovacao_ref(TipoAprovacao.GERENCIA, estado=EstadoAprovacao.REPROVADA),
        ]
    )
    assert avaliar(ctx) == GateResultado.APTO
    assert calcular_impedimentos(ctx) == []


def test_t85_reprovada_com_etapa_posterior_pendente_nunca_alcancada_nao_e_impedimento():
    """spec.md RC-47/T-85 — bug real reproduzido no E2E: uma reprovação em
    etapa intermediária (ex.: DIRETORIA) deixa etapas de ordem posterior
    (ex.: GESTOR_RH_ADICIONAL) permanentemente `PENDENTE` no banco — elas
    nunca foram e nunca serão decididas, porque a ordem sequencial bloqueia
    decisão fora de sequência. `calcular_impedimentos` não pode reportá-las
    como "aguardando aprovação": a única causa real do bloqueio é a
    reprovação."""
    ctx = contexto_transferencia(
        aprovacoes=[
            aprovacao_ref(TipoAprovacao.GESTOR_ORIGEM, estado=EstadoAprovacao.REPROVADA, aprovador_nome="Diretor X"),
            aprovacao_ref(TipoAprovacao.GESTOR_DESTINO, estado=EstadoAprovacao.PENDENTE, aprovador_id=None),
            aprovacao_ref(TipoAprovacao.RH, estado=EstadoAprovacao.PENDENTE, aprovador_id=None),
        ]
    )
    assert avaliar(ctx) == GateResultado.BLOQUEADA
    impedimentos = calcular_impedimentos(ctx)
    assert len(impedimentos) == 1
    assert impedimentos[0].codigo == "APROVACAO_REPROVADA"
    assert impedimentos[0].mensagem == "Aprovação GESTOR_ORIGEM reprovada por Diretor X."
    assert not any(i.codigo == "APROVACAO_PENDENTE" for i in impedimentos)


def test_aprovada_sem_integridade_ainda_assim_e_apta_no_gate():
    """A integridade do aprovador (responsável esperado, ativo) não é mais
    checada pelo gate — só o estado. Fica a cargo da engine (T06/P04-06/etc.)
    quando a movimentação chega lá."""
    ctx = contexto_transferencia(
        responsaveis_derivados={"GESTOR_ORIGEM": None, "GESTOR_DESTINO": None}
    )
    assert avaliar(ctx) == GateResultado.APTO
