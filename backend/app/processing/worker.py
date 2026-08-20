"""Worker Python — consumer local da fila `JobValidacao` (spec.md §7.2/§7.4).

Processo independente, executável via `python -m app.processing.worker`.
Delega todo o processamento ao orquestrador único (`processing/orchestrator`)
— o mesmo usado por `POST /validar` (INV-09) — e nunca decide status de
negócio nem reimplementa nenhuma das 34 regras (INV-11). Único consumer no
MVP: sem locking distribuído ou coordenação multi-worker.
"""

from __future__ import annotations

import logging
import time

from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models import OrigemExecucao
from app.processing import orchestrator
from app.repositories import job_validacao_repository as job_repo

logger = logging.getLogger("app.processing.worker")

INTERVALO_POLLING_SEGUNDOS = 2


def processar_um_job(session: Session) -> bool:
    """Recupera jobs `PROCESSANDO` travados (stale) e, em seguida, consome o
    job `PENDENTE` mais antigo, se houver, delegando ao orquestrador.

    Retorna `True` se encontrou e processou um job (sucesso, reprovação ou
    falha técnica), `False` se a fila estava vazia.
    """
    orchestrator.recuperar_jobs_stale(session)

    job = job_repo.buscar_pendente_mais_antigo(session)
    if job is None:
        return False

    resultado = orchestrator.processar(session, job.movimentacao_id, OrigemExecucao.AUTOMATICO)
    logger.info(
        "job_validacao_processado job_id=%s movimentacao_id=%s resultado=%s",
        job.id,
        job.movimentacao_id,
        resultado.resultado.value,
    )
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

    session_recuperacao = SessionLocal()
    try:
        recuperados = orchestrator.recuperar_jobs_stale(session_recuperacao)
        if recuperados:
            logger.info("jobs_recuperados_no_startup total=%s", recuperados)
    finally:
        session_recuperacao.close()

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
