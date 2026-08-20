"""AprovacaoService — entrada única de decisão de aprovação (spec.md §6.2,
plan.md §10). Corrige o bug intermitente de histórico: `Aprovacao` +
`HistoricoProcessamento` + reavaliação do gate + status + Job (quando apta)
sempre no mesmo commit — se qualquer passo falhar antes do commit, nada
persiste (a sessão nunca é commitada parcialmente).
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal

from sqlalchemy.orm import Session

from app.models import (
    Colaborador,
    EstadoAprovacao,
    OrigemEvento,
    PerfilUsuario,
    StatusMovimentacao,
    TipoAprovacao,
    TipoEventoProcessamento,
    Usuario,
)
from app.processing.producer import aplicar_gate
from app.repositories import aprovacao_repository
from app.repositories import historico_processamento_repository as historico_repo
from app.repositories import movimentacao_repository
from app.repositories.exceptions import OrdenacaoInvalida
from app.security import object_scope
from app.services import rotulo_service
from app.services.exceptions import (
    AcessoNegado,
    AprovacaoForaDeOrdem,
    AprovacaoJaDecidida,
    AprovacaoNaoEncontrada,
    MovimentacaoNaoAguardandoAprovacao,
    MovimentacaoNaoEncontrada,
)
from app.services.movimentacao_service import montar_contexto
from app.validation.aprovacoes import exigencias_para
from app.validation.types import ExigenciaAprovacao


def _usuario_pode_decidir(exigencia: ExigenciaAprovacao, usuario: Usuario) -> bool:
    """spec.md §5.8/RC-12 — ADMIN decide qualquer aprovação. Para os demais
    perfis, etapas de pessoa específica exigem identidade
    (`usuario.colaborador_id`); etapas por perfil exigem o perfil exato."""
    if usuario.perfil == PerfilUsuario.ADMIN:
        return True
    if exigencia.aprovador_esperado_colaborador_id is not None:
        return usuario.colaborador_id == exigencia.aprovador_esperado_colaborador_id
    if exigencia.perfil_esperado is not None:
        return usuario.perfil.value == exigencia.perfil_esperado
    return False


def _mensagem_evento(tipo: TipoAprovacao, decisao: EstadoAprovacao, usuario: Usuario) -> str:
    verbo = "aprovada" if decisao == EstadoAprovacao.APROVADA else "reprovada"
    return f"Aprovação {tipo.value} {verbo} por {usuario.username}."


ORDENACAO_PENDENTES_PADRAO = "data_solicitacao"

_CHAVES_ORDENACAO_PENDENTES = {
    "id": lambda mov, _exigencia: mov.id,
    "data_solicitacao": lambda mov, _exigencia: mov.data_solicitacao,
    "tipo": lambda mov, exigencia: exigencia.tipo.value,
    "solicitante": lambda mov, _exigencia: mov.solicitante.username if mov.solicitante else "",
    "colaborador": lambda mov, _exigencia: mov.colaborador.nome,
    "setor": lambda mov, _exigencia: rotulo_service.setor(mov) or "",
}
"""spec.md RC-51/plan.md §24.6 — whitelist de campos ordenáveis de
`/aprovacoes/pendentes`. Nenhum outro valor é aceito."""


def listar_pendentes(
    session: Session,
    usuario: Usuario,
    busca: str | None = None,
    ordenar_por: str = ORDENACAO_PENDENTES_PADRAO,
    direcao: str = "desc",
) -> list[tuple]:
    """spec.md §6.1/RC-35/RC-51 — só aprovações **acionáveis agora**:
    `usuario` pode decidir, dentro do escopo BOLA, e todas as etapas de
    ordem inferior já estão `APROVADA` (a mesma checagem de
    `decidir`/`AprovacaoForaDeOrdem` — uma etapa posterior nunca aparece
    aqui antes da anterior obrigatória). `busca`/`ordenar_por`/`direcao`
    (padrão `data_solicitacao DESC`) não afetam esse filtro de
    "acionável agora" — só a apresentação. Retorna tuplas
    `(movimentacao, exigencia, aprovacao)`."""
    if ordenar_por not in _CHAVES_ORDENACAO_PENDENTES:
        raise OrdenacaoInvalida(ordenar_por)

    ids_permitidos = object_scope.ids_colaboradores_permitidos(session, usuario)
    movimentacoes = movimentacao_repository.listar_aguardando_aprovacao(session, ids_permitidos, busca)

    resultado = []
    for mov in movimentacoes:
        ctx = montar_contexto(session, mov)
        exigencias = exigencias_para(ctx)
        persistidas = {a.tipo: a for a in aprovacao_repository.listar_por_movimentacao(session, mov.id)}
        for exigencia in exigencias:
            aprovacao = persistidas.get(exigencia.tipo)
            if aprovacao is None or aprovacao.estado != EstadoAprovacao.PENDENTE:
                continue
            if not _usuario_pode_decidir(exigencia, usuario):
                continue
            etapas_anteriores_ok = all(
                persistidas.get(e.tipo) is not None and persistidas[e.tipo].estado == EstadoAprovacao.APROVADA
                for e in exigencias
                if e.ordem < exigencia.ordem
            )
            if not etapas_anteriores_ok:
                continue
            resultado.append((mov, exigencia, aprovacao))

    chave = _CHAVES_ORDENACAO_PENDENTES[ordenar_por]
    resultado.sort(key=lambda item: chave(item[0], item[1]), reverse=(direcao == "desc"))
    return resultado


def _auto_satisfazer_por_mesmo_aprovador(
    session: Session,
    movimentacao_id: int,
    exigencias: list[ExigenciaAprovacao],
    agora: datetime,
    solicitante_usuario_id: int | None,
) -> None:
    """RC-42 (dedup de aprovador — decisão do candidato em T-75) — quando
    duas exigências de PESSOA ESPECÍFICA (`aprovador_esperado_colaborador_id`)
    da mesma movimentação resolvem para o mesmo colaborador, uma única
    decisão real satisfaz as duas: não força um segundo clique da mesma
    pessoa. Nunca deduplica etapas por PERFIL (RH/GESTOR_RH/
    GESTOR_RH_ADICIONAL) só por coincidência de quem decidiu — só entra em
    jogo quando o `aprovador_id` já persistido em outra etapa desta
    movimentação bate exatamente com o `aprovador_esperado_colaborador_id`
    da etapa ainda pendente (ou seja, quando é de fato a mesma pessoa real
    quem já decidiu — uma decisão via override de ADMIN, registrada com o
    `colaborador_id` do próprio ADMIN, não conta como decisão da pessoa
    esperada). Cada etapa auto-satisfeita continua existindo como sua
    própria `Aprovacao` (nunca é apagada/fundida) — a auditoria preserva
    quais papéis foram atendidos, com um evento de histórico explícito.
    Roda em loop até estabilizar, porque satisfazer uma etapa pode destravar
    a ordem de outra (RC-35)."""
    mudou = True
    while mudou:
        mudou = False
        persistidas = {a.tipo: a for a in aprovacao_repository.listar_por_movimentacao(session, movimentacao_id)}
        aprovador_por_tipo_decidido = {
            a.tipo: a.aprovador_id
            for a in persistidas.values()
            if a.estado == EstadoAprovacao.APROVADA and a.aprovador_id is not None
        }
        for exigencia in exigencias:
            if exigencia.aprovador_esperado_colaborador_id is None:
                continue  # etapa por perfil — nunca deduplicada
            linha = persistidas.get(exigencia.tipo)
            if linha is None or linha.estado != EstadoAprovacao.PENDENTE:
                continue
            anteriores_ok = all(
                persistidas.get(e.tipo) is not None and persistidas[e.tipo].estado == EstadoAprovacao.APROVADA
                for e in exigencias
                if e.ordem < exigencia.ordem
            )
            if not anteriores_ok:
                continue
            tipo_ja_satisfeito = next(
                (
                    t
                    for t, aprovador_id in aprovador_por_tipo_decidido.items()
                    if t != exigencia.tipo and aprovador_id == exigencia.aprovador_esperado_colaborador_id
                ),
                None,
            )
            if tipo_ja_satisfeito is None:
                continue
            aprovacao_repository.decidir(
                session, linha, EstadoAprovacao.APROVADA, exigencia.aprovador_esperado_colaborador_id, None, agora
            )
            colaborador = session.get(Colaborador, exigencia.aprovador_esperado_colaborador_id)
            nome = colaborador.nome if colaborador is not None else "aprovador"
            historico_repo.registrar(
                session,
                movimentacao_id,
                TipoEventoProcessamento.APROVACAO_CONCLUIDA,
                OrigemEvento.SISTEMA,
                (
                    f"Aprovação {exigencia.tipo.value} satisfeita automaticamente — "
                    f"mesmo aprovador de {tipo_ja_satisfeito.value} ({nome})."
                ),
                agora,
                solicitante_usuario_id=solicitante_usuario_id,
            )
            mudou = True


def decidir(
    session: Session,
    movimentacao_id: int,
    tipo: TipoAprovacao,
    usuario: Usuario,
    decisao: Literal["APROVADA", "REPROVADA"],
    justificativa: str | None,
):
    agora = datetime.now(timezone.utc).replace(tzinfo=None)

    mov = movimentacao_repository.buscar_por_id(session, movimentacao_id)
    if mov is None or not object_scope.pode_visualizar_movimentacao(session, usuario, mov.colaborador_id):
        raise MovimentacaoNaoEncontrada(movimentacao_id)

    if mov.status != StatusMovimentacao.AGUARDANDO_APROVACAO:
        # spec.md RC-47/T-85 — BLOQUEADA (ou qualquer outro estado que já
        # deixou a fase de aprovação) é terminal: mesmo uma etapa "paralela"
        # (mesma ordem) ainda PENDENTE no banco não pode mais ser decidida —
        # o workflow de aprovação já encerrou.
        raise MovimentacaoNaoAguardandoAprovacao()

    aprovacao = aprovacao_repository.buscar_por_movimentacao_e_tipo(session, movimentacao_id, tipo)
    if aprovacao is None:
        raise AprovacaoNaoEncontrada(movimentacao_id, tipo.value)

    ctx = montar_contexto(session, mov)
    exigencias = exigencias_para(ctx)
    exigencia = next((e for e in exigencias if e.tipo == tipo), None)
    if exigencia is None:
        raise AprovacaoNaoEncontrada(movimentacao_id, tipo.value)

    if not _usuario_pode_decidir(exigencia, usuario):
        raise AcessoNegado(f"Perfil {usuario.perfil.value} não pode decidir a aprovação {tipo.value}.")

    if aprovacao.estado != EstadoAprovacao.PENDENTE:
        raise AprovacaoJaDecidida()

    estados_persistidos = {a.tipo: a.estado for a in aprovacao_repository.listar_por_movimentacao(session, movimentacao_id)}
    etapas_anteriores_ok = all(
        estados_persistidos.get(e.tipo) == EstadoAprovacao.APROVADA for e in exigencias if e.ordem < exigencia.ordem
    )
    if not etapas_anteriores_ok:
        raise AprovacaoForaDeOrdem()

    novo_estado = EstadoAprovacao.APROVADA if decisao == "APROVADA" else EstadoAprovacao.REPROVADA
    aprovacao_repository.decidir(session, aprovacao, novo_estado, usuario.colaborador_id, justificativa, agora)

    tipo_evento = (
        TipoEventoProcessamento.APROVACAO_CONCLUIDA
        if novo_estado == EstadoAprovacao.APROVADA
        else TipoEventoProcessamento.APROVACAO_REPROVADA
    )
    historico_repo.registrar(
        session,
        movimentacao_id,
        tipo_evento,
        OrigemEvento.MANUAL,
        _mensagem_evento(tipo, novo_estado, usuario),
        agora,
        ator_usuario_id=usuario.id,
        solicitante_usuario_id=mov.solicitante_usuario_id,
    )

    _auto_satisfazer_por_mesmo_aprovador(session, movimentacao_id, exigencias, agora, mov.solicitante_usuario_id)

    if mov.status == StatusMovimentacao.AGUARDANDO_APROVACAO:
        aplicar_gate(session, mov, agora)

    session.commit()
    session.refresh(aprovacao)
    return aprovacao
