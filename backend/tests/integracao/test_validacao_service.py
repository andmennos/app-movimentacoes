"""`services/validacao_service.py` — executa a engine sobre uma movimentação
já carregada e grava a auditoria (spec.md §7.5). Não decide status de negócio
nem toca na fila/histórico — isso é do orquestrador (`test_orchestrator.py`).
"""

from app.models import OrigemExecucao, ResultadoValidacao, TipoMovimentacao, ValidacaoAuditoria
from app.repositories import auditoria_repository, movimentacao_repository
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


def test_validar_movimentacao_valida_resulta_aprovada_na_auditoria(db_session):
    mov = _transferencia_valida(db_session)
    criar_aprovacoes_exigidas(db_session, mov)
    db_session.commit()
    carregada = movimentacao_repository.carregar_para_validacao(db_session, mov.id)

    auditoria = validacao_service.validar(db_session, carregada, OrigemExecucao.AUTOMATICO)

    assert auditoria.resultado == ResultadoValidacao.APROVADA
    assert auditoria.total_inconsistencias == 0
    assert auditoria.origem_execucao == OrigemExecucao.AUTOMATICO
    assert carregada.resultado_ultima_validacao == ResultadoValidacao.APROVADA


def test_validar_movimentacao_com_defeito_resulta_reprovada_na_auditoria(db_session):
    dep = DepartamentoBuilder(ativo=False).build(db_session)
    mov = MovimentacaoBuilder(
        tipo=TipoMovimentacao.TRANSFERENCIA, departamento_destino_id=dep.id
    ).build(db_session)
    criar_aprovacoes_exigidas(db_session, mov)
    db_session.commit()
    carregada = movimentacao_repository.carregar_para_validacao(db_session, mov.id)

    auditoria = validacao_service.validar(db_session, carregada, OrigemExecucao.AUTOMATICO)

    assert auditoria.resultado == ResultadoValidacao.REPROVADA
    assert auditoria.total_inconsistencias >= 1


def test_cada_chamada_cria_exatamente_um_registro_de_auditoria(db_session):
    mov = MovimentacaoBuilder(tipo=TipoMovimentacao.TRANSFERENCIA).build(db_session)
    criar_aprovacoes_exigidas(db_session, mov)
    db_session.commit()
    carregada = movimentacao_repository.carregar_para_validacao(db_session, mov.id)

    validacao_service.validar(db_session, carregada, OrigemExecucao.AUTOMATICO)
    db_session.commit()

    total = db_session.query(ValidacaoAuditoria).filter_by(movimentacao_id=mov.id).count()
    assert total == 1


def test_revalidar_cria_novo_registro_sem_alterar_anteriores(db_session):
    mov = MovimentacaoBuilder(tipo=TipoMovimentacao.TRANSFERENCIA).build(db_session)
    criar_aprovacoes_exigidas(db_session, mov)
    db_session.commit()
    carregada = movimentacao_repository.carregar_para_validacao(db_session, mov.id)

    primeira = validacao_service.validar(db_session, carregada, OrigemExecucao.AUTOMATICO)
    db_session.commit()
    primeira_id = primeira.id
    segunda = validacao_service.validar(db_session, carregada, OrigemExecucao.MANUAL)
    db_session.commit()

    assert segunda.id != primeira_id
    ainda_la = auditoria_repository.buscar_ultima(db_session, mov.id)
    assert ainda_la.id == segunda.id
