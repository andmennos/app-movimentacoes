"""Worker Python — consumer local da fila `JobValidacao` (spec.md §6, §7.5).

Processo independente, executável via `python -m app.processing.worker`.
Reutiliza exatamente o `ValidacaoService` usado por `POST /validar` — nenhuma
das 34 regras é reimplementada aqui (INV-11). Único consumer no MVP: sem
locking distribuído ou coordenação multi-worker (plan.md §7.5).
"""

from __future__ import annotations

import logging
import time
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models import JobValidacao
from app.repositories import job_validacao_repository as job_repo
from app.services import validacao_service

logger = logging.getLogger("app.processing.worker")

LIMITE_TENTATIVAS = 3
"""Após esgotar as tentativas, o job fica `ERRO` (terminal) em vez de voltar
para `PENDENTE` — spec.md §7.5. Política simples do MVP, sem backoff."""

INTERVALO_POLLING_SEGUNDOS = 2


def _agora() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def processar_um_job(session: Session) -> bool:
    """Consome o job pendente mais antigo, se houver.

    Sucesso → job `CONCLUIDO`, `ValidacaoService` já gravou auditoria e
    atualizou a movimentação na mesma transação síncrona de `POST /validar`.

    Falha técnica → nenhuma escrita de negócio permanece (o `ValidacaoService`
    não commita antes de propagar a exceção — INV-04); o job registra a
    tentativa e o erro técnico, sem dado sensível, e volta para `PENDENTE`
    (nova tentativa) ou vai para `ERRO` (tentativas esgotadas).

    Retorna `True` se encontrou e processou um job (sucesso ou falha), `False`
    se a fila estava vazia.
    """
    job = job_repo.buscar_pendente_mais_antigo(session)
    if job is None:
        return False

    job_id = job.id
    movimentacao_id = job.movimentacao_id
    job_repo.marcar_processando(session, job, _agora())

    try:
        validacao_service.validar(session, movimentacao_id)
    except Exception as exc:  # noqa: BLE001 — falha técnica genuína, não de negócio (INV-04)
        session.rollback()
        job = session.get(JobValidacao, job_id)
        mensagem = f"{type(exc).__name__}: {exc}"[:500]
        logger.error(
            "job_validacao_falhou job_id=%s movimentacao_id=%s tentativas=%s erro=%s",
            job_id,
            movimentacao_id,
            job.tentativas,
            mensagem,
        )
        if job.tentativas >= LIMITE_TENTATIVAS:
            job_repo.marcar_erro_terminal(session, job, mensagem, _agora())
        else:
            job_repo.marcar_para_nova_tentativa(session, job, mensagem)
    else:
        job = session.get(JobValidacao, job_id)
        job_repo.marcar_concluido(session, job, _agora())
        logger.info("job_validacao_concluido job_id=%s movimentacao_id=%s", job_id, movimentacao_id)

    return True


def drenar_fila(session: Session) -> int:
    """Processa todos os jobs pendentes disponíveis agora, um de cada vez,
    até a fila esvaziar. Usado pelo seed (demonstração determinística) e por
    testes — evita depender do intervalo de polling do processo contínuo."""
    total = 0
    while processar_um_job(session):
        total += 1
    return total


def main() -> None:  # pragma: no cover — laço de processo real, exercitado manualmente
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    logger.info("worker_iniciado intervalo_polling_s=%s", INTERVALO_POLLING_SEGUNDOS)
    try:
        while True:
            session = SessionLocal()
            try:
                processou = processar_um_job(session)
            finally:
                session.close()
            if not processou:
                time.sleep(INTERVALO_POLLING_SEGUNDOS)
    except KeyboardInterrupt:
        logger.info("worker_finalizado_por_usuario")


if __name__ == "__main__":
    main()
