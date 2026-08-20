"""Orquestrador único (spec.md §7.2, T-50/T-51/T-52) — cobre os cenários
CN-Q08 a CN-Q21 do plan.md/spec.md revisados em 2026-08-18: gate reavaliado
no processamento, prevenção de dupla validação/efetivação, job stale, falha
técnica mantendo `PENDENTE`, e efetivação local dos cinco tipos.
"""

from datetime import datetime, timedelta, timezone

import pytest

from app.models import (
    Aprovacao,
    Colaborador,
    EstadoAprovacao,
    JobValidacao,
    Movimentacao,
    OrigemExecucao,
    StatusJob,
    StatusMovimentacao,
    TipoAprovacao,
    TipoMovimentacao,
    ValidacaoAuditoria,
)
from app.processing import orchestrator
from app.processing.orchestrator import OrchestratorResultado
from app.repositories import job_validacao_repository as job_repo
from app.services.exceptions import MovimentacaoNaoEncontrada
from tests.builders import (
    CargoBuilder,
    CentroCustoBuilder,
    ColaboradorBuilder,
    DepartamentoBuilder,
    EstruturaOrganizacionalBuilder,
    MovimentacaoBuilder,
    criar_aprovacoes_exigidas,
)


def _transferencia_valida(db_session):
    dep_origem = DepartamentoBuilder(gestor_id=ColaboradorBuilder().build(db_session).id).build(db_session)
    dep_destino = DepartamentoBuilder(gestor_id=ColaboradorBuilder().build(db_session).id).build(db_session)
    return MovimentacaoBuilder(
        tipo=TipoMovimentacao.TRANSFERENCIA,
        departamento_origem_id=dep_origem.id,
        departamento_destino_id=dep_destino.id,
    ).build(db_session)


def _apto_com_job(db_session, mov):
    """Simula o que o producer faz: aprovações concluídas, status PENDENTE, job criado."""
    criar_aprovacoes_exigidas(db_session, mov, estado=EstadoAprovacao.APROVADA)
    mov.status = StatusMovimentacao.PENDENTE
    db_session.commit()
    job_repo.criar(db_session, mov.id, datetime(2026, 1, 1))
    db_session.commit()
    return mov


def test_movimentacao_inexistente_levanta_excecao(db_session):
    with pytest.raises(MovimentacaoNaoEncontrada):
        orchestrator.processar(db_session, 999999, OrigemExecucao.MANUAL)


def test_movimentacao_ja_terminal_nao_reprocessa(db_session):
    mov = _transferencia_valida(db_session)
    mov.status = StatusMovimentacao.APROVADA
    db_session.commit()

    saida = orchestrator.processar(db_session, mov.id, OrigemExecucao.MANUAL)

    assert saida.resultado == OrchestratorResultado.JA_TERMINAL


def test_cnq08_aprovacao_reprovada_bloqueia_sem_engine(db_session):
    mov = _transferencia_valida(db_session)
    criar_aprovacoes_exigidas(db_session, mov, estado=EstadoAprovacao.REPROVADA)
    db_session.commit()

    saida = orchestrator.processar(db_session, mov.id, OrigemExecucao.MANUAL)

    assert saida.resultado == OrchestratorResultado.BLOQUEADO_APROVACAO
    assert saida.movimentacao.status == StatusMovimentacao.BLOQUEADA
    assert any(i.codigo == "APROVACAO_REPROVADA" for i in saida.impedimentos)
    assert db_session.query(ValidacaoAuditoria).filter_by(movimentacao_id=mov.id).count() == 0


def test_cnq09_aprovacao_pendente_aguarda_sem_engine(db_session):
    mov = _transferencia_valida(db_session)
    criar_aprovacoes_exigidas(db_session, mov, estado=EstadoAprovacao.PENDENTE)
    db_session.commit()

    saida = orchestrator.processar(db_session, mov.id, OrigemExecucao.MANUAL)

    assert saida.resultado == OrchestratorResultado.BLOQUEADO_APROVACAO
    assert saida.movimentacao.status == StatusMovimentacao.AGUARDANDO_APROVACAO
    assert any(i.codigo == "APROVACAO_PENDENTE" for i in saida.impedimentos)
    assert db_session.query(ValidacaoAuditoria).filter_by(movimentacao_id=mov.id).count() == 0


