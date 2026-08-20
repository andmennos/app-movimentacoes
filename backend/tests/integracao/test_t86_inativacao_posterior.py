"""T-86/RC-50 — esta revisão não altera o comportamento de catálogos
ativos/inativos: uma referência ativa na criação da solicitação e inativada
depois do processamento continua sendo detectada pelas regras já existentes
(T02/T04), sem nova regra nem relaxamento."""

from datetime import datetime

from app.models import EstadoAprovacao, OrigemExecucao, ResultadoValidacao, StatusMovimentacao, TipoMovimentacao
from app.processing import orchestrator
from app.repositories import job_validacao_repository as job_repo
from tests.builders import ColaboradorBuilder, DepartamentoBuilder, MovimentacaoBuilder, criar_aprovacoes_exigidas


def test_e2e11_departamento_destino_ativo_na_criacao_e_inativado_depois_e_detectado_no_processamento(db_session):
    dep_origem = DepartamentoBuilder(gestor_id=ColaboradorBuilder().build(db_session).id).build(db_session)
    dep_destino = DepartamentoBuilder(ativo=True).build(db_session)
    mov = MovimentacaoBuilder(
        tipo=TipoMovimentacao.TRANSFERENCIA,
        departamento_origem_id=dep_origem.id,
        departamento_destino_id=dep_destino.id,
    ).build(db_session)
    criar_aprovacoes_exigidas(db_session, mov, estado=EstadoAprovacao.APROVADA)
    mov.status = StatusMovimentacao.PENDENTE
    db_session.commit()
    job_repo.criar(db_session, mov.id, datetime(2026, 1, 1))
    db_session.commit()

    # a referência estava ativa quando a solicitação foi criada — só se
    # torna inativa depois, imediatamente antes do processamento.
    dep_destino.ativo = False
    db_session.commit()

    saida = orchestrator.processar(db_session, mov.id, OrigemExecucao.AUTOMATICO)

    assert saida.auditoria is not None
    assert saida.auditoria.resultado == ResultadoValidacao.REPROVADA
    codigos = {i.codigo_regra for i in saida.auditoria.inconsistencias}
    assert "T04" in codigos
    assert saida.movimentacao.status == StatusMovimentacao.REPROVADA
