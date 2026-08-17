"""Monta o `ValidationContext` a partir do banco — em carga única, sem N+1
(plan.md §6, passo 4). Ponte entre `models/` (ORM) e `validation/` (puro):
este módulo importa ambos; `validation/` nunca importa isto.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.models import Colaborador, Movimentacao
from app.repositories import aprovacao_repository, movimentacao_repository
from app.validation import types as vt


def _cargo_ref(cargo) -> vt.CargoRef | None:
    if cargo is None:
        return None
    aprovacao_adicional = (
        vt.AprovacaoAdicional(cargo.aprovacao_adicional.value) if cargo.aprovacao_adicional else None
    )
    return vt.CargoRef(
        id=cargo.id,
        nivel=cargo.nivel,
        ativo=cargo.ativo,
        permite_gestao=cargo.permite_gestao,
        aprovacao_adicional=aprovacao_adicional,
    )


def _colaborador_ref(colaborador: Colaborador | None, com_cargo: bool = False) -> vt.ColaboradorRef | None:
    if colaborador is None:
        return None
    return vt.ColaboradorRef(
        id=colaborador.id,
        ativo=colaborador.ativo,
        cargo=_cargo_ref(colaborador.cargo) if com_cargo else None,
        gestor_id=colaborador.gestor_id,
    )


def _departamento_ref(departamento) -> vt.DepartamentoRef | None:
    if departamento is None:
        return None
    return vt.DepartamentoRef(id=departamento.id, ativo=departamento.ativo, gestor_id=departamento.gestor_id)


def _centro_custo_ref(centro_custo) -> vt.CentroCustoRef | None:
    if centro_custo is None:
        return None
    return vt.CentroCustoRef(
        id=centro_custo.id, ativo=centro_custo.ativo, responsavel_id=centro_custo.responsavel_id
    )


def _estrutura_ref(estrutura) -> vt.EstruturaRef | None:
    if estrutura is None:
        return None
    return vt.EstruturaRef(id=estrutura.id, ativo=estrutura.ativo)


def _resolver_responsaveis(
    tipo: vt.TipoMovimentacao,
    movimentacao: Movimentacao,
    colaborador: Colaborador | None,
) -> dict[str, vt.ColaboradorRef | None]:
    """spec.md §5.3.1 — origem do aprovador esperado, por tipo. Congelado:
    nenhuma outra forma de derivação é válida."""
    if tipo == vt.TipoMovimentacao.TRANSFERENCIA:
        return {
            "GESTOR_ORIGEM": _colaborador_ref(
                movimentacao.departamento_origem.gestor if movimentacao.departamento_origem else None
            ),
            "GESTOR_DESTINO": _colaborador_ref(
                movimentacao.departamento_destino.gestor if movimentacao.departamento_destino else None
            ),
        }
    if tipo == vt.TipoMovimentacao.PROMOCAO:
        return {"GESTOR_ORIGEM": _colaborador_ref(colaborador.gestor if colaborador else None)}
    if tipo == vt.TipoMovimentacao.TROCA_GESTOR:
        return {
            "GESTOR_ORIGEM": _colaborador_ref(movimentacao.gestor_origem),
            "GESTOR_DESTINO": _colaborador_ref(movimentacao.gestor_destino),
        }
    if tipo == vt.TipoMovimentacao.MUDANCA_CENTRO_CUSTO:
        return {
            "GESTOR_DESTINO": _colaborador_ref(
                movimentacao.centro_custo_destino.responsavel if movimentacao.centro_custo_destino else None
            )
        }
    if tipo == vt.TipoMovimentacao.ALTERACAO_ESTRUTURA:
        return {"GESTOR_ORIGEM": _colaborador_ref(colaborador.gestor if colaborador else None)}
    return {}


def _montar_cadeia_hierarquica(session: Session, gestor_destino_id: int | None) -> dict[int, vt.NoHierarquia]:
    if gestor_destino_id is None:
        return {}
    grafo = movimentacao_repository.carregar_grafo_gestores(session)
    cadeia: dict[int, vt.NoHierarquia] = {}
    atual = gestor_destino_id
    visitados: set[int] = set()
    while atual is not None and atual not in visitados and atual in grafo:
        visitados.add(atual)
        cadeia[atual] = vt.NoHierarquia(id=atual, gestor_id=grafo[atual])
        atual = grafo[atual]
    return cadeia


def montar_contexto(session: Session, movimentacao: Movimentacao) -> vt.ValidationContext:
    tipo = vt.TipoMovimentacao(movimentacao.tipo.value)
    colaborador = movimentacao.colaborador

    aprovacoes_orm = aprovacao_repository.listar_por_movimentacao(session, movimentacao.id)
    aprovacoes = [
        vt.AprovacaoRef(
            tipo=vt.TipoAprovacao(a.tipo.value),
            estado=vt.EstadoAprovacao(a.estado.value),
            aprovador_id=a.aprovador_id,
            aprovador_ativo=a.aprovador.ativo if a.aprovador is not None else None,
        )
        for a in aprovacoes_orm
    ]

    conflito = movimentacao_repository.existe_conflito(
        session, movimentacao.colaborador_id, movimentacao.tipo, movimentacao.id
    )

    cadeia = (
        _montar_cadeia_hierarquica(session, movimentacao.gestor_destino_id)
        if tipo == vt.TipoMovimentacao.TROCA_GESTOR
        else {}
    )

    return vt.ValidationContext(
        movimentacao=vt.MovimentacaoRef(id=movimentacao.id, tipo=tipo, colaborador_id=movimentacao.colaborador_id),
        colaborador=_colaborador_ref(colaborador, com_cargo=True),
        cargo_atual=_cargo_ref(colaborador.cargo) if colaborador else None,
        cargo_destino=_cargo_ref(movimentacao.cargo_destino),
        departamento_origem=_departamento_ref(movimentacao.departamento_origem),
        departamento_destino=_departamento_ref(movimentacao.departamento_destino),
        centro_custo_origem=_centro_custo_ref(movimentacao.centro_custo_origem),
        centro_custo_destino=_centro_custo_ref(movimentacao.centro_custo_destino),
        estrutura_origem=_estrutura_ref(movimentacao.estrutura_origem),
        estrutura_destino=_estrutura_ref(movimentacao.estrutura_destino),
        gestor_origem=_colaborador_ref(movimentacao.gestor_origem),
        gestor_destino=_colaborador_ref(movimentacao.gestor_destino, com_cargo=True),
        cadeia_hierarquica=cadeia,
        aprovacoes=aprovacoes,
        responsaveis_derivados=_resolver_responsaveis(tipo, movimentacao, colaborador),
        conflito_mesmo_tipo_em_aberto=conflito,
    )
