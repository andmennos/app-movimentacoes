"""Dependências FastAPI de autenticação/autorização — plan.md §6.4.

`get_current_user` decodifica o Bearer, confirma assinatura/expiração e que
o usuário ainda existe e está ativo no banco (spec §12.2). `require_scope`
aplica a autorização funcional (RBAC) — a autorização de objeto (BOLA) é
responsabilidade de `security/object_scope.py` (T-59), reaplicada dentro de
cada rota sobre o objeto concreto.
"""

from __future__ import annotations

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Usuario
from app.repositories import usuario_repository
from app.security.jwt import TokenInvalido, decode_and_validate_token
from app.services.exceptions import AcessoNegado, TokenInvalidoOuExpirado

_bearer_scheme = HTTPBearer(auto_error=False)


def get_current_user(
    credenciais: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
    db: Session = Depends(get_db),
) -> Usuario:
    if credenciais is None:
        raise TokenInvalidoOuExpirado()

    try:
        claims = decode_and_validate_token(credenciais.credentials)
    except TokenInvalido as exc:
        raise TokenInvalidoOuExpirado() from exc

    try:
        usuario_id = int(claims["sub"])
    except (KeyError, ValueError, TypeError) as exc:
        raise TokenInvalidoOuExpirado() from exc

    usuario = usuario_repository.buscar_por_id(db, usuario_id)
    if usuario is None or not usuario.ativo:
        raise TokenInvalidoOuExpirado()

    return usuario


def require_scope(scope: str):
    def _checar(usuario: Usuario = Depends(get_current_user)) -> Usuario:
        from app.security.permissions import scopes_do_perfil

        if scope not in scopes_do_perfil(usuario.perfil.value):
            raise AcessoNegado(f"Perfil {usuario.perfil.value} não possui o escopo {scope}.")
        return usuario

    return _checar


def ip_cliente(request: Request) -> str:
    """spec.md §12.4 — não confia em `X-Forwarded-For` no modo local; usa o
    IP efetivo da conexão. Em produção, a origem confiável viria do proxy."""
    return request.client.host if request.client else "desconhecido"
