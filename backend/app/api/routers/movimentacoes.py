import math
from typing import Literal

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.schemas import (
    AprovacaoResponse,
    CargoResumo,
    CentroCustoResumo,
    ColaboradorDetalhe,
    ColaboradorResumo,
    DepartamentoResumo,
    EstruturaResumo,
    GestorResumo,
    InconsistenciaResponse,
    MovimentacaoDetalheResponse,
    MovimentacaoItem,
    MovimentacaoListaResponse,
    UltimaValidacaoResponse,
)
from app.database import get_db
from app.models import Movimentacao, StatusMovimentacao, TipoMovimentacao
from app.repositories import aprovacao_repository, auditoria_repository, movimentacao_repository
from app.services.exceptions import MovimentacaoNaoEncontrada

router = APIRouter(prefix="/movimentacoes", tags=["movimentacoes"])


@router.get("", response_model=MovimentacaoListaResponse)
def listar_movimentacoes(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, alias="pageSize"),
    status: StatusMovimentacao | None = Query(None),
    busca: str | None = Query(None),
    ordenar_por: str = Query("dataSolicitacao", alias="ordenarPor"),
    direcao: Literal["asc", "desc"] = Query("desc"),
    db: Session = Depends(get_db),
) -> MovimentacaoListaResponse:
    itens, total = movimentacao_repository.listar(
        db,
        page=page,
        page_size=page_size,
        status=status,
        busca=busca,
        ordenar_por=ordenar_por,
        direcao=direcao,
    )
    page_size_efetivo = min(page_size, movimentacao_repository.PAGE_SIZE_MAXIMO)
    total_pages = math.ceil(total / page_size_efetivo) if total else 0

    return MovimentacaoListaResponse(
        items=[_item(m) for m in itens],
        page=page,
        page_size=page_size_efetivo,
        total=total,
        total_pages=total_pages,
    )


@router.get("/{movimentacao_id}", response_model=MovimentacaoDetalheResponse)
def detalhar_movimentacao(movimentacao_id: int, db: Session = Depends(get_db)) -> MovimentacaoDetalheResponse:
    mov = movimentacao_repository.buscar_por_id(db, movimentacao_id)
    if mov is None:
        raise MovimentacaoNaoEncontrada(movimentacao_id)

    aprovacoes_orm = aprovacao_repository.listar_por_movimentacao(db, movimentacao_id)
    ultima = auditoria_repository.buscar_ultima(db, movimentacao_id)

    return _detalhe(mov, aprovacoes_orm, ultima)


def _item(mov: Movimentacao) -> MovimentacaoItem:
    return MovimentacaoItem(
        id=mov.id,
        tipo=mov.tipo.value,
        status=mov.status.value,
        colaborador=ColaboradorResumo(
            id=mov.colaborador.id, matricula=mov.colaborador.matricula, nome=mov.colaborador.nome
        ),
        data_solicitacao=mov.data_solicitacao,
        resultado_ultima_validacao=(
            mov.resultado_ultima_validacao.value if mov.resultado_ultima_validacao else None
        ),
    )


def _detalhe(mov: Movimentacao, aprovacoes_orm, ultima) -> MovimentacaoDetalheResponse:
    return MovimentacaoDetalheResponse(
        id=mov.id,
        tipo=mov.tipo.value,
        status=mov.status.value,
        data_solicitacao=mov.data_solicitacao,
        colaborador=ColaboradorDetalhe(
            id=mov.colaborador.id,
            matricula=mov.colaborador.matricula,
            nome=mov.colaborador.nome,
            ativo=mov.colaborador.ativo,
        ),
        cargo_atual=(
            _cargo(mov.colaborador.cargo)
            if mov.tipo == TipoMovimentacao.PROMOCAO and mov.colaborador.cargo
            else None
        ),
        cargo_destino=_cargo(mov.cargo_destino) if mov.cargo_destino else None,
        departamento_origem=_departamento(mov.departamento_origem) if mov.departamento_origem else None,
        departamento_destino=_departamento(mov.departamento_destino) if mov.departamento_destino else None,
        centro_custo_origem=_centro_custo(mov.centro_custo_origem) if mov.centro_custo_origem else None,
        centro_custo_destino=_centro_custo(mov.centro_custo_destino) if mov.centro_custo_destino else None,
        estrutura_origem=_estrutura(mov.estrutura_origem) if mov.estrutura_origem else None,
        estrutura_destino=_estrutura(mov.estrutura_destino) if mov.estrutura_destino else None,
        gestor_origem=_gestor(mov.gestor_origem) if mov.gestor_origem else None,
        gestor_destino=_gestor(mov.gestor_destino) if mov.gestor_destino else None,
        aprovacoes=[_aprovacao(a) for a in aprovacoes_orm],
        ultima_validacao=_ultima_validacao(ultima) if ultima else None,
    )


def _cargo(cargo) -> CargoResumo:
    return CargoResumo(id=cargo.id, nome=cargo.nome, nivel=cargo.nivel)


def _departamento(dep) -> DepartamentoResumo:
    return DepartamentoResumo(id=dep.id, codigo=dep.codigo, nome=dep.nome, ativo=dep.ativo)


def _centro_custo(cc) -> CentroCustoResumo:
    return CentroCustoResumo(id=cc.id, codigo=cc.codigo, nome=cc.nome, ativo=cc.ativo)


def _estrutura(est) -> EstruturaResumo:
    return EstruturaResumo(id=est.id, codigo=est.codigo, nome=est.nome, ativo=est.ativo)


def _gestor(gestor) -> GestorResumo:
    return GestorResumo(id=gestor.id, matricula=gestor.matricula, nome=gestor.nome, ativo=gestor.ativo)


def _aprovacao(a) -> AprovacaoResponse:
    return AprovacaoResponse(
        tipo=a.tipo.value,
        estado=a.estado.value,
        aprovador=(
            ColaboradorResumo(id=a.aprovador.id, matricula=a.aprovador.matricula, nome=a.aprovador.nome)
            if a.aprovador
            else None
        ),
        data_decisao=a.data_decisao,
    )


def _ultima_validacao(auditoria) -> UltimaValidacaoResponse:
    return UltimaValidacaoResponse(
        resultado=auditoria.resultado.value,
        validado_em=auditoria.data_hora,
        inconsistencias=[
            InconsistenciaResponse(codigo=i.codigo_regra, mensagem=i.mensagem, severidade=i.severidade.value)
            for i in auditoria.inconsistencias
        ],
    )
