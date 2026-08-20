"""Criação de solicitações — spec.md §4/plan.md §8.2.

Fluxo único e transacional: conferir escopo do objeto -> carregar
colaborador/destino -> derivar origem a partir do estado atual -> persistir
`Movimentacao` -> calcular aprovações exigidas pela política única
(`app.validation.aprovacoes`, a mesma fonte usada pelo gate/producer) ->
`SOLICITACAO_RECEBIDA` -> reavaliar gate -> commit único. O cliente nunca
controla solicitante/origem/status/aprovações (spec §4.2).

Nesta tarefa (T-60), a política ainda é a matriz estática por tipo — T-61
a torna sensível ao solicitante; este serviço já delega 100% da decisão de
"quais aprovações" para `app.validation.aprovacoes`/`processing.producer`,
então não precisa mudar quando a política evoluir.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.api.schemas.movimentacao import (
    CriarAlteracaoEstruturaRequest,
    CriarMudancaCentroCustoRequest,
    CriarPromocaoRequest,
    CriarTransferenciaRequest,
    CriarTrocaGestorRequest,
)
from app.models import (
    Cargo,
    CentroCusto,
    Colaborador,
    Departamento,
    EstruturaOrganizacional,
    Movimentacao,
    OrigemEvento,
    StatusMovimentacao,
    TipoAprovacao,
    TipoEventoProcessamento,
    TipoMovimentacao,
    Usuario,
)
from app.processing.producer import aplicar_gate
from app.repositories import aprovacao_repository
from app.repositories import historico_processamento_repository as historico_repo
from app.security import object_scope
from app.services.exceptions import (
    ApprovadorHierarquicoNaoResolvido,
    ColaboradorNaoEncontrado,
    ReferenciaNaoEncontrada,
)
from app.services.movimentacao_service import montar_contexto
from app.validation import aprovacoes as approval_policy

CriarMovimentacaoPayload = (
    CriarTransferenciaRequest
    | CriarPromocaoRequest
    | CriarMudancaCentroCustoRequest
    | CriarTrocaGestorRequest
    | CriarAlteracaoEstruturaRequest
)


def _carregar_colaborador_no_escopo(session: Session, usuario: Usuario, colaborador_id: int) -> Colaborador:
    colaborador = session.get(Colaborador, colaborador_id)
    if colaborador is None or not object_scope.pode_criar_para_colaborador(session, usuario, colaborador_id):
        # RC-16: mesmo tratamento para "não existe" e "fora do escopo" — não
        # revela qual dos dois casos ocorreu.
        raise ColaboradorNaoEncontrado(colaborador_id)
    return colaborador


def _campos_derivados(payload: CriarMovimentacaoPayload, colaborador: Colaborador, session: Session) -> dict:
    if isinstance(payload, CriarTransferenciaRequest):
        destino = session.get(Departamento, payload.departamento_destino_id)
        if destino is None:
            raise ReferenciaNaoEncontrada("Departamento", payload.departamento_destino_id)
        return {
            "departamento_origem_id": colaborador.departamento_id,
            "departamento_destino_id": destino.id,
        }
    if isinstance(payload, CriarPromocaoRequest):
        destino = session.get(Cargo, payload.cargo_destino_id)
        if destino is None:
            raise ReferenciaNaoEncontrada("Cargo", payload.cargo_destino_id)
        return {
            "cargo_origem_id": colaborador.cargo_id,
            "cargo_destino_id": destino.id,
            "centro_custo_origem_id": colaborador.centro_custo_id,
        }
    if isinstance(payload, CriarMudancaCentroCustoRequest):
        destino = session.get(CentroCusto, payload.centro_custo_destino_id)
        if destino is None:
            raise ReferenciaNaoEncontrada("CentroCusto", payload.centro_custo_destino_id)
        return {
            "centro_custo_origem_id": colaborador.centro_custo_id,
            "centro_custo_destino_id": destino.id,
        }
    if isinstance(payload, CriarTrocaGestorRequest):
        destino = session.get(Colaborador, payload.gestor_destino_id)
        if destino is None:
            raise ReferenciaNaoEncontrada("Colaborador", payload.gestor_destino_id)
        return {
            "gestor_origem_id": colaborador.gestor_id,
            "gestor_destino_id": destino.id,
        }
    if isinstance(payload, CriarAlteracaoEstruturaRequest):
        destino = session.get(EstruturaOrganizacional, payload.estrutura_destino_id)
        if destino is None:
            raise ReferenciaNaoEncontrada("EstruturaOrganizacional", payload.estrutura_destino_id)
        return {
            "estrutura_origem_id": colaborador.estrutura_id,
            "estrutura_destino_id": destino.id,
        }
    raise AssertionError(f"tipo de solicitação não tratado: {payload}")  # pragma: no cover — união exaustiva


def criar(session: Session, payload: CriarMovimentacaoPayload, usuario: Usuario) -> Movimentacao:
    agora = datetime.now(timezone.utc).replace(tzinfo=None)
    colaborador = _carregar_colaborador_no_escopo(session, usuario, payload.colaborador_id)
    campos = _campos_derivados(payload, colaborador, session)

    movimentacao = Movimentacao(
        tipo=TipoMovimentacao(payload.tipo),
        status=StatusMovimentacao.AGUARDANDO_APROVACAO,
        colaborador_id=colaborador.id,
        data_solicitacao=agora,
        solicitante_usuario_id=usuario.id,
        **campos,
    )
    session.add(movimentacao)
    session.flush()

    ctx = montar_contexto(session, movimentacao)
    exigencias = approval_policy.exigencias_para(ctx)
    for exigencia in exigencias:
        # spec.md RC-38/T-75 — GERENCIA/DIRETORIA precisam de uma pessoa
        # concreta resolvida pela cadeia hierárquica (papel_lideranca); se a
        # política não conseguiu resolver ninguém, a criação falha
        # explicitamente aqui, antes de qualquer aprovação ser persistida
        # (session.flush() da Movimentacao acima é revertido pelo rollback
        # de get_db() quando a exceção propaga — sem persistência parcial).
        if exigencia.tipo.value in ("GERENCIA", "DIRETORIA") and exigencia.aprovador_esperado_colaborador_id is None:
            raise ApprovadorHierarquicoNaoResolvido(exigencia.tipo.value)
        aprovacao_repository.criar_pendente(session, movimentacao.id, TipoAprovacao(exigencia.tipo.value))

    historico_repo.registrar(
        session,
        movimentacao.id,
        TipoEventoProcessamento.SOLICITACAO_RECEBIDA,
        OrigemEvento.MANUAL,
        f"Solicitação de {movimentacao.tipo.value.lower()} recebida.",
        agora,
        ator_usuario_id=usuario.id,
        solicitante_usuario_id=usuario.id,
    )

    # spec §4.3: caso a política não exija nenhuma aprovação humana, o gate
    # já libera PENDENTE+job na mesma operação em vez de ficar preso em
    # AGUARDANDO_APROVACAO sem nada pendente para decidir.
    aplicar_gate(session, movimentacao, agora)

    session.commit()
    session.refresh(movimentacao)
    return movimentacao
