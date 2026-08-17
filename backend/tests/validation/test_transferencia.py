from app.validation.engine import executar
from app.validation.transferencia import (
    t01_departamento_origem_existe,
    t02_departamento_origem_ativo,
    t03_departamento_destino_existe,
    t04_departamento_destino_ativo,
    t05_origem_diferente_destino,
    t06_aprovacoes_integras,
)
from app.validation.types import EstadoAprovacao, TipoAprovacao
from tests.validation.factories import (
    aprovacao_ref,
    contexto_transferencia,
    departamento_ref,
)


def test_t01_dispara_quando_origem_ausente():
    ctx = contexto_transferencia(departamento_origem=None)
    assert [i.codigo for i in t01_departamento_origem_existe(ctx)] == ["T01"]


def test_t01_suprime_quando_origem_presente():
    assert t01_departamento_origem_existe(contexto_transferencia()) == []


def test_t02_dispara_quando_origem_inativa():
    ctx = contexto_transferencia(departamento_origem=departamento_ref(ativo=False))
    assert [i.codigo for i in t02_departamento_origem_ativo(ctx)] == ["T02"]


def test_t02_suprime_quando_origem_ativa():
    assert t02_departamento_origem_ativo(contexto_transferencia()) == []


def test_t02_precondicao_nao_avalia_sem_origem():
    ctx = contexto_transferencia(departamento_origem=None)
    assert t02_departamento_origem_ativo(ctx) == []


def test_t03_dispara_quando_destino_ausente():
    ctx = contexto_transferencia(departamento_destino=None)
    assert [i.codigo for i in t03_departamento_destino_existe(ctx)] == ["T03"]


def test_t03_suprime_quando_destino_presente():
    assert t03_departamento_destino_existe(contexto_transferencia()) == []


def test_t04_dispara_quando_destino_inativo():
    ctx = contexto_transferencia(departamento_destino=departamento_ref(ativo=False))
    assert [i.codigo for i in t04_departamento_destino_ativo(ctx)] == ["T04"]


def test_t04_suprime_quando_destino_ativo():
    assert t04_departamento_destino_ativo(contexto_transferencia()) == []


def test_t05_dispara_quando_origem_igual_destino():
    dep = departamento_ref()
    ctx = contexto_transferencia(departamento_origem=dep, departamento_destino=dep)
    assert [i.codigo for i in t05_origem_diferente_destino(ctx)] == ["T05"]


def test_t05_suprime_quando_origem_diferente_destino():
    assert t05_origem_diferente_destino(contexto_transferencia()) == []


def test_t06_dispara_quando_aprovacao_ausente():
    ctx = contexto_transferencia(aprovacoes=[aprovacao_ref(TipoAprovacao.GESTOR_ORIGEM)])
    codigos = [i.codigo for i in t06_aprovacoes_integras(ctx)]
    assert codigos == ["T06"]


def test_t06_dispara_para_cada_linha_nao_integra():
    ctx = contexto_transferencia(
        aprovacoes=[
            aprovacao_ref(TipoAprovacao.GESTOR_ORIGEM, estado=EstadoAprovacao.APROVADA, aprovador_id=None),
            aprovacao_ref(TipoAprovacao.GESTOR_DESTINO, estado=EstadoAprovacao.APROVADA, aprovador_id=None),
        ]
    )
    codigos = [i.codigo for i in t06_aprovacoes_integras(ctx)]
    assert codigos == ["T06", "T06"]


def test_t06_suprime_quando_aprovacoes_integras():
    assert t06_aprovacoes_integras(contexto_transferencia()) == []


def test_ca010_destino_inexistente_emite_apenas_t03():
    ctx = contexto_transferencia(departamento_destino=None)
    codigos = [i.codigo for i in executar(ctx)]
    assert "T03" in codigos
    assert "T04" not in codigos
    assert "T05" not in codigos


def test_multiplas_inconsistencias_simultaneas_no_tipo():
    ctx = contexto_transferencia(
        departamento_destino=departamento_ref(ativo=False),
        aprovacoes=[aprovacao_ref(TipoAprovacao.GESTOR_ORIGEM)],
    )
    codigos = [i.codigo for i in executar(ctx)]
    assert "T04" in codigos
    assert "T06" in codigos
