"""JWT Bearer — spec.md §2.2/§12.2/plan.md §6.3. Claims mínimas: `sub`
(usuario_id), `perfil`, `scopes`, `exp`. Nunca inclui senha/hash."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import jwt

from app.config import settings
from app.security.permissions import scopes_do_perfil


class TokenInvalido(Exception):
    pass


def create_access_token(usuario_id: int, perfil: str) -> tuple[str, int]:
    agora = datetime.now(timezone.utc)
    expira_em = agora + timedelta(minutes=settings.jwt_expire_minutes)
    claims = {
        "sub": str(usuario_id),
        "perfil": perfil,
        "scopes": scopes_do_perfil(perfil),
        "iat": int(agora.timestamp()),
        "exp": int(expira_em.timestamp()),
    }
    token = jwt.encode(claims, settings.jwt_secret, algorithm=settings.jwt_algorithm)
    return token, settings.jwt_expire_minutes * 60


def decode_and_validate_token(token: str) -> dict:
    try:
        return jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    except jwt.PyJWTError as exc:
        raise TokenInvalido(str(exc)) from exc
