"""Orquestrador único de processamento — spec.md §7.2 (revisão 2026-08-18,
T-50). Único ponto que finaliza `Movimentacao`, `JobValidacao`, auditoria,
efetivação e eventos finais (INV-08). O Worker e `POST /validar` chamam
exatamente esta função — nenhum dos dois decide status de negócio por conta
própria (INV-09), e nenhuma das 34 regras é reimplementada em nenhum dos dois
caminhos.
"""

from __future__ import annotations

import enum
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.config import settings
from app.models import (
    JobValidacao,
    Movimentacao,
    OrigemEvento,
    OrigemExecucao,
    ResultadoValidacao,
    StatusJob,
    StatusMovimentacao,
    TipoEventoProcessamento,
    ValidacaoAuditoria,
)
from app.processing.approval_gate import GateResultado, Impedimento, avaliar, calcular_impedimentos
from app.repositories import historico_processamento_repository as historico_repo
from app.repositories import job_validacao_repository as job_repo
from app.repositories import movimentacao_repository
from app.services import efetivacao_service, validacao_service
from app.services.exceptions import MovimentacaoNaoEncontrada
from app.services.movimentacao_service import montar_contexto

logger = logging.getLogger("app.processing.orchestrator")

LIMITE_TENTATIVAS = 3
"""Após esgotar as tentativas, o job fica `ERRO` (terminal) em vez de voltar
para `PENDENTE` — spec.md §7.4/plan.md §12. Política simples do MVP, sem
backoff — mesmo valor usado tanto para falha em execução quanto para
recuperação de job stale."""

ESTADOS_TERMINAIS = (
    StatusMovimentacao.APROVADA,
    StatusMovimentacao.REPROVADA,
    StatusMovimentacao.BLOQUEADA,
)


class OrchestratorResultado(str, enum.Enum):
    EXECUTADO = "EXECUTADO"
    """A engine rodou (aprovada ou reprovada), com ou sem efetivação."""
    BLOQUEADO_APROVACAO = "BLOQUEADO_APROVACAO"
    """Gate reavaliado no instante do processamento não está apto
    (BLOQUEADA ou AGUARDANDO_APROVACAO) — a engine não rodou."""
    JA_TERMINAL = "JA_TERMINAL"
    EM_ANDAMENTO = "EM_ANDAMENTO"
    """Job `PROCESSANDO` saudável, adquirido por outra origem."""
    ERRO_TECNICO = "ERRO_TECNICO"


@dataclass
class ProcessamentoSaida:
    resultado: OrchestratorResultado
    movimentacao: Movimentacao | None = None
    auditoria: ValidacaoAuditoria | None = None
    impedimentos: list[Impedimento] = field(default_factory=list)


def _agora() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _origem_evento(origem_execucao: OrigemExecucao) -> OrigemEvento:
    return OrigemEvento.AUTOMATICO if origem_execucao == OrigemExecucao.AUTOMATICO else OrigemEvento.MANUAL


