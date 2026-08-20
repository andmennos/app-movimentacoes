from pydantic import ConfigDict, Field

from app.api.schemas.base import CamelModel


class LoginRequest(CamelModel):
    model_config = ConfigDict(extra="forbid")

    username: str = Field(min_length=1, max_length=100)
    password: str = Field(min_length=1, max_length=200)


class UsuarioResponse(CamelModel):
    id: int
    username: str
    perfil: str
    scopes: list[str]
    """spec.md RC-39/T-77 — scopes efetivos do perfil, devolvidos pelo
    backend (`security/permissions.py::scopes_do_perfil`, fonte única). O
    Angular não mantém `SCOPES_POR_PERFIL` próprio; usa exatamente esta
    lista para decidir navegação (`scopeGuard`), nunca para autorizar de
    verdade — o backend sempre reautoriza cada rota (RC-16)."""


class LoginResponse(CamelModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    usuario: UsuarioResponse