def test_cnq10_pendente_pronto_processa_via_automatico(db_session):
    mov = _apto_com_job(db_session, _transferencia_valida(db_session))

    saida = orchestrator.processar(db_session, mov.id, OrigemExecucao.AUTOMATICO)

    assert saida.resultado == OrchestratorResultado.EXECUTADO
    assert saida.movimentacao.status == StatusMovimentacao.APROVADA


def test_cnq11_manual_assume_job_e_worker_nao_duplica(db_session):
    mov = _apto_com_job(db_session, _transferencia_valida(db_session))

    manual = orchestrator.processar(db_session, mov.id, OrigemExecucao.MANUAL)
    assert manual.resultado == OrchestratorResultado.EXECUTADO

    automatico = orchestrator.processar(db_session, mov.id, OrigemExecucao.AUTOMATICO)
    assert automatico.resultado == OrchestratorResultado.JA_TERMINAL

    assert db_session.query(ValidacaoAuditoria).filter_by(movimentacao_id=mov.id).count() == 1
    job = job_repo.buscar_por_movimentacao(db_session, mov.id)
    assert job.status == StatusJob.CONCLUIDO


def test_cnq12_job_processando_saudavel_retorna_em_andamento(db_session):
    mov = _apto_com_job(db_session, _transferencia_valida(db_session))
    job = job_repo.buscar_por_movimentacao(db_session, mov.id)
    agora = datetime.now(timezone.utc).replace(tzinfo=None)
    job_repo.tentar_adquirir(db_session, job.id, agora)

    saida = orchestrator.processar(db_session, mov.id, OrigemExecucao.MANUAL)

    assert saida.resultado == OrchestratorResultado.EM_ANDAMENTO
    assert db_session.query(ValidacaoAuditoria).filter_by(movimentacao_id=mov.id).count() == 0


def test_cnq13_aprovacao_volta_a_pendente_antes_do_clique_bloqueia(db_session):
    mov = _apto_com_job(db_session, _transferencia_valida(db_session))
    # simula a corrida: uma aprovação exigida volta para PENDENTE depois que
    # o producer já tinha marcado a movimentação como PENDENTE (negócio).
    linha = db_session.query(Aprovacao).filter_by(movimentacao_id=mov.id).first()
    linha.estado = EstadoAprovacao.PENDENTE
    linha.aprovador_id = None
    db_session.commit()

    saida = orchestrator.processar(db_session, mov.id, OrigemExecucao.MANUAL)

    assert saida.resultado == OrchestratorResultado.BLOQUEADO_APROVACAO
    assert saida.movimentacao.status == StatusMovimentacao.AGUARDANDO_APROVACAO
    assert db_session.query(ValidacaoAuditoria).filter_by(movimentacao_id=mov.id).count() == 0


def test_cnq14_engine_com_inconsistencias_reprova_sem_efetivar(db_session):
    dep_destino = DepartamentoBuilder(ativo=False).build(db_session)
    mov = MovimentacaoBuilder(
        tipo=TipoMovimentacao.TRANSFERENCIA, departamento_destino_id=dep_destino.id
    ).build(db_session)
    mov = _apto_com_job(db_session, mov)
    colaborador_id = mov.colaborador_id
    departamento_original = db_session.get(Colaborador, colaborador_id).departamento_id

    saida = orchestrator.processar(db_session, mov.id, OrigemExecucao.AUTOMATICO)

    assert saida.resultado == OrchestratorResultado.EXECUTADO
    assert saida.movimentacao.status == StatusMovimentacao.REPROVADA
    assert saida.auditoria.total_inconsistencias >= 1
    colaborador = db_session.get(Colaborador, colaborador_id)
    assert colaborador.departamento_id == departamento_original