def processar(session: Session, movimentacao_id: int, origem_execucao: OrigemExecucao) -> ProcessamentoSaida:
    """Interface conceitual de plan.md §10. Passos: carregar → rejeitar
    terminal → reavaliar gate → (bloqueado: atualizar status e sair) →
    assegurar/adquirir job → executar engine → concluir (auditoria +
    efetivação + status + job + eventos, em um único commit por resultado)."""
    agora = _agora()
    origem_evento = _origem_evento(origem_execucao)

    movimentacao = movimentacao_repository.carregar_para_validacao(session, movimentacao_id)
    if movimentacao is None:
        raise MovimentacaoNaoEncontrada(movimentacao_id)

    if movimentacao.status in ESTADOS_TERMINAIS:
        if origem_execucao == OrigemExecucao.MANUAL:
            historico_repo.registrar(
                session,
                movimentacao.id,
                TipoEventoProcessamento.VALIDACAO_MANUAL_NAO_PERMITIDA,
                OrigemEvento.MANUAL,
                "Solicitação já concluída — nada a processar.",
                agora,
            )
            session.commit()
        return ProcessamentoSaida(OrchestratorResultado.JA_TERMINAL, movimentacao=movimentacao)

    if origem_execucao == OrigemExecucao.MANUAL:
        historico_repo.registrar(
            session,
            movimentacao.id,
            TipoEventoProcessamento.VALIDACAO_MANUAL_SOLICITADA,
            OrigemEvento.MANUAL,
            "Validação manual solicitada.",
            agora,
        )

    # RF-10/RF-16: reavalia o gate antes de qualquer execução, mesmo que a
    # tela ou o job já apontem PENDENTE — protege contra corrida (CN-Q13).
    ctx = montar_contexto(session, movimentacao)
    gate = avaliar(ctx)

    if gate != GateResultado.APTO:
        return _bloquear_por_aprovacao(session, movimentacao, ctx, gate, origem_execucao, agora)

    if movimentacao.status != StatusMovimentacao.PENDENTE:
        movimentacao.status = StatusMovimentacao.PENDENTE

    job = job_repo.obter_ou_criar(session, movimentacao.id, agora)
    if job.status == StatusJob.ERRO:
        job_repo.reabrir(session, job)
    session.commit()

    if job.status == StatusJob.PROCESSANDO:
        limite = agora - timedelta(seconds=settings.job_stale_after_seconds)
        if job.iniciado_em is not None and job.iniciado_em < limite:
            _recuperar_job_stale(session, job, agora)
        else:
            return ProcessamentoSaida(OrchestratorResultado.EM_ANDAMENTO, movimentacao=movimentacao)

    if job.status == StatusJob.CONCLUIDO:
        # Já processado por outra origem entre a checagem de estado terminal
        # (acima) e este ponto — nada a fazer.
        return ProcessamentoSaida(OrchestratorResultado.JA_TERMINAL, movimentacao=movimentacao)

    adquiriu = job_repo.tentar_adquirir(session, job.id, agora)
    if not adquiriu:
        return ProcessamentoSaida(OrchestratorResultado.EM_ANDAMENTO, movimentacao=movimentacao)

    historico_repo.registrar(
        session,
        movimentacao.id,
        TipoEventoProcessamento.PROCESSAMENTO_INICIADO,
        origem_evento,
        "Processamento de validação iniciado.",
        agora,
    )
    session.commit()

    return _executar_e_concluir(session, movimentacao.id, job.id, origem_execucao)


def _bloquear_por_aprovacao(session, movimentacao, ctx, gate, origem_execucao, agora) -> ProcessamentoSaida:
    impedimentos = calcular_impedimentos(ctx)
    movimentacao.status = (
        StatusMovimentacao.BLOQUEADA if gate == GateResultado.BLOQUEADA else StatusMovimentacao.AGUARDANDO_APROVACAO
    )

    # Um job PENDENTE órfão (criado num ciclo anterior em que o gate ainda
    # estava apto) não deve ficar preso indefinidamente na fila — encerra o
    # ciclo; se a movimentação voltar a ficar apta, o producer/orquestrador
    # reabre o mesmo job (unique por movimentação).
    job_existente = job_repo.buscar_por_movimentacao(session, movimentacao.id)
    if job_existente is not None and job_existente.status == StatusJob.PENDENTE:
        job_repo.marcar_concluido(session, job_existente, agora)

    if origem_execucao == OrigemExecucao.MANUAL:
        motivo = "; ".join(i.mensagem for i in impedimentos) or "Aprovação exigida ainda não concluída."
        historico_repo.registrar(
            session,
            movimentacao.id,
            TipoEventoProcessamento.VALIDACAO_MANUAL_NAO_PERMITIDA,
            OrigemEvento.MANUAL,
            f"Validação manual não permitida: {motivo}",
            agora,
        )

    session.commit()
    return ProcessamentoSaida(
        OrchestratorResultado.BLOQUEADO_APROVACAO, movimentacao=movimentacao, impedimentos=impedimentos
    )


