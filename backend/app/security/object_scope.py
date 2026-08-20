"""BOLA — autorização em nível de objeto (spec.md §3/RC-16, plan.md §7.2).

`ADMIN`, `RH_ANALISTA` e `RH_GESTOR` consultam sem filtro organizacional
(spec §3.1). `LIDERANCA` só enxerga sua subárvore hierárquica inteira —
resolvida em uma única consulta por request (`carregar_grafo_gestores`),
nunca uma query por nível/por item de listagem (plan §7.2).

Convenção: "subárvore de X" inclui o próprio X — um líder pode ver/agir
sobre si mesmo, além de todo mundo abaixo dele na cadeia de `gestor_id`.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.models import PerfilUsuario, Usuario
from app.repositories import movimentacao_repository

PERFIS_SEM_FILTRO_ORGANIZACIONAL = (
    PerfilUsuario.ADMIN,
    PerfilUsuario.RH_ANALISTA,
    PerfilUsuario.RH_GESTOR,
)


def ids_subarvore(session: Session, raiz_colaborador_id: int) -> set[int]:
    grafo = movimentacao_repository.carregar_grafo_gestores(session)
    filhos: dict[int, list[int]] = {}
    for colaborador_id, gestor_id in grafo.items():
        if gestor_id is not None:
            filhos.setdefault(gestor_id, []).append(colaborador_id)

    resultado: set[int] = set()
    pilha = [raiz_colaborador_id]
    while pilha:
        atual = pilha.pop()
        if atual in resultado:
            continue
        resultado.add(atual)
        pilha.extend(filhos.get(atual, ()))
    return resultado


def ids_colaboradores_permitidos(session: Session, usuario: Usuario) -> set[int] | None:
    """`None` significa "sem filtro" (acesso total). Conjunto vazio significa
    "nenhum objeto visível" (ex.: LIDERANCA sem colaborador vinculado)."""
    if usuario.perfil in PERFIS_SEM_FILTRO_ORGANIZACIONAL:
        return None
    if usuario.perfil == PerfilUsuario.LIDERANCA:
        if usuario.colaborador_id is None:
            return set()
        return ids_subarvore(session, usuario.colaborador_id)
    return set()


def pode_visualizar_colaborador(session: Session, usuario: Usuario, colaborador_id: int) -> bool:
    permitidos = ids_colaboradores_permitidos(session, usuario)
    return permitidos is None or colaborador_id in permitidos


def pode_criar_para_colaborador(session: Session, usuario: Usuario, colaborador_id: int) -> bool:
    return pode_visualizar_colaborador(session, usuario, colaborador_id)


def pode_visualizar_movimentacao(session: Session, usuario: Usuario, colaborador_id_da_movimentacao: int) -> bool:
    return pode_visualizar_colaborador(session, usuario, colaborador_id_da_movimentacao)