def test_cnq15_engine_sem_inconsistencias_efetiva_e_aprova(db_session):
    mov = _apto_com_job(db_session, _transferencia_valida(db_session))
    colaborador_id = mov.colaborador_id
    destino_id = mov.departamento_destino_id

    saida = orchestrator.processar(db_session, mov.id, OrigemExecucao.AUTOMATICO)

    assert saida.resultado == OrchestratorResultado.EXECUTADO
    assert saida.movimentacao.status == StatusMovimentacao.APROVADA
    colaborador = db_session.get(Colaborador, colaborador_id)
    assert colaborador.departamento_id == destino_id


def test_cnq16_falha_tecnica_mantem_pendente_e_registra_erro(db_session, monkeypatch):
    mov = _apto_com_job(db_session, _transferencia_valida(db_session))

    def quebrar(session, movimentacao, origem_execucao):
        raise RuntimeError("falha técnica simulada")

    monkeypatch.setattr(orchestrator, "validacao_service", type("M", (), {"validar": staticmethod(quebrar)}))

    saida = orchestrator.processar(db_session, mov.id, OrigemExecucao.AUTOMATICO)

    assert saida.resultado == OrchestratorResultado.ERRO_TECNICO
    assert saida.movimentacao.status == StatusMovimentacao.PENDENTE
    job = job_repo.buscar_por_movimentacao(db_session, mov.id)
    assert job.status == StatusJob.PENDENTE
    assert job.tentativas == 1
    assert db_session.query(ValidacaoAuditoria).filter_by(movimentacao_id=mov.id).count() == 0

    from app.repositories import historico_processamento_repository as historico_repo

    eventos = [e.tipo_evento.value for e in historico_repo.listar_por_movimentacao(db_session, mov.id)]
    assert "ERRO_TECNICO" in eventos
    assert "RETRY_AGENDADO" in eventos


def test_falha_tecnica_apos_limite_de_tentativas_vai_para_erro_terminal(db_session, monkeypatch):
    mov = _apto_com_job(db_session, _transferencia_valida(db_session))
    job = job_repo.buscar_por_movimentacao(db_session, mov.id)
    job.tentativas = orchestrator.LIMITE_TENTATIVAS - 1
    db_session.commit()

    def quebrar(session, movimentacao, origem_execucao):
        raise RuntimeError("falha persistente")

    monkeypatch.setattr(orchestrator, "validacao_service", type("M", (), {"validar": staticmethod(quebrar)}))

    orchestrator.processar(db_session, mov.id, OrigemExecucao.AUTOMATICO)

    job = job_repo.buscar_por_movimentacao(db_session, mov.id)
    assert job.tentativas == orchestrator.LIMITE_TENTATIVAS
    assert job.status == StatusJob.ERRO


def test_cnq17_job_stale_e_recuperado_e_reprocessado(db_session):
    mov = _apto_com_job(db_session, _transferencia_valida(db_session))
    job = job_repo.buscar_por_movimentacao(db_session, mov.id)
    ha_uma_hora = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(hours=1)
    job_repo.tentar_adquirir(db_session, job.id, ha_uma_hora)

    saida = orchestrator.processar(db_session, mov.id, OrigemExecucao.AUTOMATICO)

    assert saida.resultado == OrchestratorResultado.EXECUTADO
    assert saida.movimentacao.status == StatusMovimentacao.APROVADA

    from app.repositories import historico_processamento_repository as historico_repo

    eventos = [e.tipo_evento.value for e in historico_repo.listar_por_movimentacao(db_session, mov.id)]
    assert "JOB_RECUPERADO" in eventos


def test_falha_de_efetivacao_faz_rollback_completo(db_session, monkeypatch):
    mov = _apto_com_job(db_session, _transferencia_valida(db_session))
    colaborador_id = mov.colaborador_id
    departamento_original = db_session.get(Colaborador, colaborador_id).departamento_id

    def quebrar(colaborador, movimentacao):
        raise RuntimeError("falha de efetivação simulada")

    monkeypatch.setattr(orchestrator, "efetivacao_service", type("E", (), {"efetivar": staticmethod(quebrar)}))

    saida = orchestrator.processar(db_session, mov.id, OrigemExecucao.AUTOMATICO)

    assert saida.resultado == OrchestratorResultado.ERRO_TECNICO
    colaborador = db_session.get(Colaborador, colaborador_id)
    assert colaborador.departamento_id == departamento_original
    assert db_session.query(ValidacaoAuditoria).filter_by(movimentacao_id=mov.id).count() == 0
    db_session.refresh(mov)
    assert mov.status == StatusMovimentacao.PENDENTE


