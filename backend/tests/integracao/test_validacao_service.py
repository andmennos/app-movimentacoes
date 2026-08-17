import pytest

from app.models import ResultadoValidacao, StatusMovimentacao, TipoMovimentacao
from app.repositories import auditoria_repository
from app.services import validacao_service
from tests.builders import ColaboradorBuilder, DepartamentoBuilder, MovimentacaoBuilder, criar_aprovacoes_exigidas


def _transferencia_valida(db_session) -> MovimentacaoBuilder:
    dep_origem = DepartamentoBuilder(gestor_id=ColaboradorBuilder().build(db_session).id).build(db_session)
    dep_destino = DepartamentoBuilder(gestor_id=ColaboradorBuilder().build(db_session).id).build(db_session)
    return MovimentacaoBuilder(
        tipo=TipoMovimentacao.TRANSFERENCIA,
        departamento_origem_id=dep_origem.id,
        departamento_destino_id=dep_destino.id,
    ).build(db_session)


def test_validar_movimentacao_valida_resulta_aprovada(db_session):
    mov = _transferencia_valida(db_session)
    criar_aprovacoes_exigidas(db_session, mov)
    db_session.commit()

    atualizada, auditoria = validacao_service.validar(db_session, mov.id)

    assert atualizada.status == StatusMovimentacao.APROVADA
    assert atualizada.resultado_ultima_validacao == ResultadoValidacao.APROVADA
    assert auditoria.resultado == ResultadoValidacao.APROVADA
    assert auditoria.total_inconsistencias == 0


def test_validar_movimentacao_com_defeito_resulta_reprovada(db_session):
    dep = DepartamentoBuilder(ativo=False).build(db_session)
    mov = MovimentacaoBuilder(
        tipo=TipoMovimentacao.TRANSFERENCIA, departamento_destino_id=dep.id
    ).build(db_session)
    criar_aprovacoes_exigidas(db_session, mov)
    db_session.commit()

    atualizada, auditoria = validacao_service.validar(db_session, mov.id)

    assert atualizada.status == StatusMovimentacao.REPROVADA
    assert auditoria.resultado == ResultadoValidacao.REPROVADA
    assert auditoria.total_inconsistencias >= 1


def test_validar_movimentacao_aguardando_aprovacao(db_session):
    from app.models import EstadoAprovacao

    mov = _transferencia_valida(db_session)
    criar_aprovacoes_exigidas(db_session, mov, estado=EstadoAprovacao.PENDENTE)
    db_session.commit()

    atualizada, auditoria = validacao_service.validar(db_session, mov.id)

    assert atualizada.status == StatusMovimentacao.PENDENTE
    assert auditoria.resultado == ResultadoValidacao.AGUARDANDO_APROVACAO


def test_validar_movimentacao_inexistente_levanta_excecao_dedicada(db_session):
    with pytest.raises(validacao_service.MovimentacaoNaoEncontrada):
        validacao_service.validar(db_session, 999999)


def test_ca012_cada_post_validar_cria_exatamente_um_registro(db_session):
    mov = MovimentacaoBuilder(tipo=TipoMovimentacao.TRANSFERENCIA).build(db_session)
    criar_aprovacoes_exigidas(db_session, mov)
    db_session.commit()

    validacao_service.validar(db_session, mov.id)

    from app.models import ValidacaoAuditoria

    total = db_session.query(ValidacaoAuditoria).filter_by(movimentacao_id=mov.id).count()
    assert total == 1


def test_ca013_revalidar_cria_novo_registro_sem_alterar_anteriores(db_session):
    mov = MovimentacaoBuilder(tipo=TipoMovimentacao.TRANSFERENCIA).build(db_session)
    criar_aprovacoes_exigidas(db_session, mov)
    db_session.commit()

    _, primeira = validacao_service.validar(db_session, mov.id)
    primeira_id = primeira.id
    _, segunda = validacao_service.validar(db_session, mov.id)

    assert segunda.id != primeira_id
    ainda_la = auditoria_repository.buscar_ultima(db_session, mov.id)
    assert ainda_la.id == segunda.id

    from app.models import ValidacaoAuditoria

    total = db_session.query(ValidacaoAuditoria).filter_by(movimentacao_id=mov.id).count()
    assert total == 2


def test_ca024_excecao_nao_tratada_produz_500_sem_alterar_movimentacao(db_session, monkeypatch):
    mov = MovimentacaoBuilder(tipo=TipoMovimentacao.TRANSFERENCIA).build(db_session)
    criar_aprovacoes_exigidas(db_session, mov)
    db_session.commit()
    status_original = mov.status
    resultado_original = mov.resultado_ultima_validacao

    def quebrar(ctx):
        raise RuntimeError("falha inesperada simulada")

    monkeypatch.setattr(validacao_service, "executar", quebrar)

    with pytest.raises(RuntimeError):
        validacao_service.validar(db_session, mov.id)

    db_session.rollback()
    from app.models import Movimentacao, ValidacaoAuditoria

    recarregada = db_session.get(Movimentacao, mov.id)
    assert recarregada.status == status_original
    assert recarregada.resultado_ultima_validacao == resultado_original
    assert db_session.query(ValidacaoAuditoria).filter_by(movimentacao_id=mov.id).count() == 0
