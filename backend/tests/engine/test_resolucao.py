from app.validation.engine import resolver_resultado
from app.validation.types import EstadoAprovacao, ResultadoValidacao, TipoAprovacao
from tests.validation.factories import aprovacao_ref


def test_ca029_sem_defeitos_e_todas_aprovadas_retorna_aprovada():
    aprovacoes = [aprovacao_ref(TipoAprovacao.GESTOR_ORIGEM), aprovacao_ref(TipoAprovacao.GESTOR_DESTINO)]
    assert resolver_resultado([], aprovacoes) == ResultadoValidacao.APROVADA


def test_ca030_sem_defeitos_com_pendente_retorna_aguardando():
    aprovacoes = [
        aprovacao_ref(TipoAprovacao.GESTOR_ORIGEM),
        aprovacao_ref(TipoAprovacao.GESTOR_DESTINO, estado=EstadoAprovacao.PENDENTE, aprovador_id=None),
    ]
    assert resolver_resultado([], aprovacoes) == ResultadoValidacao.AGUARDANDO_APROVACAO


def test_ca031_aprovacao_reprovada_retorna_reprovada():
    aprovacoes = [
        aprovacao_ref(TipoAprovacao.GESTOR_ORIGEM, estado=EstadoAprovacao.REPROVADA),
        aprovacao_ref(TipoAprovacao.GESTOR_DESTINO),
    ]
    assert resolver_resultado([], aprovacoes) == ResultadoValidacao.REPROVADA


def test_inconsistencia_de_regra_sempre_reprova_independente_de_aprovacoes():
    from app.validation.types import Inconsistencia

    aprovacoes = [aprovacao_ref(TipoAprovacao.GESTOR_ORIGEM), aprovacao_ref(TipoAprovacao.GESTOR_DESTINO)]
    inconsistencias = [Inconsistencia("T05", "Departamento de origem e destino são iguais")]
    assert resolver_resultado(inconsistencias, aprovacoes) == ResultadoValidacao.REPROVADA


def test_precedencia_reprovada_sobre_pendente():
    aprovacoes = [
        aprovacao_ref(TipoAprovacao.GESTOR_ORIGEM, estado=EstadoAprovacao.REPROVADA),
        aprovacao_ref(TipoAprovacao.GESTOR_DESTINO, estado=EstadoAprovacao.PENDENTE, aprovador_id=None),
    ]
    assert resolver_resultado([], aprovacoes) == ResultadoValidacao.REPROVADA