def test_ca053_promocao_efetiva_cargo(db_session):
    cargo_baixo = CargoBuilder(nivel=1).build(db_session)
    cargo_alto = CargoBuilder(nivel=2).build(db_session)
    gestor = ColaboradorBuilder().build(db_session)
    colaborador = ColaboradorBuilder(cargo_id=cargo_baixo.id, gestor_id=gestor.id).build(db_session)
    mov = MovimentacaoBuilder(
        tipo=TipoMovimentacao.PROMOCAO,
        colaborador_id=colaborador.id,
        cargo_origem_id=cargo_baixo.id,
        cargo_destino_id=cargo_alto.id,
    ).build(db_session)
    mov = _apto_com_job(db_session, mov)

    saida = orchestrator.processar(db_session, mov.id, OrigemExecucao.AUTOMATICO)

    assert saida.movimentacao.status == StatusMovimentacao.APROVADA
    assert db_session.get(Colaborador, colaborador.id).cargo_id == cargo_alto.id


def test_pro11_efetivacao_atualiza_cargo_e_custo_comprometido_atomicamente(db_session):
    """spec.md §11.1/PRO-11 — cargo e custo_comprometido do CC atual mudam
    juntos, na mesma efetivação."""
    from app.models import CentroCusto

    cc = CentroCustoBuilder(orcamento_mensal=10_000_00, custo_comprometido=2_000_00).build(db_session)
    cargo_baixo = CargoBuilder(
        familia_cargo="OPERACOES", ordem_progressao=1, custo_mensal_referencia=5_000_00
    ).build(db_session)
    cargo_alto = CargoBuilder(
        familia_cargo="OPERACOES", ordem_progressao=2, custo_mensal_referencia=8_000_00
    ).build(db_session)
    gestor = ColaboradorBuilder().build(db_session)
    colaborador = ColaboradorBuilder(
        cargo_id=cargo_baixo.id, gestor_id=gestor.id, centro_custo_id=cc.id
    ).build(db_session)
    mov = MovimentacaoBuilder(
        tipo=TipoMovimentacao.PROMOCAO,
        colaborador_id=colaborador.id,
        cargo_origem_id=cargo_baixo.id,
        cargo_destino_id=cargo_alto.id,
        centro_custo_origem_id=cc.id,
    ).build(db_session)
    mov = _apto_com_job(db_session, mov)

    saida = orchestrator.processar(db_session, mov.id, OrigemExecucao.AUTOMATICO)

    assert saida.movimentacao.status == StatusMovimentacao.APROVADA
    assert db_session.get(Colaborador, colaborador.id).cargo_id == cargo_alto.id
    # delta = 8_000_00 - 5_000_00 = 3_000_00; 2_000_00 + 3_000_00 = 5_000_00
    assert db_session.get(CentroCusto, cc.id).custo_comprometido == 5_000_00


def test_pro09_saldo_insuficiente_reprova_promocao_via_orquestrador(db_session):
    from app.models import CentroCusto

    cc = CentroCustoBuilder(orcamento_mensal=1_000_00, custo_comprometido=900_00).build(db_session)
    cargo_baixo = CargoBuilder(
        familia_cargo="OPERACOES", ordem_progressao=1, custo_mensal_referencia=1_000_00
    ).build(db_session)
    cargo_alto = CargoBuilder(
        familia_cargo="OPERACOES", ordem_progressao=2, custo_mensal_referencia=2_000_00
    ).build(db_session)
    gestor = ColaboradorBuilder().build(db_session)
    colaborador = ColaboradorBuilder(
        cargo_id=cargo_baixo.id, gestor_id=gestor.id, centro_custo_id=cc.id
    ).build(db_session)
    mov = MovimentacaoBuilder(
        tipo=TipoMovimentacao.PROMOCAO,
        colaborador_id=colaborador.id,
        cargo_origem_id=cargo_baixo.id,
        cargo_destino_id=cargo_alto.id,
        centro_custo_origem_id=cc.id,
    ).build(db_session)
    mov = _apto_com_job(db_session, mov)

    saida = orchestrator.processar(db_session, mov.id, OrigemExecucao.AUTOMATICO)

    assert saida.movimentacao.status == StatusMovimentacao.REPROVADA
    assert db_session.get(Colaborador, colaborador.id).cargo_id == cargo_baixo.id
    assert db_session.get(CentroCusto, cc.id).custo_comprometido == 900_00


