from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import Session

from app.api.schemas.auth import LoginRequest, LoginResponse, UsuarioResponse
from app.database import get_db
from app.models import Usuario
from app.security import permissions
from app.security.dependencies import get_current_user, ip_cliente
from app.services import auth_service

router = APIRouter(prefix="/auth", tags=["auth"])


def _usuario_response(usuario: Usuario) -> UsuarioResponse:
    return UsuarioResponse(
        id=usuario.id,
        username=usuario.username,
        perfil=usuario.perfil.value,
        scopes=permissions.scopes_do_perfil(usuario.perfil.value),
    )


@router.post("/login", response_model=LoginResponse)
def login(
    payload: LoginRequest,
    response: Response,
    ip: str = Depends(ip_cliente),
    db: Session = Depends(get_db),
) -> LoginResponse:
    response.headers["Cache-Control"] = "no-store"
    agora = datetime.now(timezone.utc).replace(tzinfo=None)
    token, expires_in, usuario = auth_service.login(db, payload.username, payload.password, ip, agora)
    return LoginResponse(access_token=token, expires_in=expires_in, usuario=_usuario_response(usuario))


@router.get("/me", response_model=UsuarioResponse)
def me(response: Response, usuario: Usuario = Depends(get_current_user)) -> UsuarioResponse:
    response.headers["Cache-Control"] = "no-store"
    return _usuario_response(usuario)
