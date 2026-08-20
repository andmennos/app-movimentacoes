"""Lockout de força bruta por IP — spec.md §12.3/RC-25, persistido no SQLite
(sobrevive a reinício, diferente do rate limiter geral em memória)."""

from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.models import SecurityLockout


def _buscar(session: Session, ip: str) -> SecurityLockout | None:
    consulta = select(SecurityLockout).where(SecurityLockout.ip == ip)
    return session.scalars(consulta).one_or_none()


def segundos_bloqueado_restantes(session: Session, ip: str, agora: datetime) -> int | None:
    """`None` se o IP não está bloqueado agora; caso contrário, segundos
    restantes (mínimo 1) para uso em `Retry-After`."""
    lockout = _buscar(session, ip)
    if lockout is None or lockout.blocked_until is None:
        return None
    if lockout.blocked_until <= agora:
        return None
    return max(1, int((lockout.blocked_until - agora).total_seconds()))


def registrar_falha(session: Session, ip: str, agora: datetime) -> SecurityLockout:
    lockout = _buscar(session, ip)
    janela = timedelta(seconds=settings.login_failure_window_seconds)

    if lockout is None:
        lockout = SecurityLockout(ip=ip, failed_attempts=0, window_started_at=None, blocked_until=None, updated_at=agora)
        session.add(lockout)

    janela_expirada = lockout.window_started_at is None or (agora - lockout.window_started_at) > janela
    if janela_expirada:
        lockout.window_started_at = agora
        lockout.failed_attempts = 1
    else:
        lockout.failed_attempts += 1

    if lockout.failed_attempts >= settings.login_max_failures:
        lockout.blocked_until = agora + timedelta(seconds=settings.login_block_seconds)

    lockout.updated_at = agora
    session.flush()
    return lockout


def limpar_falhas(session: Session, ip: str, agora: datetime) -> None:
    """Sucesso de login limpa o contador aplicável (spec §12.3)."""
    lockout = _buscar(session, ip)
    if lockout is None:
        return
    lockout.failed_attempts = 0
    lockout.window_started_at = None
    lockout.blocked_until = None
    lockout.updated_at = agora
    session.flush()


def resetar_todos(session: Session) -> int:
    """`python -m app.security.reset_lockouts` — só altera esta tabela."""
    total = session.query(SecurityLockout).delete()
    session.commit()
    return total