def test_ca053_troca_gestor_efetiva_gestor(db_session):
    gestor_atual = ColaboradorBuilder().build(db_session)
    cargo_gestor = CargoBuilder(permite_gestao=True).build(db_session)
    novo_gestor = ColaboradorBuilder(cargo_id=cargo_gestor.id).build(db_session)
    colaborador = ColaboradorBuilder(gestor_id=gestor_atual.id).build(db_session)
    mov = MovimentacaoBuilder(
        tipo=TipoMovimentacao.TROCA_GESTOR,
        colaborador_id=colaborador.id,
        gestor_origem_id=gestor_atual.id,
        gestor_destino_id=novo_gestor.id,
    ).build(db_session)
    mov = _apto_com_job(db_session, mov)

    saida = orchestrator.processar(db_session, mov.id, OrigemExecucao.AUTOMATICO)

    assert saida.movimentacao.status == StatusMovimentacao.APROVADA
    assert db_session.get(Colaborador, colaborador.id).gestor_id == novo_gestor.id


def test_ca053_centro_custo_efetiva_centro_custo(db_session):
    responsavel = ColaboradorBuilder().build(db_session)
    cc_destino = CentroCustoBuilder(responsavel_id=responsavel.id).build(db_session)
    mov = MovimentacaoBuilder(
        tipo=TipoMovimentacao.MUDANCA_CENTRO_CUSTO, centro_custo_destino_id=cc_destino.id
    ).build(db_session)
    mov = _apto_com_job(db_session, mov)

    saida = orchestrator.processar(db_session, mov.id, OrigemExecucao.AUTOMATICO)

    assert saida.movimentacao.status == StatusMovimentacao.APROVADA
    assert db_session.get(Colaborador, mov.colaborador_id).centro_custo_id == cc_destino.id


def test_ca053_alteracao_estrutura_efetiva_estrutura(db_session):
    gestor = ColaboradorBuilder().build(db_session)
    colaborador = ColaboradorBuilder(gestor_id=gestor.id).build(db_session)
    mov = MovimentacaoBuilder(tipo=TipoMovimentacao.ALTERACAO_ESTRUTURA, colaborador_id=colaborador.id).build(
        db_session
    )
    mov = _apto_com_job(db_session, mov)
    destino_id = mov.estrutura_destino_id

    saida = orchestrator.processar(db_session, mov.id, OrigemExecucao.AUTOMATICO)

    assert saida.movimentacao.status == StatusMovimentacao.APROVADA
    assert db_session.get(Colaborador, colaborador.id).estrutura_id == destino_id


def test_cnq20_aprovacao_extra_nao_exigida_reprovada_nao_bloqueia(db_session):
    mov = _transferencia_valida(db_session)
    criar_aprovacoes_exigidas(db_session, mov, estado=EstadoAprovacao.APROVADA)
    aprovador = ColaboradorBuilder().build(db_session)
    db_session.add(
        Aprovacao(
            movimentacao_id=mov.id,
            tipo=TipoAprovacao.GERENCIA,
            estado=EstadoAprovacao.REPROVADA,
            aprovador_id=aprovador.id,
        )
    )
    db_session.commit()

    saida = orchestrator.processar(db_session, mov.id, OrigemExecucao.MANUAL)

    assert saida.resultado == OrchestratorResultado.EXECUTADO
    assert saida.movimentacao.status == StatusMovimentacao.APROVADA