def _executar_e_concluir(session: Session, movimentacao_id: int, job_id: int, origem_execucao: OrigemExecucao) -> ProcessamentoSaida:
    agora = _agora()
    origem_evento = _origem_evento(origem_execucao)
    movimentacao = session.get(Movimentacao, movimentacao_id)
    job = session.get(JobValidacao, job_id)

    try:
        auditoria = validacao_service.validar(session, movimentacao, origem_execucao)

        if auditoria.resultado == ResultadoValidacao.REPROVADA:
            movimentacao.status = StatusMovimentacao.REPROVADA
            job_repo.marcar_concluido(session, job, agora)
            historico_repo.registrar(
                session,
                movimentacao.id,
                TipoEventoProcessamento.VALIDACAO_REPROVADA,
                origem_evento,
                f"Validação reprovada com {auditoria.total_inconsistencias} inconsistência(s).",
                agora,
            )
        else:
            efetivacao_service.efetivar(movimentacao.colaborador, movimentacao)
            movimentacao.status = StatusMovimentacao.APROVADA
            job_repo.marcar_concluido(session, job, agora)
            historico_repo.registrar(
                session,
                movimentacao.id,
                TipoEventoProcessamento.MOVIMENTACAO_EFETIVADA,
                origem_evento,
                "Movimentação efetivada no cadastro do colaborador.",
                agora,
            )

        session.commit()
        session.refresh(movimentacao)
        return ProcessamentoSaida(OrchestratorResultado.EXECUTADO, movimentacao=movimentacao, auditoria=auditoria)

    except Exception as exc:  # noqa: BLE001 — falha técnica genuína, não de negócio (INV-04/RF-13)
        session.rollback()
        return _tratar_falha_tecnica(session, job_id, movimentacao_id, exc, origem_execucao)


def _tratar_falha_tecnica(session: Session, job_id: int, movimentacao_id: int, exc: Exception, origem_execucao: OrigemExecucao) -> ProcessamentoSaida:
    agora = _agora()
    job = session.get(JobValidacao, job_id)
    mensagem = f"{type(exc).__name__}: {exc}"[:500]
    logger.error(
        "processamento_falhou job_id=%s movimentacao_id=%s tentativas=%s erro=%s",
        job_id,
        movimentacao_id,
        job.tentativas,
        mensagem,
    )

    if job.tentativas >= LIMITE_TENTATIVAS:
        job_repo.marcar_erro_terminal(session, job, mensagem, agora)
        evento_mensagem = "Falha técnica — limite de tentativas esgotado."
    else:
        job_repo.marcar_para_nova_tentativa(session, job, mensagem)
        evento_mensagem = "Falha técnica — nova tentativa agendada."

    movimentacao = session.get(Movimentacao, movimentacao_id)
    # RC-19/INV-13: falha técnica não muda negócio para REPROVADA/BLOQUEADA;
    # as aprovações continuam válidas, então a movimentação permanece PENDENTE.
    movimentacao.status = StatusMovimentacao.PENDENTE

    historico_repo.registrar(
        session,
        movimentacao_id,
        TipoEventoProcessamento.ERRO_TECNICO,
        _origem_evento(origem_execucao),
        evento_mensagem,
        agora,
        detalhe_sanitizado=mensagem,
    )
    if job.status == StatusJob.PENDENTE:
        historico_repo.registrar(
            session,
            movimentacao_id,
            TipoEventoProcessamento.RETRY_AGENDADO,
            OrigemEvento.SISTEMA,
            "Nova tentativa de processamento agendada.",
            agora,
        )

    session.commit()
    return ProcessamentoSaida(OrchestratorResultado.ERRO_TECNICO, movimentacao=movimentacao)


def _recuperar_job_stale(session: Session, job: JobValidacao, agora: datetime) -> None:
    novo_status = job_repo.marcar_recuperado(session, job, agora, LIMITE_TENTATIVAS)
    historico_repo.registrar(
        session,
        job.movimentacao_id,
        TipoEventoProcessamento.JOB_RECUPERADO,
        OrigemEvento.SISTEMA,
        f"Job travado em processamento recuperado — novo estado {novo_status.value}.",
        agora,
    )
    session.commit()


def recuperar_jobs_stale(session: Session) -> int:
    """T-52 — chamada no startup do Worker e antes de cada ciclo de polling
    (spec §7.4). Retorna quantos jobs foram recuperados."""
    limite = _agora() - timedelta(seconds=settings.job_stale_after_seconds)
    stale = job_repo.buscar_processando_stale(session, limite)
    for job in stale:
        _recuperar_job_stale(session, job, _agora())
    return len(stale)
