"""Mapa único de perfil → scopes — spec.md §2.3/RC-07..RC-12/plan.md §7.1.

Fonte única: nenhuma rota ou serviço mantém uma segunda cópia deste mapa.
Estático em código (não precisa de cache de rede/banco — plan.md §7.1).

`movimentacoes:validate` (fallback manual de `POST /validar`) é concedido a
todo perfil autenticado que também tem alguma forma de leitura de
movimentação: a rota já reaplica BOLA sobre o objeto (RC-16), então o scope
funcional aqui só define "pode tentar chamar a rota", nunca "pode ver
qualquer objeto" — a spec não restringe `POST /validar` por perfil além da
autenticação (§15), então não introduz uma exigência de perfil que não
existia no fluxo pré-autenticação.
"""

from __future__ import annotations

from app.models.enums import PerfilUsuario

SCOPE_MOVIMENTACOES_READ = "movimentacoes:read"
SCOPE_MOVIMENTACOES_CREATE = "movimentacoes:create"
SCOPE_MOVIMENTACOES_APPROVE = "movimentacoes:approve"
SCOPE_MOVIMENTACOES_VALIDATE = "movimentacoes:validate"
SCOPE_COLABORADORES_READ = "colaboradores:read"

_SCOPES_POR_PERFIL: dict[PerfilUsuario, tuple[str, ...]] = {
    PerfilUsuario.ADMIN: (
        SCOPE_MOVIMENTACOES_READ,
        SCOPE_MOVIMENTACOES_CREATE,
        SCOPE_MOVIMENTACOES_APPROVE,
        SCOPE_MOVIMENTACOES_VALIDATE,
        SCOPE_COLABORADORES_READ,
    ),
    PerfilUsuario.RH_ANALISTA: (
        SCOPE_MOVIMENTACOES_READ,
        SCOPE_MOVIMENTACOES_CREATE,
        SCOPE_MOVIMENTACOES_VALIDATE,
        SCOPE_COLABORADORES_READ,
    ),
    PerfilUsuario.RH_GESTOR: (
        SCOPE_MOVIMENTACOES_READ,
        SCOPE_MOVIMENTACOES_APPROVE,
        SCOPE_MOVIMENTACOES_VALIDATE,
        SCOPE_COLABORADORES_READ,
    ),
    PerfilUsuario.LIDERANCA: (
        SCOPE_MOVIMENTACOES_READ,
        SCOPE_MOVIMENTACOES_CREATE,
        SCOPE_MOVIMENTACOES_APPROVE,
        SCOPE_MOVIMENTACOES_VALIDATE,
        SCOPE_COLABORADORES_READ,
    ),
}


def scopes_do_perfil(perfil: str) -> list[str]:
    return list(_SCOPES_POR_PERFIL.get(PerfilUsuario(perfil), ()))


def perfil_pode_aprovar_propria_solicitacao(perfil: str) -> bool:
    """spec.md RC-07/RC-12 — exceção exclusiva de `ADMIN`."""
    return PerfilUsuario(perfil) == PerfilUsuario.ADMIN
